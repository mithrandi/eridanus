from datetime import timedelta
from textwrap import dedent

from twisted.trial import unittest

from eridanus import util, errors


class TestMisc(unittest.TestCase):
    def test_humanReadableTimeDelta(self):
        self.assertEqual(util.humanReadableTimeDelta(timedelta()), u'never')
        self.assertEqual(util.humanReadableTimeDelta(timedelta(days=1)), u'1 day')
        self.assertEqual(util.humanReadableTimeDelta(timedelta(days=1, hours=3)), u'1 day 3 hours')
        self.assertEqual(util.humanReadableTimeDelta(timedelta(days=1, hours=3, minutes=5)), u'1 day 3 hours 5 minutes')
        self.assertEqual(util.humanReadableTimeDelta(timedelta(days=1, hours=3, minutes=5, seconds=7)), u'1 day 3 hours 5 minutes 7 seconds')
        self.assertEqual(util.humanReadableTimeDelta(timedelta(seconds=60)), u'1 minute')
        self.assertEqual(util.humanReadableTimeDelta(timedelta(minutes=60)), u'1 hour')
        self.assertEqual(util.humanReadableTimeDelta(timedelta(hours=24)), u'1 day')

    def test_humanReadableFileSize(self):
        """
        L{eridanus.util.humanReadableFileSize} correctly converts a value in
        bytes to something easier for a human to interpret.
        """
        self.assertEqual(util.humanReadableFileSize(1023), u'1023 bytes')
        self.assertEqual(util.humanReadableFileSize(1024), u'1.00 KB')
        self.assertEqual(util.humanReadableFileSize(1024 ** 3), u'1.00 GB')

        self.assertNotEqual(util.humanReadableFileSize(1023), u'1023.00 bytes')
        self.assertNotEqual(util.humanReadableFileSize(1024), u'1024 bytes')

    def test_hostMatches(self):
        """
        Matching a usermask against a mask with L{eridanus.util.hostMatches}
        gives the correct result.
        """
        host = 'joe!joebloggs@an-isp-of-some-sort.roflcopter.com'
        self.assertTrue(util.hostMatches(host, '*'))
        self.assertTrue(util.hostMatches(host, 'joe!*@*'))
        self.assertTrue(util.hostMatches(host, 'joe!*blog*@*'))
        self.assertTrue(util.hostMatches(host, 'joe!*blog*@*rofl*.com'))

        self.assertFalse(util.hostMatches(host, 'joe'))
        self.assertFalse(util.hostMatches(host, 'bob!*@*'))
        self.assertFalse(util.hostMatches(host, '*!*@*lol*'))

    def test_padIterable(self):
        """
        L{eridanus.util.padIterable} correctly pads an interable in both
        length and value.
        """
        padIterable = lambda *a, **kw: list(util.padIterable(*a, **kw))

        self.assertEqual(padIterable([], 2), [None, None])
        self.assertEqual(padIterable([1], 2), [1, None])
        self.assertEqual(padIterable([1, 2], 2), [1, 2])
        self.assertEqual(padIterable([1, 2, 3], 2), [1, 2])
        self.assertEqual(padIterable([1], 2, padding='foo'), [1, 'foo'])

        self.assertNotEqual(padIterable([1], 2),    [1])
        self.assertNotEqual(padIterable([1, 2], 2), [1, None])

    def test_normalizeMask(self):
        """
        Normalizing a mask with L{eridanus.util.normalizeMask} results in a
        normalized mask that successfully represents the input.
        """
        self.assertEqual(util.normalizeMask('bob'), 'bob!*@*')
        self.assertEqual(util.normalizeMask('bob!foo'), 'bob!foo@*')
        self.assertEqual(util.normalizeMask('bob!foo@bar'), 'bob!foo@bar')

        self.assertRaises(errors.InvalidMaskError, util.normalizeMask, '')
        self.assertRaises(errors.InvalidMaskError, util.normalizeMask, 'bob@bar')
        self.assertRaises(errors.InvalidMaskError, util.normalizeMask, 'bob@foo!bar')

    def test_tabulateDefaultJoiner(self):
        """
        Tabulating data with the default joiner works as intended.
        """
        output = dedent("""\
        Col1    Col2  Col3
        1       test  k
        foobar  lol   zozlasdf""")

        headers = ['Col1', 'Col2', 'Col3']
        data = [['1', 'test', 'k'],
                ['foobar', 'lol', 'zozlasdf']]
        result = '\n'.join(util.tabulate(headers, data))
        self.assertEqual(result, output)

    def test_tabulateCustomJoiner(self):
        """
        Tabulating data with a custom joiner works as intended.
        """
        output = dedent("""\
        Col1   | Col2 | Col3
        1      | test | k
        foobar | lol  | zozlasdf""")

        headers = ['Col1', 'Col2', 'Col3']
        data = [['1', 'test', 'k'],
                ['foobar', 'lol', 'zozlasdf']]
        result = '\n'.join(util.tabulate(headers, data, joiner=' | '))
        self.assertEqual(result, output)
