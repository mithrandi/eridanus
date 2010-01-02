import math

from decimal import Decimal
from twisted.trial import unittest

from eridanusstd import calc



class CalcGrammarTests(unittest.TestCase):
    """
    Tests for L{eridanusstd.calc}.
    """
    def assertEvaluates(self, expn, expectedResult):
        """
        Assert that C{expn}, when evaluated by L{eridanusstd.calc.evaluate},
        produces C{expectedResult}.
        """
        self.assertEquals(expectedResult, calc.evaluate(expn))


    def assertInvalidExpression(self, expn, error=SyntaxError):
        """
        Assert that C{expn} causes L{eridanusstd.calc.evaluate} to raise
        C{error}.
        """
        self.assertRaises(error, calc.evaluate, expn)


    def test_atom(self):
        """
        An atom is a single unit of an expression: decimals, integers,
        functions and constants. Atoms may be preceeded by signs (C{'+'} or
        C{'-'}) only.
        """
        self.assertEvaluates('-1', -1)
        self.assertEvaluates('2', 2)
        self.assertEvaluates('+3', 3)

        self.assertEvaluates('3.1415', Decimal('3.1415'))
        self.assertEvaluates('.1415', Decimal('.1415'))
        self.assertEvaluates('3.', 3)
        self.assertInvalidExpression('.')

        self.assertEvaluates('(3)', 3)
        self.assertEvaluates('(2.5)', Decimal('2.5'))

        for op in ['/', '*', '%', '//', '**', '@']:
            self.assertInvalidExpression(op + '42')
            self.assertInvalidExpression('42' + op)


    def test_func(self):
        """
        Functions can be called and passed parameters. Constants can by used by
        name, but cannot be called.
        """
        self.assertEvaluates('sin(0)', 0)
        self.assertEvaluates('cos(0)', 1)

        self.assertInvalidExpression('cos()', TypeError)
        self.assertInvalidExpression('sin')

        self.assertEvaluates('pi', Decimal(str(math.pi)))
        self.assertInvalidExpression('pi()')


    def test_sum(self):
        """
        Summing terms.
        """
        self.assertEvaluates('1+1', 2)
        self.assertEvaluates('10 - 11', -1)
        self.assertEvaluates('1+1 +1- 3', 0)
        self.assertInvalidExpression('1+1+')


    def test_product(self):
        """
        Products of terms.
        """
        self.assertEvaluates('1* 1', 1)
        self.assertEvaluates('25 /5', 5)
        self.assertEvaluates('5 / 2', Decimal('2.5'))
        self.assertEvaluates('5 // 2', 2)
        self.assertEvaluates('5% 2', 1)
        self.assertEvaluates('3 * 5% 10 /5', 1)
        self.assertInvalidExpression('1*1*')


    def test_pow(self):
        """
        Exponent operator.
        """
        self.assertEvaluates('1 ** 0', 1)
        self.assertEvaluates('-1 ** 2', -1)
        self.assertEvaluates('(-1) ** 2', 1)
        self.assertEvaluates('10 ** -2', Decimal('0.01'))


    def test_complex(self):
        """
        Expressions comprising all the separate parts.
        """
        self.assertEvaluates('10 / 2 + 5 * 4 - (15 + 10)', 0)
        self.assertEvaluates('cos(0) * 10 % 3 * sin(pi / 2) + (2** 0)', 2)



class BaseConversionTests(unittest.TestCase):
    """
    Tests for L{eridanusstd.calc.base}.
    """
    def test_base(self):
        """
        Convert a base-10 number to a base-N number, represented as text.
        """
        self.assertEquals(u'11', calc.base(11, 10))
        self.assertEquals(u'12', calc.base(10, 8))
        self.assertEquals(u'A', calc.base(10, 16))
        self.assertEquals(u'3YW', calc.base(5144, 36))
