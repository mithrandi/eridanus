import lxml.objectify

from twisted.python.failure import Failure
from twisted.web import error as weberror

from nevow.url import URL

from eridanus import util
from eridanusstd import errors



TWITTER_API = URL.fromString('http://api.twitter.com/1/')
TWITTER_SEARCH = URL.fromString('http://search.twitter.com/')



def handleError(f):
    f.trap(weberror.Error)
    try:
        root = lxml.objectify.fromstring(f.value.response)
        return Failure(
            errors.RequestError(u'%s: %s' % (root.request, root.error)))
    except lxml.etree.XMLSyntaxError:
        return f



def query(method, arg=None, **params):
    cat, name = method.split('/')
    names = [name]
    if arg is not None:
        names.append(arg)
    names[-1] += '.xml'

    url = TWITTER_API.child(cat)
    for name in names:
        url = url.child(name)

    for key, value in params.iteritems():
        url.add(key, value)
    d = util.PerseverantDownloader(url).go()
    d.addErrback(handleError)
    d.addCallback(
        lambda (data, headers): lxml.objectify.fromstring(data))
    return d



def _quoteTerms(terms):
    """
    Iterate C{terms} and quote any terms that need to be quoted.
    """
    for term in terms:
        if u' ' in term:
            yield u'"%s"' % (term,)
        else:
            yield term



def search(terms, limit=25):
    terms = list(_quoteTerms(terms))
    url = TWITTER_SEARCH.child('search.atom'
        ).add('q', u' '.join(terms).encode('utf-8')
        ).add('rpp', limit
        ).add('result_type', 'mixed')
    d = util.PerseverantDownloader(url).go()
    d.addErrback(handleError)

    def getResults((data, headers)):
        root = lxml.objectify.fromstring(data)
        if not root.findall('{http://www.w3.org/2005/Atom}entry'):
            raise errors.NoSearchResults(
                u'No results for the search terms: ' + u'; '.join(terms))
        return root

    d.addCallback(getResults)
    return d
