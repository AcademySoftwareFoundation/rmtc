# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import warnings
import random
from itertools import islice, chain, repeat

import torch
from torch import nn
from torch import optim
import numpy as np

from rmtc.core.ops.io.torch.weights import TorchWeightsFile
from rmtc.core.ops.io.torch.checkpoints import TorchCheckpointFile

from rmtc.ops.train import Trainer
from rmtc.system import RMTCException, Device
from rmtc.ops.artifacts import ModelType
from rmtc.ops.process import Process
from rmtc.system.objects import IN

MAX_SIGNED_32_INT = (1 << 31) - 1

ignore_warnings = [
    ".*TypedStorage is deprecated.*",
    ".*Converting a tensor with requires_grad=True.*",
]
for to_ignore in ignore_warnings:
    warnings.filterwarnings("ignore", message=to_ignore)


def generate_batch(dataset, batch_size, repetitions=0):
    """
    Batch dataset into tuples of length batch_size.
    The last batch may be shorter.

    Args:
        dataset (rmtc.Dataset): RMTC training data
        batch_size (int): Number of data samples to batch together
        repetitions (int): Number of times to consecutively repeat samples
    """
    if batch_size < 1:
        raise ValueError("Batch size must be at least one")
    it = iter(dataset)
    if repetitions:
        it = chain.from_iterable(repeat(entry, repetitions) for entry in it)

    for first in it:
        batch_iterator = chain((first,), islice(it, batch_size - 1))
        yield tuple(batch_iterator)


class TorchRegression(Trainer):
    """
    PyTorch regression trainer with CUDA support and comprehensive logging.

    The TorchRegression class provides a complete training implementation for
    PyTorch regression models with automatic mixed precision, checkpointing,
    experiment tracking, and support for multiple optimizers. It integrates
    with the RMTC system for artifact management and experiment reproducibility.
    The trainer supports binary cross-entropy with logits loss and includes
    comprehensive logging of training metrics, hyperparameters, and checkpoints.
    It requires CUDA availability and automatically manages GPU memory and
    mixed precision training.
    """

    def __init__(
        self,
        checkpoint_interval=5,
        lr=0.006,
        batch_size=5,
        repetitions=0,
        accumulation_steps=1,
        epochs=5,
        optimizer="adam",
        criterion="bce",
        device=Device.GPU,
        pre_process=None,
        random_seed=None,
    ):
        """Initialize TorchRegression trainer with hyperparameters."""
        super(TorchRegression, self).__init__(
            checkpoint_interval=checkpoint_interval,
            epochs=epochs,
            batch_size=batch_size,
            device=device,
        )
        self.add_property("lr", float, lr)
        self.add_property("optimizer", str, optimizer)
        self.add_property("criterion", str, criterion)
        self.add_property("accumulation_steps", int, accumulation_steps)
        self.add_property("repetitions", int, repetitions)
        self.add_property(
            "pre_process",
            [Process],
            pre_process,
            direction=IN,
        )

        if random_seed is None:
            random_seed = random.randint(1, MAX_SIGNED_32_INT)
        self.add_property("random_seed", int, random_seed)

        self.finish = False

    def run(
        self,
        tracker,
        run,
        asset_manager,
        dataset_range,
    ):
        """
        Execute the complete training process with logging and checkpointing.
        """

        # TODO : deal with dataset ranges
        if (dataset_range[1] - dataset_range[0]) != 1:
            raise NotImplementedError()

        # TODO : move torch-agnostic aspects of this code up the stack
        # for example: reading, validation, preprocess & batching

        # get model & dataset and validate they are compatible
        model = run.model
        dataset = run.dataset

        # validate the dataset before starting
        asset_manager.read([dataset])
        if not dataset.is_valid():
            raise RMTCException(f"Invalid entries in dataset {dataset}")
        if len(dataset) == 0:
            raise RMTCException("No data for training!")
        if not dataset.valid_types(model.input_types + model.output_types):
            raise RMTCException(f"Dataset types {dataset}, do not match {model}")

        # load model duplicate
        # TODO: model should really be const, taking a duplicate
        # however creating checkpoints and weights off the duplicate
        # causes these artifacts to link to the duplcate, not the original
        training_device = "cuda"
        if self.device == Device.CPU:
            training_device = "cpu"
        else:
            if not torch.cuda.is_available():
                raise RMTCException(
                    f"CUDA is not available. Trainer {self} requires a GPU."
                )
        training_model = self.get_model_instance(run, asset_manager)
        torch_model = training_model.torch_model
        torch_model = torch_model.to(training_device)

        # setup optimiser
        optimizer = None
        if self.optimizer == "adam":
            optimizer = optim.Adam(
                filter(lambda p: p.requires_grad, torch_model.parameters()), lr=self.lr
            )
        elif self.optimizer == "adadelta":
            optimizer = optim.Adadelta(
                filter(lambda p: p.requires_grad, torch_model.parameters()),
                lr=self.lr,
            )
        elif self.optimizer == "rmsprop":
            optimizer = optim.RMSprop(
                filter(lambda p: p.requires_grad, torch_model.parameters()), lr=self.lr
            )
        elif self.optimizer == "sgd":
            optimizer = optim.SGD(
                filter(lambda p: p.requires_grad, torch_model.parameters()), lr=self.lr
            )
        else:
            raise RMTCException(f"Invalid optimizer: {self.optimizer}")

        # setup criterion
        criterion = None
        if self.criterion == "bce":  # stable classifier loss
            criterion = nn.BCEWithLogitsLoss()
        elif self.criterion == "mse":  # regression loss
            criterion = nn.MSELoss()
        elif self.criterion == "crossentropy":  # common classifier loss
            criterion = nn.CrossEntropyLoss()
        else:  # assign a preferred criterion depending on the model
            if model.model_type == ModelType.REGRESSION:
                criterion = nn.MSELoss()
            elif model.model_type == ModelType.CLASSIFICATION:
                criterion = nn.BCEWithLogitsLoss()
        if criterion is None:
            raise RMTCException(f"Invalid criterion: {self.criterion}")

        # init
        checkpoints = []
        repetitions = 1 + self.repetitions
        total_samples = len(dataset) * repetitions
        num_batches = (total_samples + self.batch_size - 1) // self.batch_size
        mean_epoch_loss = np.zeros(num_batches)
        mean_loss = []
        step = 0
        scaler = torch.amp.GradScaler("cuda")
        metric = 1.0
        epoch = 0

        # output status to log
        tracker.log_info(f"Starting Trainer {self.name}")
        tracker.log_info(f"- Solution: {run.solution}")
        tracker.log_info(f"- Run: {run}")
        tracker.log_info(f"- Device: {self.device}")
        tracker.log_info(f"- Epochs: {self.epochs}")
        tracker.log_info(f"- Dataset: {dataset.uri} ({len(dataset)})")
        tracker.log_info(f"- Model: {model.uri}")
        tracker.log_info(f"- Learning Rate: {self.lr}")
        tracker.log_info(f"- Criterion: {self.criterion}")
        tracker.log_info(f"- Optimizer: {self.optimizer}")
        tracker.log_info(f"- Batch Size: {self.batch_size}")
        tracker.log_info(f"- Repeat Data: {self.repetitions}")
        tracker.log_info(f"- Gradient Accumulation Steps: {self.accumulation_steps}")
        tracker.log_info(f"- Random Seed: {self.random_seed}")

        # run epochs
        torch.cuda.empty_cache()
        torch_model.set_training(True)
        torch_model.train()
        optimizer.zero_grad()
        for i in range(self.epochs):

            # epoch is not index from 0
            epoch = i + 1

            # Requst made to end training run
            if self.finish:
                break

            # TODO: single batch right now
            running_loss = 0.0
            iteration = 0
            for data_rows in generate_batch(
                dataset, self.batch_size, repetitions=repetitions
            ):
                # End training run
                if self.finish:
                    break

                # get the src and dst data by mapping rows to the input & output
                # NOTE: this could be more formal, datasets are just 2D tables
                # so we have to cherry pick the inputs and outputs, which
                # by convention are organised: in1, in2, in3, out1, out2
                # We could nominate the input and output indices at the trainer level
                # We could have the dataset nominate input and output
                # We could have views on datasets that nominate input and output
                # This works for the minute
                src = []
                dst = []
                try:
                    for row in data_rows:
                        inputs_outputs = model.extract_inputs_outputs(row)
                        src.append(inputs_outputs[0])
                        dst.append(inputs_outputs[1])
                except RMTCException as e:
                    tracker.log_warning(
                        f"Model {model} not compatible with dataset row {row}, {e}"
                    )
                    continue

                # load all the assets
                try:
                    for row in data_rows:
                        asset_manager.read(row)
                except RMTCException as e:
                    tracker.log_warning(
                        f"Failed to read assets {e}, src: {src} dst: {dst}"
                    )
                    continue

                # run augmentation/preprocess
                if self.pre_process:

                    # Use deterministic random seeds for transformation
                    random_seeds = []
                    random.seed(self.random_seed)
                    for _ in range(len(src)):
                        random_seeds.append(random.randint(1, MAX_SIGNED_32_INT))

                    # process src & dst using the same seed
                    for src_assets, dst_assets, random_seed in zip(
                        src, dst, random_seeds
                    ):
                        for src_asset, dst_asset in zip(src_assets, dst_assets):
                            random.seed(random_seed)
                            for processor in self.pre_process:
                                src_asset.process(processor)
                            random.seed(random_seed)
                            for processor in self.pre_process:
                                dst_asset.process(processor)

                # convert asset to model input and output
                inputs = model.to_input(src, device=self.device)
                outputs = model.to_output(dst, device=self.device)

                # run prediction
                with torch.amp.autocast("cuda"):
                    prediction = torch_model(inputs)
                    loss = criterion(prediction, outputs)

                # Scale loss for gradient accumulation
                scaled_loss = loss / self.accumulation_steps

                # step
                scaler.scale(scaled_loss).backward()

                # Accumulate gradient across multiple batches
                if (iteration + 1) % self.accumulation_steps == 0:
                    scaler.step(optimizer)
                    scaler.update()
                    optimizer.zero_grad()

                # metrics
                running_loss += loss.item()
                mean_epoch_loss[iteration] = loss  # BUG: unexpected behavior
                step += 1
                tracker.log_metric(name="training_loss", step=step, metric=loss)
                iteration += 1

                # unload the batch
                for row in data_rows:
                    asset_manager.reset(row)
                torch.cuda.empty_cache()

            # Ensure we do the final gradient update
            if iteration % self.accumulation_steps != 0:
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad()

            # did not move the needle
            if iteration == 0:
                tracker.log_warning(
                    f"No data loaded in dataset {dataset}@{dataset.uri}"
                )

            # update model metrics
            mean_loss.append(mean_epoch_loss.mean())
            metric = mean_loss[-1]
            torch.cuda.empty_cache()
            tracker.log_info(f"Loss: {metric}", step=epoch)
            checkpoint = self._update(
                run=run,
                model=model,
                metric=metric,
                epoch=epoch,
                tracker=tracker,
                optimizer_name=self.optimizer,
                optimizer=optimizer,
                asset_manager=asset_manager,
            )
            if checkpoint is not None:
                checkpoints.append(checkpoint)
                torch.cuda.empty_cache()

        tracker.log_hyperparameters(
            params={
                "lr": self.lr,
                "epochs": self.epochs,
                "batch_size": self.batch_size,
                "repeat data": self.repetitions,
                "accumulation_steps": self.accumulation_steps,
                "optimizer": self.optimizer,
            },
            metric=metric,
        )
        tracker.log_metric(name="model_loss", metric=metric, step=step)

        # create weights clear the model now the weights are processed
        weights = self.create_weights(
            run=run,
            model=model,
            metric=metric,
            epoch=epoch,
            io=TorchWeightsFile(),
            asset_manager=asset_manager,
        )
        asset_manager.write([weights])
        asset_manager.reset([weights, dataset, training_model])
        if len(dataset) > 0:
            raise RMTCException(f"Dataset not empty {dataset}")

        # we don't make a model so don't return it
        return (metric, [None, weights] + checkpoints)

    def _update(
        self,
        run,
        model,
        metric,
        epoch,
        tracker,
        optimizer_name,
        optimizer,
        asset_manager,
    ):
        """Runs after each training epoch."""
        if self.do_checkpoint(epoch):

            # create checkpoint
            checkpoint = self.create_checkpoint(
                run=run,
                model=model,
                epoch=epoch,
                metric=metric,
                io=TorchCheckpointFile(),
                asset_manager=asset_manager,
            )
            checkpoint.torch_optimizer = (optimizer_name,)
            checkpoint.torch_optimizer_state = (optimizer.state_dict(),)

            # create URI and write
            asset_manager.write([checkpoint])
            asset_manager.reset([checkpoint])
            tracker.log_checkpoint(checkpoint, step=epoch)

            return checkpoint

        return None
