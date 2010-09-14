import html5lib
from lxml import etree

from twisted.trial.unittest import TestCase, SkipTest
from twisted.python.filepath import FilePath

from eridanusstd import util



class UtilTests(TestCase):
    """
    Tests for L{eridanusstd.util}.
    """
    def setUp(self):
        self.path = FilePath(__file__)


    def test_parseHTML(self):
        """
        L{eridanusstd.util.parseHTML} will use the newer html5lib API if
        available and parse HTML content into an LXML element tree.
        """
        if not hasattr(html5lib, 'parse'):
            raise SkipTest('html5lib is too old')

        tree = util.parseHTML(self.path.sibling('index.html').open())
        self.assertIdentical(
            type(tree),
            type(etree.ElementTree()))
