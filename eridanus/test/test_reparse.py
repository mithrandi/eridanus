from datetime import timedelta

from twisted.trial import unittest

from eridanus import errors, reparse


class TestREParse(unittest.TestCase):
    def test_parseRegex(self):
        f, g = reparse.parseRegex('s/foo/bar/g')
        self.assertEqual(f('quuxfooquux'), 'quuxbarquux')
        self.assertNotEqual(f('quuxFooquux'), 'quuxbarquux')
        self.assertTrue(g)

        f, g = reparse.parseRegex('s/foo\/baz/bar/')
        self.assertEqual(f('quuxfoo/bazquux'), 'quuxbarquux')

        f, g = reparse.parseRegex('s/foo/bar/i')
        self.assertEqual(f('QUUXFOOQUUX'), 'QUUXbarQUUX')
        self.assertFalse(g)

        self.assertRaises(errors.MalformedRegex, reparse.parseRegex, 's/foo/baz/quux')
        self.assertRaises(errors.MalformedRegex, reparse.parseRegex, 's/foo/baz/bar/g')
