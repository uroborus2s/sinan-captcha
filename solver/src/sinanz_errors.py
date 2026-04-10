"""Error types exposed by the standalone solver package."""


class SolverError(RuntimeError):
    """Base error for standalone solver failures."""


class SolverInputError(SolverError):
    """Raised when caller-provided inputs are invalid."""


class SolverAssetError(SolverError):
    """Raised when embedded model assets are missing or incompatible."""


class SolverRuntimeError(SolverError):
    """Raised when the solver runtime cannot complete inference."""
