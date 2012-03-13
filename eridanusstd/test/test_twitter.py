import lxml.objectify
from twisted.trial import unittest
from twisted.python.filepath import FilePath
from twisted.internet.defer import succeed
from twisted.web import error as weberror

from axiom.store import Store

from nevow.url import URL

from eridanusstd import twitter, errors
from eridanusstd.plugindefs import twitter as twitter_plugin



class MockPerseverantDownloader(object):
    """
    Mock C{PerseverantDownloader}.
    """
    def __init__(self, value, callback):
        self.value = value
        self.callback = callback


    def go(self):
        return succeed(self.value).addCallback(self.callback)



class TwitterTestsMixin(object):
    """
    Mixin for Twitter tests.
    """
    def setUp(self):
        self.path = FilePath(__file__)
        self.store = Store()
        self.plugin = twitter_plugin.Twitter(store=self.store)


    def objectify(self, filename):
        """
        Read XML, from a file, and parse it with C{lxml.objectify}.
        """
        return lxml.objectify.fromstring(
            self.path.sibling(filename).getContent())



class TwitterTests(TwitterTestsMixin, unittest.TestCase):
    def test_extractStatusIDFromURL(self):
        """
        Status identifiers are extracted from known valid forms of Twitter
        status URLs, C{None} is extracted for unknown forms.
        """
        expected = [
            ('http://twitter.com/bob/status/514431337', '514431337'),
            ('http://www.twitter.com/bob/status/514431337', '514431337'),
            ('http://twitter.com/bob/statuses/514431337', '514431337'),
            ('http://twitter.com/#!/bob/statuses/514431337', '514431337'),
            ('http://www.twitter.com/#!/bob/statuses/514431337', '514431337'),
            ('http://www.twitter.com/bob/statuses/hello', None),
            ('http://www.twitter.com/bob/statuses', None),
            ('http://somethingnottwitter.com/bob/statuses/514431337', None)]

        for url, result in expected:
            assertFn = self.assertEquals
            if result is None:
                assertFn = self.assertIdentical

        assertFn(twitter.extractStatusIDFromURL(URL.fromString(url)), result)


    def test_formatStatus(self):
        """
        Format an objectified Twitter status query response. Newlines are
        converted to spaces.
        """
        o = self.objectify('twitter_status.xml')
        self.assertEquals(
            twitter.formatStatus(o),
            dict(name=u'Bob Jones (bob)',
                 reply=u'',
                 text=u'This is text.',
                 timestamp=u'25 Jun 2009, 09:57 am'))

        o.in_reply_to_status_id = '42'
        self.assertEquals(
            twitter.formatStatus(o),
            dict(name=u'Bob Jones (bob)',
                 reply=u'42',
                 text=u'This is text.',
                 timestamp=u'25 Jun 2009, 09:57 am'))

        o['text'] = 'Foo\nbar.'
        self.assertEquals(
            twitter.formatStatus(o),
            dict(name=u'Bob Jones (bob)',
                 reply=u'42',
                 text=u'Foo bar.',
                 timestamp=u'25 Jun 2009, 09:57 am'))


    def test_formatStatusPlugin(self):
        """
        Format an objectified Twitter status query response with the plugin's
        internal formatter.
        """
        o = self.objectify('twitter_status.xml')
        self.assertEquals(
            self.plugin.formatStatus(o),
            u'\002Bob Jones (bob)\002: This is text. (posted 25 Jun 2009, 09:57 am)')

        o.in_reply_to_status_id = '42'
        self.assertEquals(
            self.plugin.formatStatus(o),
            u'\002Bob Jones (bob)\002 (in reply to #42): This is text. (posted 25 Jun 2009, 09:57 am)')

        o['text'] = 'Foo\nbar.'
        self.assertEquals(
            self.plugin.formatStatus(o),
            u'\002Bob Jones (bob)\002 (in reply to #42): Foo bar. (posted 25 Jun 2009, 09:57 am)')


    def test_formatUserInfo(self):
        """
        Format an objectified Twitter user info query response. Newlines are
        converted to spaces and blank fields are omitted.
        """
        o = self.objectify('twitter_user.xml')
        expected = [
            (u'User', u'Bob Jones (bob)'),
            (u'Statuses', u'2'),
            (u'Followers', u'5'),
            (u'Friends', u'7'),
            (u'Location', u'Earth'),
            (u'Description', u'Foo. Bar.')]

        for expected, result in zip(expected, twitter.formatUserInfo(o)):
            self.assertEquals(expected, result)


    def test_formatUserInfoPlugin(self):
        """
        Format an objectified Twitter user info query response with the
        plugin's internal formatter.
        """
        o = self.objectify('twitter_user.xml')
        expected = [
            (u'User', u'Bob Jones (bob)'),
            (u'Statuses', u'2'),
            (u'Followers', u'5'),
            (u'Friends', u'7'),
            (u'Location', u'Earth'),
            (u'Description', u'Foo. Bar.')]

        for (key, value), res in zip(expected, self.plugin.formatUserInfo(o)):
            self.assertEquals(
                res,
                u'\002%s\002: %s' % (key, value))


    def test_handleError(self):
        """
        Convert Twitter API error responses into
        L{eridanusstd.errors.RequestError} exceptions.
        """
        def makeError(dummy):
            data = self.path.sibling('twitter_error.xml').open().read()
            raise weberror.Error(404, None, data)

        def makeFetcher(url):
            return MockPerseverantDownloader(None, makeError)

        self.patch(twitter.util, 'PerseverantDownloader', makeFetcher)
        d = self.assertFailure(twitter.query('foo/bar'), errors.RequestError)

        @d.addCallback
        def checkError(e):
            o = self.objectify('twitter_error.xml')
            self.assertEquals(e.request, o.request)
            self.assertEquals(e.error, o.error)

        return d



class TwitterConversationTests(TwitterTestsMixin, unittest.TestCase):
    """
    Tests for L{eridanusstd.twitter.conversation}.
    """
    def setUp(self):
        super(TwitterConversationTests, self).setUp()
        self.called = []


    def query(self, method, arg):
        """
        Replacement for L{eridanusstd.twitter.query}.
        """
        self.called.append((method, arg))
        return succeed(self.objectify(self.results.next()))


    def test_conversation(self):
        """
        Unlimited Twitter conversation thread.
        """
        self.results = iter([
            'twitter_convo_3.xml',
            'twitter_convo_2.xml',
            'twitter_convo_1.xml'])

        def checkResults(results):
            self.assertEquals(3, len(results))
            self.assertEquals(3, len(self.called))
            self.assertEquals(
                list(zip(*self.called)[1]),
                [str(s.id) for s in results])

        d = twitter.conversation('3', limit=None, query=self.query)
        d.addCallback(checkResults)
        return d


    def test_conversationLimit(self):
        """
        Limited Twitter conversation thread.
        """
        self.results = iter([
            'twitter_convo_3.xml',
            'twitter_convo_2.xml',
            'twitter_convo_1.xml'])

        def checkResults(results):
            self.assertEquals(2, len(results))
            self.assertEquals(2, len(self.called))
            self.assertEquals(
                list(zip(*self.called)[1]),
                [str(s.id) for s in results])

        d = twitter.conversation('3', limit=2, query=self.query)
        d.addCallback(checkResults)
        return d
