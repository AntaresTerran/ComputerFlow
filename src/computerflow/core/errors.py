class ComputerFlowError(Exception):
    """An expected, user-visible failure without private payloads."""


class Cancelled(ComputerFlowError):
    pass


class BackendError(ComputerFlowError):
    pass


class PlatformError(ComputerFlowError):
    pass
