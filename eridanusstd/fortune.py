import os

from twisted.internet.utils import getProcessOutput
from twisted.python.procutils import which

from eridanusstd import errors


fortuneBinary = (which('fortune') or [None])[0]


def parseOutput(out):
    """
    Parse fortune output.

    @rtype: C{iterable} of C{(unicode, list)}
    @return: An iterable of C{(dbName, fortuneLines)} pairs, C{fortuneLines}
        are not newline terminated
    """
    out = out.decode('utf-8').splitlines()

    while out:
        if out[0].startswith('(') and out[0].endswith(')'):
            dbName = out.pop(0)[1:-1] # Remove ()s from DB name
            dbName = os.path.split(dbName)[-1]
        out.pop(0) # Pop the '%'

        quote = []
        while True:
            # XXX: If multiple lines of output are required, we probably
            # shouldn't be stripping these.
            line = out.pop(0).strip()
            if len(out) == 0:
                quote.append(line)
                break
            elif line == u'%' :
                break
            quote.append(line)

        yield dbName, quote


def fortune(db=None, match=None, short=None):
    """
    Retrieve a fortune.

    @type db: C{unicode} or C{None}
    @param db: The fortune database to use or C{None} to use any available
        databases

    @type match: C{unicode} or C{None}
    @param match: Fortune text to match or C{None} to retrieve a random
        fortune

    @type short: C{bool} or C{None}
    @param short: Flag indicating whether only short fortunes should be
        considered or C{None} for all fortunes

    @raise errors.MissingBinary: If the fortune command could not be located
    @raise errors.NoFortunes: No fortunes were found for the given criteria

    @return: C{Deferred} firing with the results of L{parseOutput} 
    """
    if fortuneBinary is None:
        raise errors.MissingBinary(u'No binary for fortune could be found')

    # XXX: -a should be configurable along with -o
    args = ['-a', '-c']
    if match is not None:
        args.append('-i') # Mmm.  Might be nice to make this configurable.
        args.append('-m')
        args.append(match.encode('utf-8'))
    if short:
        args.append('-s')
    if db:
        args.append(db.encode('utf-8'))

    def gotOutput(out):
        if not out or out.strip() == 'No fortunes found':
            raise errors.NoFortunes(u'No fortunes found')
        return parseOutput(out)

    return getProcessOutput(fortuneBinary, args, errortoo=True
        ).addCallback(gotOutput)
