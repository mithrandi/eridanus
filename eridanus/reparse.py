"""
Parse a regular expression into it's parts.
"""
import re, string

from pymeta.grammar import OMeta
from pymeta.runtime import ParseError

from eridanus import errors


regexGrammar = """
regex        ::= 's' '/' <expn>:a '/' <expn>:b '/' <flag>*:c <end> => (''.join(a), ''.join(b), c)

flag         ::= 'i' | 'g'

printable    ::= :x ?(x in string.printable.replace('/', '')) => x
escapedSlash ::= '\\\\' '/'
expn         ::= (<escapedSlash> | <printable>)+
"""

class RegexGrammar(OMeta.makeGrammar(regexGrammar, globals())):
    pass


class Substitution(object):
    def __init__(self, pattern, repl, globalFlag):
        self.pattern = pattern
        self.repl = repl
        self.globalFlag = globalFlag

    def sub(self, s):
        return self.pattern.sub(self.repl, s)


_regexFlags = {
    u'i': re.IGNORECASE,
    }

def parseRegex(regex):
    """
    Convert a regular expression string into something useful.

    The regular expression should be of the form::

        s/find/replace/flags

        e.g. s/foo/bar/ig

    @rtype: C{(callable, boolean)}
    @return: A callable that returns a transformed string and takes 1
        parameter, the input string to perform the regular expression on, and a
        boolean indicating whether or not the global (C{g}) flag was specified
        or not
    """
    g = RegexGrammar(regex)
    try:
        find, repl, _flags = g.apply('regex')
    except ParseError:
        raise errors.MalformedRegex(u'"%s" is not a well-formed regular expression' % (regex,))

    globalFlag = False
    flags = 0
    for flag in _flags:
        f = _regexFlags.get(flag)
        if f is not None:
            flags |= f
        elif flag == 'g':
            globalFlag = True

    pattern = re.compile(find, flags)
    return Substitution(pattern, repl, globalFlag)
