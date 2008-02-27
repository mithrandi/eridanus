import re

from BeautifulSoup import BeautifulSoup

from twisted.web import client, http, error as weberror

from eridanus import const


def encode(s):
    return s.encode(const.ENCODING, 'replace')


def decode(s):
    return s.decode(const.ENCODING, 'replace')


def handle206(failure):
    failure.trap(weberror.Error)
    err = failure.value
    if int(err.status) == http.PARTIAL_CONTENT:
        return err.response

    return failure


def getPage(*a, **kw):
    return client.getPage(*a, **kw).addErrback(handle206)


_whitespace = re.compile(ur'\s+')

def sanitizeTitle(title):
    return _whitespace.sub(u' ', title.strip())


def extractTitle(data):
    try:
        soup = BeautifulSoup(data)
        titleElem = soup.find('title')
        if titleElem is not None:
            return sanitizeTitle(titleElem.contents[0])
    except:
        pass

    return None


def truncate(s, limit):
    if len(s) + 3 < limit:
        return s

    return s[:limit] + '...'
