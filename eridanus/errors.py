class PluginError(Exception):
    """
    General plugin-related error.
    """


class PluginNotFound(PluginError):
    """
    The specified plugin does not exist.
    """


class PluginNotInstalled(PluginError):
    """
    The specified plugin exists but is not installed.
    """


class UsageError(Exception):
    """
    Attempting to use a command resulted in an error.

    Usually this indicates a malformed command or missing parameters.
    """


class InvalidMaskError(ValueError):
    """
    Caused by a malformed user mask.
    """


class AuthenticationError(ValueError):
    """
    Authentication could not complete successfully.
    """
