# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import random
from itertools import islice, chain, repeat

import torch
from torch import nn
from torch import optim
import numpy as np

from rmtc_core.artifacts.torch.models import Torch
from rmtc_core.io.torch.weights import TorchWeightsFile
from rmtc_core.io.torch.checkpoints import TorchCheckpointFile

from rmtc.train import Trainer
from rmtc.system import RMTCException, Context
from rmtc.containers import ITable
from rmtc.artifacts import ModelType

MAX_SIGNED_32_INT = (1 << 31) - 1


def batched(dataset, batch_size, repeat_data=0):
    """
    Batch dataset into tuples of length batch_size.
    The last batch may be shorter.

    Args:
        dataset (rmtc.Dataset): RMTC training data
        batch_size (int): Number of data samples to batch together
        repeat_data (int): Number of times to consecutively repeat samples
    """
    if batch_size < 1:
        raise ValueError("Batch size must be at least one")
    it = iter(dataset)
    if repeat_data:
        it = chain.from_iterable(repeat(entry, repeat_data) for entry in it)

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
        repeat_data=0,
        accumulation_steps=1,
        epochs=5,
        optimizer="adam",
        criterion="bce",
        context=Context.GPU,
        preprocess=None,
        random_seed=None,
    ):  # pylint: disable=unused-argument
        """Initialize TorchRegression trainer with hyperparameters."""
        super(TorchRegression, self).__init__(
            checkpoint_interval=checkpoint_interval,
            epochs=epochs,
            batch_size=batch_size,
            context=context,
            preprocess=preprocess,
        )
        self.add_property("lr", float, lr)
        self.add_property("optimizer", str, optimizer)
        self.add_property("criterion", str, criterion)
        self.add_property("accumulation_steps", int, accumulation_steps)
        self.add_property("repeat_data", int, repeat_data)

        if random_seed is None:
            random_seed = random.randint(1, MAX_SIGNED_32_INT)
        self.add_property("random_seed", int, random_seed)

        self._checkpoints = []
        self.finish = False

    def __call__(
        self,
        tracker,
        run,
        asset_manager,
        env_manager,
        collector=None,
    ):
        """Execute the complete training process with logging and checkpointing.

        Performs end-to-end training including data loading, model preparation,
        optimizer setup, training loop execution, checkpointing, and final
        artifact creation. The method handles all aspects of the training
        lifecycle with comprehensive error handling and resource management.
        """
        self._collector = collector

        if not torch.cuda.is_available():
            raise RMTCException(
                f"CUDA is not available. Trainer {self} requires a GPU."
            )

        training_device = "cuda"
        if self.context == Context.CPU:
            training_device = "cpu"

        # load data
        dataset = run.dataset
        asset_manager.read([dataset])

        # train this model
        # TODO: model should really be const, taking a duplicate
        # however creating checkpoints and weights off the duplicate
        # causes these artifacts to link to the duplcate, not the original
        model = run.model
        if not isinstance(model, Torch):
            raise RMTCException(
                f"Model to train: {model}, not an instance of a torch model"
            )
        training_model = model.duplicate()
        asset_manager.read([training_model])
        torch_model = training_model.torch_model
        torch_model = torch_model.to(training_device)

        # setup optimiser
        # TODO : need some way to parameterise
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
        # TODO : choose default according to the model, maybe a regressor/classifier etc.
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
        self._checkpoints = []
        repetitions = 1 + self.repeat_data
        total_samples = len(dataset) * repetitions
        num_batches = (total_samples + self.batch_size - 1) // self.batch_size
        mean_epoch_loss = np.zeros(num_batches)
        mean_loss = []
        step = 0
        scaler = torch.cuda.amp.GradScaler()

        tracker.log_info(f"Starting Trainer {self.name}")
        tracker.log_info(f"- Context: {self.context}")
        tracker.log_info(f"- Epochs: {self.epochs}")
        tracker.log_info(f"- Dataset: {dataset.uri} ({len(dataset)})")
        tracker.log_info(f"- Model: {model.uri}")
        tracker.log_info(f"- Learning Rate: {self.lr}")
        tracker.log_info(f"- Criterion: {self.criterion}")
        tracker.log_info(f"- Optimizer: {self.optimizer}")
        tracker.log_info(f"- Batch Size: {self.batch_size}")
        tracker.log_info(f"- Repeat Data: {self.repeat_data}")
        tracker.log_info(f"- Gradient Accumulation Steps: {self.accumulation_steps}")
        tracker.log_info(f"- Random Seed: {self.random_seed}")

        # validate the dataset before starting
        if not dataset.is_valid():
            raise RMTCException(f"Invalid entries in dataset {dataset}")
        if not isinstance(dataset, ITable):
            raise RMTCException(
                f"Invalid dataset type {dataset}, not an instance of ITable"
            )

        # run epochs
        torch.cuda.empty_cache()
        torch_model.set_training(True)
        torch_model.train()
        optimizer.zero_grad()

        for epoch in range(self.epochs):

            # Requst made to end training run
            if self.finish:
                break

            # TODO: single batch right now
            running_loss = 0.0
            iteration = 0
            for data_rows in batched(dataset, self.batch_size, repeat_data=repetitions):

                rows = []
                for row in data_rows:
                    # skip invalid rows
                    if len(row) < 2:
                        tracker.log_warning(f"Invalid row: {row} / {iteration}")
                        continue
                    rows.append(row)

                # End training run
                if self.finish:
                    break

                # get assets
                assets_src = []
                assets_dst = []
                for row in rows:
                    assets_src.append(row[0])
                    assets_dst.append(row[1])

                # TODO : move this somewhere more central, in asset manager just stops datasets
                # from being read at all
                try:
                    for asset_src in assets_src:
                        if not asset_src.is_valid():
                            asset_manager.read(assets_src)
                    for asset_dst in assets_dst:
                        if not asset_dst.is_valid():
                            asset_manager.read(assets_dst)
                except RMTCException as e:
                    src_assets = "\n".join([a.uri for a in assets_src])
                    dst_assets = "\n".join([a.uri for a in assets_dst])
                    tracker.log_warning(
                        f"Failed to read assets {e}, src: {src_assets} dst: {dst_assets}"
                    )
                    continue

                # run any trainer specific processes

                # Use deterministic random seeds for augmentation
                random_seeds = []
                random.seed(self.random_seed)
                for _ in range(len(assets_src)):
                    random_seeds.append(random.randint(1, MAX_SIGNED_32_INT))

                if self.preprocess is not None:
                    for i, asset_src in enumerate(assets_src):
                        # TODO: Handle random seed in the processes
                        random_seed = random_seeds[i]

                        # Preprocess src
                        random.seed(random_seed)
                        asset_src.process(self.preprocess)

                        # Preprocess dst
                        asset_dst = assets_dst[i]
                        random.seed(random_seed)
                        asset_dst.process(self.preprocess)

                # convert asset to tensors - note must be flattened to a single list element
                input_tensors = model.assets_to_input_tensors(assets_src)[0]
                output_tensors = model.assets_to_output_tensors(assets_dst)[0]

                # convert to torch and device
                torch_input_tensor = torch.from_numpy(input_tensors).to(training_device)
                torch_output_tensor = torch.from_numpy(output_tensors).to(
                    training_device
                )

                # run prediction
                with torch.cuda.amp.autocast():
                    torch_predicted_tensor = torch_model(torch_input_tensor)
                    loss = criterion(torch_predicted_tensor, torch_output_tensor)

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
                mean_epoch_loss[iteration] = loss
                step += 1
                tracker.log_metric(name="training_loss", step=step, metric=loss)
                iteration += 1

                # unload the batch
                for asset_src in assets_src:
                    asset_src.reset()
                for asset_dst in assets_dst:
                    asset_dst.reset()
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
                return (model, None, 1.0, [])

            # update model metrics
            mean_loss.append(mean_epoch_loss.mean())
            metric = mean_loss[-1]
            torch.cuda.empty_cache()

            tracker.log_info(f"Loss: {metric}", step=epoch)

            self.update(
                run,
                training_model,
                model,
                metric,
                epoch + 1,
                tracker,
                optimizer,
                asset_manager,
            )

        tracker.log_hyperparameters(
            params={
                "lr": self.lr,
                "epochs": self.epochs,
                "batch_size": self.batch_size,
                "repeat data": self.repeat_data,
                "accumulation_steps": self.accumulation_steps,
                "optimizer": self.optimizer,
            },
            metric=metric,
        )
        tracker.log_metric(name="model_loss", metric=metric, step=step)

        # write out the weights
        weights = training_model.create_weights(io=TorchWeightsFile())
        weights.model = model  # HACK: trained model and source model are different
        weights.metric = metric
        weights.model = model
        weights.uri = run.create_uri("weights", "weights.pt")
        asset_manager.write([weights])

        # clear the model now the weights are processed
        training_model.reset()

        return (model, weights, metric, self._checkpoints)

    def update(
        self,
        run,
        training_model,
        model,
        metric,
        epoch,
        tracker,
        optimizer,
        asset_manager,
    ):
        """Runs after each training epoch."""
        if self.do_checkpoint(epoch):
            # Generate a checkpoint
            checkpoint = training_model.create_checkpoint(io=TorchCheckpointFile())
            checkpoint.model = (
                model  # HACK : model we train and model we track are different
            )
            checkpoint.epoch = epoch
            checkpoint.optimizer = self.optimizer
            checkpoint.torch_optimizer = optimizer.state_dict()
            checkpoint.uri = run.create_uri(
                "checkpoints", f"checkpoint_epoch{epoch}.pt"
            )
            asset_manager.write([checkpoint])
            self._checkpoints.append(checkpoint)
            tracker.log_checkpoint(checkpoint, step=epoch)
            torch.cuda.empty_cache()

        if self._collector is not None and callable(self._collector):
            self._collector(
                run=run,
                model=model,
                metric=metric,
                epoch=epoch,
                optimizer=optimizer,
                total_epochs=self.epochs,
            )
