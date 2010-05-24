from twisted.trial import unittest
from twisted.python.filepath import FilePath
from twisted.internet.defer import succeed

from eridanusstd import google, errors



class CalculatorTests(unittest.TestCase):
    """
    Tests for L{eridanusstd.google.Calculator}.
    """
    def setUp(self):
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
        self.fetchData = FilePath(__file__).sibling(
            'google_calc.html').open().read()
        d = self.calc.evaluate('sqrt(2/(pi*18000/(mi^2)*80/year*30 minutes)')

        @d.addCallback
        def checkResult(res):
            self.assertEquals(res, u'sqrt(2 / (((((pi * 18 000) / (mi^2)) * 80) / year) * (30 minutes))) = 141.683342 meters')

        return d


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
