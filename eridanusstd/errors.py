class InvalidEntry(ValueError):
    """
    An invalid LinkDB entry was specified.
    """


class InvalidDictionary(ValueError):
    """
    An invalid dictionary database was specified.
    """


class NoDefinitions(ValueError):
    """
    No dictionary definitions are available for the specified word.
    """


class InvalidLanguage(ValueError):
    """
    An invalid dictionary language was specified.
    """


class NoMoreItems(RuntimeError):
    """
    A deferred-iterator has no more items.
    """
