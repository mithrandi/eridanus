class CommandError(Exception):
    pass


class CommandNotFound(CommandError):
    pass


class InvalidEntry(CommandError):
    pass


class ParameterError(CommandError):
    pass
