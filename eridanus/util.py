import re, math, fnmatch, itertools, warnings, htmlentitydefs

from twisted.internet import reactor, task, error as ineterror
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web import client, http, error as weberror
from twisted.web.http_headers import Headers
from twisted.python import log

import treq

from nevow.url import URL
from nevow.rend import Page, Fragment

from xmantissa import website
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

    @type maxDelay: C{float}
    @cvar maxDelay: Maximum delay, in seconds, between retry attempts

    @type initialDelay: C{float}
    @cvar initialDelay: The delay before the first retry attempt

    @type factor: C{float}
    @cvar factor: The factor to increase the delay by after each attempt

    @type retryableHTTPCodes: C{list}
    @cvar retryableHTTPCodes: HTTP error codes that suggest the error is
        intermittent and that a retry should be attempted

    @type defaultTimeout: C{float}
    @cvar defaultTimeout: Default fetch timeout value
    """
    maxDelay = 3600
    initialDelay = 1.0
    factor = 1.6180339887498948

    retryableHTTPCodes = [408, 500, 502, 503, 504]

    defaultTimeout = 300.0

    def __init__(self, url, tries=10, timeout=defaultTimeout, *a, **kw):
        """
        Prepare the download information.

        Any additional positional or keyword arguments are passed on to
        C{twisted.web.client.HTTPPageGetter}.

        @type url: C{nevow.url.URL} or C{unicode} or C{str}
        @param url: The HTTP URL to attempt to download

        @type tries: C{int}
        @param tries: The maximum number of retry attempts before giving up

        @type timeout: C{float}
        @param timeout: Timeout value, in seconds, for the page fetch;
            defaults to L{defaultTimeout}
        """
        if isinstance(url, unicode):
            url = url.encode('utf-8')
        if isinstance(url, str):
            url = URL.fromString(url)

        self.url = url.anchor(None)
        self.args = a
        self.kwargs = kw
        self.delay = self.initialDelay
        self.tries = tries
        self.timeout = timeout

    def __repr__(self):
        return '<%s %s>' % (type(self).__name__, self.url)

    @inlineCallbacks
    def go(self):
        """
        Attempt to download L{self.url}.
        """
        headers = self.kwargs.pop('headers', Headers())
        headers.setRawHeaders('user-agent', ['Eridanus IRC bot'])
        response = yield treq.get(
            str(self.url), timeout=self.timeout, headers=headers,
            *self.args, **self.kwargs)
        data = yield response.content()
        if response.code // 100 == 2:
            returnValue((data, response.headers))
        else:
            raise weberror.Error(response.code, response.phrase, data)


def encode(s):
    return s.encode(const.ENCODING, 'replace')


def decode(s):
    return s.decode(const.ENCODING, 'replace')


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

    years = days // 365
    days -= years * 365

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
        if years:
            yield makeText(u'%d years', years)
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
        parts = [u'0 seconds']

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
    index = min(int(math.log(size, 1024)), len(sizePrefixes) - 1)
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


def collate(it):
    """
    Unpack C{(key, value)} pairs from C{it} and collate overlapping keys.

    For example::

        >>> collate([(1, 'foo'), (2, 'bar'), (1, 'baz')])
        {1: ['foo', 'baz'], 2: ['bar']}

    @type it: C{iterable}

    @rtype: C{dict}
    """
    d = {}
    for key, value in it:
        d.setdefault(key, []).append(value)

    return d


def getSiteStore(store):
    """
    Given C{store} find the site store.
    """
    siteStore = store
    while siteStore.parent:
        siteStore = siteStore.parent

    return siteStore


def getAPIKey(store, apiName, **kw):
    """
    Get the API key for C{apiName}.

    @raise errors.MissingAPIKey: If there is no key stored for C{apiName}

    @rtype: C{unicode}
    @return: The API key for C{apiName}
    """
    hasDefault = 'default' in kw
    siteStore = getSiteStore(store)
    key = website.APIKey.getKeyForAPI(siteStore, apiName)
    if key is None:
        if hasDefault:
            return kw['default']
        else:
            raise errors.MissingAPIKey(u'No API key available for "%s"' % (apiName,))

    return key.apiKey


def setAPIKey(store, apiName, key):
    """
    Store an API key for C{apiName}.
    """
    siteStore = getSiteStore(store)
    return website.APIKey.setKeyForAPI(siteStore, apiName, key)


_entityPattern = re.compile(ur'&#?\w+;')
htmlentitydefs.name2codepoint['apos'] = ord(u"'")

def unescapeEntities(text):
    """
    Replace HTML or XML character references and entities in a string.
    """
    def fixup(m):
        text = m.group(0)
        if text[:2] == '&#':
            try:
                if text[:3] == '&#x':
                    return unichr(int(text[3:-1], 16))
                else:
                    return unichr(int(text[2:-1]))
            except ValueError:
                pass
        else:
            try:
                text = unichr(htmlentitydefs.name2codepoint[text[1:-1]])
            except KeyError:
                pass
        return text

    return _entityPattern.sub(fixup, text)
