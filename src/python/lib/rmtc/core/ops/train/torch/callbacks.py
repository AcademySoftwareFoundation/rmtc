# # SPDX-License-Identifier: Apache-2.0
# # Copyright Contributors to the RMTC Project

# from rmtc.core.ops.io.torch.checkpoints import TorchCheckpointFile
# from rmtc.ops.scheduling import Status
# from rmtc.system import Version


# class TrainerCallbacks:
#     """Optional callbacks during training"""

#     def __init__(self, rmtc_system=None):
#         self._system = rmtc_system
#         self._model = None
#         self._metric = None
#         self._epoch = None
#         self._optimizer = None
#         self._run = None

#     def collect_epoch_data(
#         self,
#         run=None,
#         model=None,
#         metric=None,
#         epoch=None,
#         _total_epochs=None,
#         optimizer=None,
#         **_kwargs,
#     ):
#         """
#         Collect the model, metric, and information after each training epoch.
#         """
#         self._model = model
#         self._metric = metric
#         self._epoch = epoch
#         self._optimizer = optimizer
#         self._run = run

#         # Sync the run, so we can check its status
#         self._run.mark_for_sync()
#         if self._system:
#             self._system.pull([self._run])

#         if self._run.status == Status.STOPPED:
#             # Save a checkpoint and end the training run
#             self._system.tracker.log_info("User terminated training run")
#             self._save_checkpoint()

#             # Tell the trainer to finish
#             self._run.trainer.finish = True

#         # Update the metric and epoch
#         self._run.metric = metric
#         self._run.epoch = epoch
#         if self._system:
#             self._system.push([self._run])

#     def _save_checkpoint(self):
#         """Save a model checkpoint for the most recently completed training epoch."""
#         # if not all(
#         #     var is not None
#         #     for var in [
#         #         self._model,
#         #         self._metric,
#         #         self._epoch,
#         #         self._optimizer,
#         #         self._run,
#         #         self._system,
#         #     ]
#         # ):
#         #     self._system.tracker.log_info("No checkpoint available")
#         #     return

#         # # Ensure model is up to date
#         # self._system.pull([self._model])
#         # self._model.read(self._system.ops.asset_manager)

#         # checkpoint = self._model.create_checkpoint(parent=self._run)
#         # checkpoint.io = TorchCheckpointFile()
#         # checkpoint.epoch = self._epoch
#         # checkpoint.optimizer = self._optimizer
#         # checkpoint.torch_optimizer = self._optimizer.state_dict()
#         # checkpoint.version = Version(major=self._run.version.major, minor=self._epoch)
#         # checkpoint.name = f"checkpoint_{checkpoint.version}"
#         # checkpoint.parent = self._run
#         # checkpoint.model = self._model_instance.ancestors[
#         #     0
#         # ]  # instance have one ancestor

#         # # create URI
#         # path = self._run.uri.path
#         # path /= "checkpoints"
#         # checkpoint.uri = self._system.ops.asset_manager.create_uri(
#         #     path=path,
#         #     name=checkpoint.io.create_name(checkpoint),
#         # )

#         # # write out
#         # self._system.ops.asset_manager.write([checkpoint])
#         # self._system.push([checkpoint])
#         # self._system.tracker.log_checkpoint(checkpoint, step=self._epoch)
#         # self._system.tracker.log_info(
#         #     f"Checkpoint saved after epoch {self._epoch}, loss: {self._metric}"
#         # )
