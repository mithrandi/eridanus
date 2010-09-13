from twisted.trial.unittest import TestCase

from pymeta.runtime import ParseError

from nevow.url import URL

from eridanus import iriparse



class IRIParseTests(TestCase):
    """
    Tests for L{eridanus.iriparse}.
    """
    def test_extractURL(self):
        """
        L{eridanus.iriparse.extractURL} extracts only a single URI, and the
        position in the original input where that URI ends, from the beginning
        of a string.
        """
        url = u'http://google.com'

        self.assertEquals(
            iriparse.extractURL(url),
            (url, len(url)))

        self.assertEquals(
            iriparse.extractURL(url + u' world'),
            (url, len(url)))

        self.assertRaises(
            ParseError,
           iriparse.extractURL, u'hello world')


    def test_extractURLsWithPosition(self):
        """
        L{eridanus.iriparse.extractURLsWithPosition} extracts pairs of URIs and
        the index of the end of the URI from a string.
        """
        self.assertEquals(
            list(iriparse.extractURLsWithPosition(
                u'hello http://google.com/ world')),
            [(u'http://google.com/', 24)])

        self.assertEquals(
            list(iriparse.extractURLsWithPosition(
                u'hello http://google.com/ http://foo.bar/ world')),
            [(u'http://google.com/', 24),
             (u'http://foo.bar/', 40)])

        self.assertEquals(
            list(iriparse.extractURLsWithPosition(
                u'hello https://google.com/ world')),
            [(u'https://google.com/', 25)])

        self.assertEquals(
            list(iriparse.extractURLsWithPosition(
                u'hello ftp://google.com/ world')),
            [])

        self.assertEquals(
            list(iriparse.extractURLsWithPosition(
                u'hello ftp://google.com/ world',
                supportedSchemes=[u'ftp'])),
            [(u'ftp://google.com/', 23)])


    def test_extractURLs(self):
        """
        L{eridanus.iriparse.extractURLs} extracts all URIs from a
        string.
        """
        self.assertEquals(
            list(iriparse.extractURLs(
                u'hello http://google.com/ http://foo.bar/ world')),
            [u'http://google.com/', u'http://foo.bar/'])


    def test_parseURL(self):
        """
        L{eridanus.iriparse.parseURL} extracts and parses (as a
        L{nevow.url.URL}) the first URI in a string.
        """
        self.assertEquals(
            iriparse.parseURL(
                u'http://google.com/ http://foo.bar/ world'),
            URL.fromString(u'http://google.com/'))


    def test_parseURLs(self):
        """
        L{eridanus.iriparse.parseURL} extracts and parses (as a
        L{nevow.url.URL}) all URIs in a string.
        """
        self.assertEquals(
            list(iriparse.parseURLs(u'http://google.com/')),
            [URL.fromString(u'http://google.com/')])
