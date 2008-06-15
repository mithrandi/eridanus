import re, math, html5lib, fnmatch, itertools, warnings

try:
    from xml.etree import ElementTree
except ImportError:
    from elementtree import ElementTree

from twisted.internet import reactor, task, error as ineterror
from twisted.web import client, http, error as weberror
from twisted.python import log

from nevow.url import URL
from nevow.rend import Page, Fragment

from xmantissa.webtheme import _ThemedMixin, SiteTemplateResolver

from eridanus import const, errors


# XXX: do we need this crap? all of it?
class _PublicThemedMixin(_ThemedMixin):
    def getDocFactory(self, fragmentName, default=None):
        resolver = SiteTemplateResolver(self.store)
        return resolver.getDocFactory(fragmentName, default)


class ThemedPage(_PublicThemedMixin, Page):
    fragmentName = 'page-no-fragment-name-specified'

    def renderHTTP(self, ctx):
        if self.docFactory is None:
            self.docFactory = self.getDocFactory(self.fragmentName)
        return super(ThemedPage, self).renderHTTP(ctx)


class ThemedFragment(_PublicThemedMixin, Fragment):
    fragmentName = 'fragment-no-fragment-name-specified'

    def __init__(self, store, **kw):
        self.store = store
        super(ThemedFragment, self).__init__(**kw)


class PerseverantDownloader(object):
    """
    Perseverantly attempt to download a URL.

    Each retry attempt is delayed by L{factor} up to a maximum of L{maxDelay},
    starting at L{initialDelay}.

    @type url: C{nevow.url.URL}
    @ivar url: The HTTP URL to attempt to download

    @type maxDelay: C{numeric}
    @cvar maxDelay: Maximum delay, in seconds, between retry attempts

    @type initialDelay: C{numeric}
    @cvar initialDelay: The delay before the first retry attempt

    @type factor: C{numeric}
    @cvar factor: The factor to increase the delay by after each attempt

    @type retryableHTTPCodes: C{list}
    @cvar retryableHTTPCodes: HTTP error codes that suggest the error is
        intermittent and that a retry should be attempted
    """
    maxDelay = 3600
    initialDelay = 1.0
    factor = 1.6180339887498948

    retryableHTTPCodes = [408, 500, 502, 503, 504]

    def __init__(self, url, tries=10, *a, **kw):
        """
        Prepare the download information.

        Any additional positional or keyword arguments are passed on to
        C{twisted.web.client.HTTPPageGetter}.

        @type url: C{nevow.url.URL}
        @param url: The HTTP URL to attempt to download

        @type tries: C{int}
        @param tries: The maximum number of retry attempts before giving up
        """
        self.url = URL(url)
        self.url.fragment = None
        self.args = a
        self.kwargs = kw
        self.delay = self.initialDelay
        self.tries = tries

    def __repr__(self):
        return '<%s %s>' % (type(self).__name__, self.url)

    def go(self):
        """
        Attempt to download L{self.url}.
        """
        d, f = getPage(str(self.url), *self.args, **self.kwargs)
        return d.addErrback(self.retryWeb
               ).addCallback(lambda data: (data, f.response_headers))

    def retryWeb(self, f):
        """
        Retry failed downloads in the case of "web errors."

        Only errors that are web related are considered for a retry attempt
        and then only when the HTTP status code is one of those in
        L{self.retryableHTTPCodes}.

        Other errors are not trapped.
        """
        f.trap((weberror.Error, ineterror.ConnectionDone))
        err = f.value
        if int(err.status) in self.retryableHTTPCodes:
            return self.retry(f)

        return f

    def retry(self, f):
        """
        The retry machinery.

        If C{self.tries} is greater than zero, a retry is attempted for
        C{self.delay} seconds in the future.
        """
        self.tries -= 1
        log.msg('PerseverantDownloader is retrying, %d attempts left.' % (self.tries,))
        log.err(f)
        self.delay = min(self.delay * self.factor, self.maxDelay)
        if self.tries == 0:
            return f

        return task.deferLater(reactor, self.delay, self.go)


def encode(s):
    return s.encode(const.ENCODING, 'replace')


def decode(s):
    return s.decode(const.ENCODING, 'replace')


def handle206(f):
    """
    Return any partial content when HTTP 206 is returned.
    """
    f.trap(weberror.Error)
    err = f.value
    try:
        if int(err.status) == http.PARTIAL_CONTENT:
            return err.response
    except ValueError:
        pass

    return f


# XXX: a copy from twisted.web.client because their getPage sucks badly.
def getPage(url, contextFactory=None, *args, **kwargs):
    scheme, host, port, path = client._parse(url)
    factory = client.HTTPClientFactory(url, *args, **kwargs)
    if scheme == 'https':
        from twisted.internet import ssl
        if contextFactory is None:
            contextFactory = ssl.ClientContextFactory()
        reactor.connectSSL(host, port, factory, contextFactory)
    else:
        reactor.connectTCP(host, port, factory)
    return factory.deferred.addErrback(handle206), factory


# XXX: move this into the linkdb stuff
_whitespace = re.compile(ur'\s+')
def extractTitle(data):
    def sanitizeTitle(title):
        return _whitespace.sub(u' ', title.strip())

    if data:
        try:
            parser = html5lib.HTMLParser(tree=html5lib.treebuilders.getTreeBuilder('etree', ElementTree))
            tree = ElementTree.ElementTree(parser.parse(data))
            titleElem = tree.find('//title')
            if titleElem is not None and titleElem.text is not None:
                text = unicode(titleElem.text)
                return sanitizeTitle(text)
        except:
            log.msg('Extracting title failed:')
            log.err()

    return None


def truncate(s, limit):
    """
    Shorten C{s} to C{limit} characters and append an ellipsis.
    """
    if len(s) - 3 < limit:
        return s

    return s[:limit] + '...'


def humanReadableTimeDelta(delta):
    """
    Convert a C{datetime.timedelta} instance into a human readable string.
    """
    days = delta.days

    seconds = delta.seconds

    hours = seconds // 3600
    seconds -= hours * 3600

    minutes = seconds // 60
    seconds -= minutes * 60

    def makeText(s, value):
        if value == 1:
            s = s[:-1]
        return s % (value,)

    def getParts():
        if days:
            yield makeText(u'%d days', days)
        if hours:
            yield makeText(u'%d hours', hours)
        if minutes:
            yield makeText(u'%d minutes', minutes)
        if seconds:
            yield makeText(u'%d seconds', seconds)

    parts = list(getParts())
    if not parts:
        parts = [u'never']

    return u' '.join(parts)


sizePrefixes = (u'bytes', u'KB', u'MB', u'GB', u'TB', u'PB', u'EB', u'ZB', u'YB')

def humanReadableFileSize(size):
    """
    Convert a size in bytes to a human readable string.

    @param size: The size, in bytes, to convert
    @type size: C{int} or C{float}

    @returns: A human readable string
    @rtype: C{unicode}
    """
    index = int(math.log(size, 1024))
    size = size / (1024.0 ** index)
    prefix = sizePrefixes[index]
    if index == 0:
        size = int(size)
        format = u'%s %s'
    else:
        format = u'%0.2f %s'
    return format % (size, prefix)


def hostMatches(host, mask):
    """
    Determine whether a given host matches the specified mask.

    @param host: Something of the form C{nick!user@host}
    @type host: C{str} or C{unicode}

    @param mask: A wildcard-enabled mask to attempt to match C{host} with
    @type mask: C{str} or C{unicode}

    @returns: Whether C{mask} matched C{host}
    @rtype: C{bool}
    """
    return re.match(fnmatch.translate(mask), host) is not None


def padIterable(iterable, length, padding=None):
    """
    Ensure that C{iterable} is at least C{length} items long.

    @param padding: The object to pad C{iterable} with in the case where it is
        less than C{length}

    @rtype: C{iterable}
    """
    return itertools.islice(itertools.chain(iterable, itertools.repeat(padding)), length)


def normalizeMask(mask):
    """
    Create the canonical IRC mask for the given input.

    For example::

        joe => joe!*@*

        joe!black => joe!black@*

        joe!black@hell => joe!black@hell

    It is an error to specify an C{@} without or before a C{!}.

    @raise errors.InvalidMaskError: If the mask is malformed
    """
    def splitMask():
        if not mask:
            return None

        nick = mask
        user = host = '*'
        if '!' in mask:
            atPos = mask.find('@')
            if atPos > 0 and atPos < mask.find('!'):
                return None

            nick, user = padIterable(mask.split('!', 1), 2, padding='*')
            user, host = padIterable(user.split('@', 1), 2, padding='*')
        elif '@' in mask:
            return None

        return nick, user, host

    parts = splitMask()
    if parts is None:
        raise errors.InvalidMaskError(u'"%s" is not a valid complete or partial mask' % (mask,))

    return '%s!%s@%s' % parts


def tabulate(headers, data, joiner='  '):
    """
    Tabulate data, attaching the specified headers.

    @param headers: The table headers
    @type headers: C{iterable}

    @param data: The table data to be split into columns under each respective
                 heading
    @type data: C{iterable} of C{iterable}s

    @param joiner: The string used to join columns together
    @type joiner: C{str}

    @returns: The tabulated data in rows
    @rtype: C{iterable} of C{str}
    """
    data = [headers] + list(data)
    columnWidths = [max(map(len, c)) for c in zip(*data)]

    for row in data:
        yield joiner.join(value.ljust(columnWidths[i]) for i, value in enumerate(row)).rstrip()


def deprecation(msg):
    warnings.warn(msg, DeprecationWarning, stacklevel=2)
