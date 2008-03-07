import re

from BeautifulSoup import BeautifulSoup

from twisted.web import client, http, error as weberror
from twisted.python import log

from eridanus import const


class PerseverantDownloader(object):
    def __init__(self, url, tries=10, *a, **kw):
        self.url = url
        self.args = a
        self.kwargs = kw
        self.tries = tries

    def go(self):
        return getPage(self.url, *self.args, **self.kwargs).addErrback(self.retry)

    def retry(self, f):
        # XXX: What to trap?
        log.msg('PerseverantDownloader is retrying because of:')
        log.err(f)
        self.tries -= 1
        if self.tries == 0:
            return f

        return self.go()


def encode(s):
    return s.encode(const.ENCODING, 'replace')


def decode(s):
    return s.decode(const.ENCODING, 'replace')


def handle206(f):
    f.trap(weberror.Error)
    err = f.value
    if int(err.status) == http.PARTIAL_CONTENT:
        return err.response

    return f


def sanitizeUrl(url):
    if '#' in url:
        url = url[:url.index('#')]
    return url


def getPage(url, *a, **kw):
    url = sanitizeUrl(url)

    # XXX: getPage just follows redirects forever, thanks for that.
    #kw['followRedirect'] = False
    return client.getPage(url, *a, **kw).addErrback(handle206)


_whitespace = re.compile(ur'\s+')

def sanitizeTitle(title):
    return _whitespace.sub(u' ', title.strip())


def extractTitle(data):
    if data is not None:
        try:
            soup = BeautifulSoup(data, convertEntities=BeautifulSoup.HTML_ENTITIES)
            titleElem = soup.find('title')
            if titleElem is not None:
                return sanitizeTitle(titleElem.contents[0])
        except:
            log.msg('Extracting title failed:')
            log.err()

    return None


def truncate(s, limit):
    if len(s) + 3 < limit:
        return s

    return s[:limit] + '...'


def prettyTimeDelta(d):
    days = d.days

    seconds = d.seconds

    hours = seconds // 3600
    seconds -= hours * 3600

    minutes = seconds // 60
    seconds -= minutes * 60

    s = []
    if days:
        s.append('%d days' % (days,))
    if hours:
        s.append('%d hours' % (hours,))
    if minutes:
        s.append('%d minutes' % (minutes,))
    if seconds:
        s.append('%d seconds' % (seconds,))

    return ' '.join(s)
