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


class SOAPFault(Exception):
    """
    A SOAP fault received in response to a SOAP request.
    """
    def __init__(self, faultcode, faultstring, faultactor, detail):
        Exception.__init__(self, faultcode, faultstring, faultactor, detail)
        self.faultcode = faultcode
        self.faultstring = faultstring
        self.faultactor = faultactor
        self.detail = detail

    def __str__(self):
        return '%s :: %s\n%s\n%s' % (self.faultactor,
                                     self.faultcode,
                                     self.faultstring,
                                     self.detail)


class InvalidSOAPFault(ValueError):
    """
    A SOAP fault could not be parsed successfully.
    """
    def __init__(self, detail):
        ValueError.__init__(self, detail)
        self.detail = detail


class MissingAPIKey(ValueError):
    """
    The key for the requested API is missing.
    """
