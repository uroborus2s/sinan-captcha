"""Runner adapters that bridge the controller to existing CLI/service behavior."""

from core.auto_train.runners import dataset, evaluate, test, train
from core.auto_train.runners.common import RunnerExecutionError

__all__ = ["RunnerExecutionError", "dataset", "evaluate", "test", "train"]
