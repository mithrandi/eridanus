from twisted.trial import unittest

from eridanus import errors, reparse


class TestREParse(unittest.TestCase):
    def test_parseRegex(self):
        """
        Parsing substitution regex syntax should result in something that
        correctly performs substitution and obeys the flags passed in.
        """
        s = reparse.parseRegex('s/foo/bar/g')
        self.assertEqual(s.sub('quuxfooquux'), 'quuxbarquux')
        self.assertNotEqual(s.sub('quuxFooquux'), 'quuxbarquux')
        self.assertTrue(s.globalFlag)

        s = reparse.parseRegex('s/foo\/baz/bar/')
        self.assertEqual(s.sub('quuxfoo/bazquux'), 'quuxbarquux')

        s = reparse.parseRegex('s/foo/bar/i')
        self.assertEqual(s.sub('QUUXFOOQUUX'), 'QUUXbarQUUX')
        self.assertFalse(s.globalFlag)

        self.assertRaises(errors.MalformedRegex, reparse.parseRegex, 's/foo/baz/quux')
        self.assertRaises(errors.MalformedRegex, reparse.parseRegex, 's/foo/baz/bar/g')
