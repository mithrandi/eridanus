"""
Utility functions designed for scraping data off IMDB.
"""
import urllib

from twisted.internet import defer

from nevow.url import URL

from eridanus.util import PerseverantDownloader

from eridanusstd.util import parseHTML


IMDB_URL = URL.fromString('http://www.imdb.com/')


_artifactParams = {
    'tvSeries':   'tv',
    'tvMovies':   'tvm',
    'tvEpisodes': 'ep',
    'videos':     'vid',
    }


def searchByTitle(title, exact=True, artifacts=None):
    """
    Search IMDB for artifacts named C{title}.

    @type title: C{unicode}
    @param title: The title of the artifact to find

    @type exact: C{bool}
    @param exact: Flag indicating whether only exact matches are considered

    @type artifacts: C{list} of C{str}
    @param artifacts: A list of artifact names to include in the search, this
        is empty by default which means to exclude everything except movies;
        Available values are::

            tvSeries - Include TV series

            tvMovies - Include TV movies

            tvEpisodes - Include individual TV series episodes

            videos - Include videos

    @rtype: Deferred firing with an C{iterable} of
        C{(unicode, unicode, unicode)}
    @return: A deferred that fires with C{(name, url, id)}
    """
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        }
    title = title.encode('utf-8')
    if artifacts is None:
        artifacts = []

    off = set(_artifactParams.values())
    on = set(_artifactParams[key] for key in artifacts)

    params = [
        'words=' + urllib.quote(title),
        'exact=' + ('off', 'on')[exact],
        ]
    params += [key + '=off' for key in off - on]
    params += [key + '=on' for key in on]

    postdata = '&'.join(params)
    pd = PerseverantDownloader(IMDB_URL.child('List'),
                               headers=headers,
                               method='POST',
                               postdata=postdata)

    return pd.go().addCallback(_parseSearchResults)


def getInfoByID(id):
    """
    Get information for the given IMDB ID.
    """
    url = IMDB_URL.child('title').child(id)
    return PerseverantDownloader(url).go(
        ).addCallback(_parseTitleInfo, url)


def getInfoByTitle(title, **kw):
    """
    Get information for the given IMDB title.

    This first calls L{searchByTitle} with C{title} and any additional
    keyword arguments, and the first result is used to retrieve the
    information.
    """
    def gotSearchResults(results):
        for name, url, id in results:
            return id

    return searchByTitle(title, **kw
        ).addCallback(gotSearchResults
        ).addCallback(getInfoByID)



def _parseSearchResults((data, headers)):
    """
    Parse search result HTML into an iterable of C{(name, url, id)}.
    """
    tree = parseHTML(data)

    # XXX: Maybe do something a little more less shot-in-the-darkish, like
    # finding the first `ol` after an `h1`.
    for li in tree.find('//ol').findall('li'):
        a = li.find('a')
        url = IMDB_URL.click(a.get('href'))
        name = unicode(a.text)
        # Skip video games, this should be part of the "I want movies,
        # I want TV series" criteria stuff.
        if not name.endswith(u'(VG)'):
            pathList = url.pathList()
            id = pathList[-1] or pathList[-2]
            yield name, url, id


def _parseSummary((data, headers)):
    """
    Extract the plot summary.
    """
    tree = parseHTML(data)

    for p in tree.findall('//p'):
        if p.get('class') == 'plotpar':
            return p.text.strip()


def _getPlotSummary(info, url):
    """
    Get the plot summary and store it in C{info}.

    @type info: C{dict}

    @type url: C{nevow.url.URL}
    @param url: IMDB URL to plot summary

    @return: Deferred firing with C{info}
    """
    def gotSummary(summary):
        info[u'summary'] = summary
        return info

    return PerseverantDownloader(url).go(
        ).addCallback(_parseSummary
        ).addCallback(gotSummary)


def _parsePoster((data, headers)):
    """
    Extract the URL for the poster image.
    """
    tree = parseHTML(data)

    for table in tree.findall('//table'):
        if table.get('id') == 'principal':
            img = table.find('.//img')
            if img is not None:
                return IMDB_URL.click(img.get('src'))
            return None


def _getPoster(info, url):
    """
    Get the poster image URL and store it in C{info}.

    @type info: C{dict}

    @type url: C{nevow.url.URL}
    @param url: IMDB URL to poster image

    @return: Deferred firing with C{info}
    """
    def gotPoster(posterURL):
        info[u'poster'] = posterURL
        return info

    return PerseverantDownloader(url).go(
        ).addCallback(_parsePoster
        ).addCallback(gotPoster)


def _hyperlinkedText(name):
    """
    Factory producing a function to get the text and URL from an element's
    anchor child.

    @type name: C{unicode}
    @param name: Info name to yield with.
    """
    def _fact(elem):
        a = elem.find('a')
        url = IMDB_URL.click(a.get('href'))
        yield name, (a.text.strip(), url)
    return _fact


def _genre(elem):
    """
    Yield a C{list} of C{unicode} genre names.
    """
    yield u'genres', [e.text
                      for e in elem.findall('a')
                      if e.get('class') is None]


def _releaseDate(elem):
    """
    Yield the release date, as it appears, and the artifact's year.
    """
    releaseDate = elem.find('h5').tail.strip()
    yield u'releaseDate', releaseDate
    try:
        year = releaseDate.split()[2]
        yield u'year', int(year)
    except ValueError:
        pass


def _parseCast(elem):
    """
    Extract actors and their characters.

    The URL components of the resulting tuples may be C{None} to indicate
    that there is no IMDB page available for that actor/character.

    @rtype: C{iterable} of
        C{((unicode, nevow.url.URL), (unicode, nevow.url.URL))}
    @return: An iterable of
        C{((actorName, actorURL), (characterName, characterURL))}
    """
    def extractCharacter(row):
        tds = tr.findall('.//td')

        # 0 is the image, 1 is the actor name, 2 is '...', 3 is the character.
        td = tds[1]
        a = td.find('a')
        if a is not None:
            actorName = a.text
            actorURL = IMDB_URL.click(a.get('href'))
        else:
            actorName = td.text
            actorURL = None

        td = tds[3]
        a = td.find('a')
        if a is not None:
            charName = a.text
            charURL = IMDB_URL.click(a.get('href'))
        else:
            charName = td.text
            charURL = None

        return (actorName, actorURL), (charName, charURL)

    for tr in elem.findall('.//tr'):
        yield extractCharacter(tr)


_infoParsers = {
    u'director': _hyperlinkedText(u'director'),
    u'genre': _genre,
    u'release date': _releaseDate,
    }

def _parseTitleInfo((data, headers), url):
    """
    Parse an IMDB HTML document into structured information.

    The resulting dictionary contains keys that map roughly to the relevant
    IMDB fields of the same name.

    @rtype: Deferred firing with a C{dict}
    """
    tree = parseHTML(data)

    info = {}
    info['title'] = tree.find('//h1').text.strip()

    # Scan all the `<div class="info">` tags for information that we know how
    # to parse.
    infoElems = (e for e in tree.findall('//div') if e.get('class') == 'info')
    for elem in infoElems:
        h5 = elem.find('h5')
        if h5 is None:
            continue

        infoName = h5.text
        if infoName is None:
            continue

        infoName = infoName.rstrip(':').lower()
        parser = _infoParsers.get(infoName)
        if parser is not None:
            info.update(parser(elem))

    castElem = (e for e in tree.findall('//table') if e.get('class') == 'cast').next()
    info['cast'] = list(_parseCast(castElem))

    posterURL = None
    for a in tree.findall('//a'):
        if a.get('name') == 'poster':
            posterURL = url.click(a.get('href'))
            break

    d = defer.succeed(info
        ).addCallback(_getPlotSummary, url.child('plotsummary'))

    if posterURL is not None:
        d.addCallback(_getPoster, posterURL)

    return d
