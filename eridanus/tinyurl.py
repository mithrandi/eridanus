from BeautifulSoup import BeautifulSoup

from nevow import url

from eridanus.util import getPage, encode


API = 'http://tinyurl.com/'


def extractTinyUrl(data):
    # XXX: raise some real exceptions here when stuff goes bad
    soup = BeautifulSoup(data)
    file('splat', 'wb').write(data)
    input = soup.find('input', attrs=dict(name='tinyurl'))
    if input is not None:
        return input['value']
    # XXX: raise an exception
    return None


def tinyurl(uri):
    #u = url.URL.fromString(API).child('create.php').add('url', uri)
    # XXX: Sigh. TinyURL makes it very obvious that it was written in PHP by
    # a retard. Quoted characters never get unquoted and then you get broken
    # URLs. Kevin Gilbertson, please burn in hell for eternity while having
    # ants bite your urethra.
    u = str(url.URL.fromString(API).child('create.php')) + '?url=' + encode(uri)
    return getPage(u).addCallback(extractTinyUrl)
