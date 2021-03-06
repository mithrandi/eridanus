import lxml.objectify
from xml.sax.saxutils import unescape

from twisted.internet.defer import succeed
from twisted.python.failure import Failure
from twisted.web import error as weberror

from nevow.url import URL

from eridanus import util
from eridanusstd import errors, timeutil



TWITTER_API = URL.fromString('http://api.twitter.com/1/')
TWITTER_SEARCH = URL.fromString('http://search.twitter.com/')



def handleError(f):
    """
    Transform a Twitter error message into a C{Failure} wrapping
    L{eridanusstd.errors.RequestError}.
    """
    f.trap(weberror.Error)
    try:
        root = lxml.objectify.fromstring(f.value.response)
        return Failure(
            errors.RequestError(root.request, root.error))
    except lxml.etree.XMLSyntaxError:
        return f



_no_arg = object()

def query(method, arg=_no_arg, **params):
    """
    Query the Twitter API and parse the response.

    @param method: Twitter API method name.

    @param arg: Optional additional method "argument". A method argument is
        added to the API URL path and not as a query parameter, since some
        methods behave more naturally this way (C{'statuses/show'} is one such
        example.)

    @param **params: Additional keyword arguments are passed on as query
        parameters.

    @rtype: C{Deferred} => C{lxml.objectify.ObjectifiedElement}
    """
    cat, name = method.split('/')
    names = [name]
    if arg is not _no_arg:
        names.append(arg)
    names[-1] += '.xml'

    url = TWITTER_API.child(cat)
    for name in names:
        url = url.child(name)

    for key, value in params.iteritems():
        url = url.add(key, value)
    d = util.PerseverantDownloader(url).go()
    d.addErrback(handleError)
    d.addCallback(
        lambda (data, headers): lxml.objectify.fromstring(data))
    return d



def search(term, limit=25):
    """
    Query the Twitter search API and parse the result.

    @rtype: C{Deferred} => C{lxml.objectify.ObjectifiedElement}
    """
    url = TWITTER_SEARCH.child('search.atom'
        ).add('q', term.encode('utf-8')
        ).add('rpp', limit
        ).add('result_type', 'mixed')
    d = util.PerseverantDownloader(url).go()
    d.addErrback(handleError)

    def getResults((data, headers)):
        root = lxml.objectify.fromstring(data)
        if not root.findall('{http://www.w3.org/2005/Atom}entry'):
            raise errors.NoSearchResults(
                u'No results for the search term: ' + term)
        return root

    d.addCallback(getResults)
    return d



def extractStatusIDFromURL(url):
    """
    Attempt to extract a status ID from a URL.

    @return: A C{unicode} value of the status ID, or C{None} if there is
        none.
    """
    netloc = url.netloc
    if netloc.startswith('www.'):
        netloc = netloc[4:]
    if netloc == 'twitter.com':
        segs = url.pathList()
        # New-style Twitter URL
        if len(segs) == 1 and not segs[0] and url.fragment:
            segs = url.fragment[2:].split('/', 2)
        if len(segs) >= 3:
            screenName, method, id = segs
            if method in ['status', 'statuses']:
                try:
                    return unicode(int(id))
                except (TypeError, ValueError):
                    pass
    return None



def _sanitizeFormatting(value):
    value = unescape(value)
    lines = value.splitlines()
    return u' '.join(lines)



def formatUserInfo(user):
    """
    Format a user info LXML C{ObjectifiedElement}.
    """
    def _fields():
        yield u'User', u'%s (%s)' % (user.name, user.screen_name)
        yield u'Statuses', user.statuses_count
        yield u'Website', user.url
        yield u'Followers', user.followers_count
        yield u'Friends', user.friends_count
        yield u'Location', user.location
        yield u'Description', user.description

    for key, value in _fields():
        if value:
            yield key, _sanitizeFormatting(unicode(value))



def formatStatus(status, includeReplyTo=True):
    """
    Format a status LXML C{ObjectifiedElement}.
    """
    parts = dict()
    parts['name'] = u'%s (%s)' % (status.user.name, status.user.screen_name)
    if includeReplyTo:
        parts['reply'] = status.in_reply_to_status_id
    parts['text'] = _sanitizeFormatting(status['text'].text)
    timestamp = timeutil.parse(status.created_at.text)
    parts['timestamp'] = timestamp.asHumanly()
    return parts



def conversation(statusID, limit=None, query=query):
    """
    Follow a Twitter conversation.

    @type  statusID: C{str}
    @param statusID: Latest tweet in the conversation.

    @type  limit: C{int}
    @param limit: Number of replies to follow, or C{None} for unlimited.

    @return: C{Deferred} that fires with a C{list} of status LXML
        C{ObjectifiedElement}s.
    """
    def _reachedLimit(results):
        if limit is None:
            return False
        return len(results) >= limit

    def _followThread(status, results):
        results.append(status)
        if status.in_reply_to_status_id and not _reachedLimit(results):
            d2 = followStatus(str(status.in_reply_to_status_id), results)
        else:
            d2 = succeed(results)
        return d2


    def followStatus(statusID, results):
        d = query('statuses/show', statusID)
        d.addCallback(_followThread, results)
        return d

    return followStatus(statusID, [])
