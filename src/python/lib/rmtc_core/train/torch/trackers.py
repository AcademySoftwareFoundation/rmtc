# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project


from torch.utils.tensorboard import SummaryWriter

from rmtc.train import Tracker


class TensorBoard(Tracker):
    """
    TensorBoard experiment tracker for ML training visualization and logging.

    The TensorBoard class provides integration with PyTorch's TensorBoard
    SummaryWriter to enable comprehensive experiment tracking, visualization,
    and logging of training metrics, hyperparameters, checkpoints, and images.

    This tracker automatically organizes logs by solution and run names,
    creating a hierarchical directory structure for easy navigation and
    comparison of experiments. It supports all major TensorBoard logging
    capabilities including scalars, hyperparameters, text, and images.
    """

    def __init__(self, uri=None, log=None):
        """Initialize TensorBoard tracker with storage URI."""
        super(TensorBoard, self).__init__(uri=uri)
        self.logdir = None
        self._writer = None
        self._log = log

    def start(self, run):
        """Start tracking for a training run with organized log directory."""
        self.finish()
        path = f"{self.uri.path}/{run.name}"
        self._writer = SummaryWriter(log_dir=path)

    def finish(self):
        """Finish tracking and close the TensorBoard writer."""
        if self._writer is not None:
            self._writer.flush()
            self._writer.close()
            self._writer = None

    def log_checkpoint(self, checkpoint, step=None):
        """Log checkpoint information as text entry."""
        if step is None:
            step = 0
        self._writer.add_text("checkpoint", str(checkpoint.uri), step)

    def log_metric(self, name, metric=0.0, step=None):
        """Log scalar metric value."""
        if step is None:
            step = 0
        self._writer.add_scalar(name, metric, step)

    def log_hyperparameters(self, params, metric=0.0):
        """Log hyperparameters with associated metric."""
        self._writer.add_hparams(params, {"metric": metric})

    def log_image(self, name, image, step=None):
        """Log image data for visualization."""
        if step is None:
            step = 0
        self._writer.add_image(image, name, step)

    def log_debug(self, message, step=None):
        if self._log is not None:
            if step is not None:
                self._log.debug(f"{step}: {message}")
            else:
                self._log.debug(f"{message}")

    def log_info(self, message, step=None):
        if self._log is not None:
            if step is not None:
                self._log.info(f"{step}: {message}")
            else:
                self._log.info(f"{message}")

    def log_warning(self, message, step=None):
        if self._log is not None:
            if step is not None:
                self._log.warning(f"{step}: {message}")
            else:
                self._log.warning(f"{message}")

    def log_error(self, message, step=None):
        if self._log is not None:
            if step is not None:
                self._log.error(f"{step}: {message}")
            else:
                self._log.error(f"{message}")
