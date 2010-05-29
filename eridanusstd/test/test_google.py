from twisted.trial import unittest
from twisted.python.filepath import FilePath
from twisted.internet.defer import succeed, gatherResults

from eridanusstd import google, errors



class CalculatorTests(unittest.TestCase):
    """
    Tests for L{eridanusstd.google.Calculator}.
    """
    def setUp(self):
        self.path = FilePath(__file__)
        self.calc = google.Calculator()
        self.fetchData = None
        self.patch(self.calc, '_fetch', self._fetch)


    def _fetch(self, url):
        """
        Patch L{eridanusstd.google.Calculator._fetch} to avoid network traffic.
        """
        return succeed((self.fetchData, dict()))


    def test_evaluateGood(self):
        """
        Evaluating a valid calculator expression yields a result.
        """
        def testExpression(filename, expected):
            self.fetchData = self.path.sibling(filename).open().read()
            # The value to evaluate is irrelevant since the page data comes
            # from "filename".
            d = self.calc.evaluate('an expression goes here')
            def checkResult(res):
                self.assertEquals(res, expected)
            return d.addCallback(checkResult)

        return gatherResults([
            testExpression('google_calc.html', u'sqrt(2 / (((((pi * 18 000) / (mi^2)) * 80) / year) * (30 minutes))) = 141.683342 meters'),
            testExpression('google_calc_2.html', u'1 googol = 1.0 \xd7 10^100')])


    def test_evaluateBad(self):
        """
        Evaluating expressions that do not yield a calculator result raise
        L{eridanusstd.errors.InvalidExpression}.
        """
        self.fetchData = FilePath(__file__).sibling(
            'google_calc_bad.html').open().read()
        d = self.calc.evaluate('davy jones')
        self.assertFailure(d, errors.InvalidExpression)
        return d
