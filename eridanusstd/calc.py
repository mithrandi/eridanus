import math, decimal
from decimal import Decimal

from pymeta.grammar import OMeta
from pymeta.runtime import ParseError

from twisted.protocols import amp
from twisted.internet.error import ProcessTerminated

from ampoule import child, pool, main


def operate(res, (op, value)):
    return op(res, value)


def foldr(op, end, seq):
    if not seq:
        return end

    head = seq[0]
    tail = seq[1:]
    return op(head, foldr(op, end, tail))

DIGITS = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
def base(n, b):
    n = int(n)
    b = int(b)
    if b < 2 or b > 36:
        raise ValueError(u'Base must be between 2 and 36, inclusively')

    digits = ''
    while n:
        n, r = divmod(n, b)
        digits = DIGITS[r] + digits

    return digits


NAMES = {
    # Functions
    'abs':     abs,
    'acos':    math.acos,
    'asin':    math.asin,
    'atan':    math.atan,
    'ceil':    math.ceil,
    'cos':     math.cos,
    'cosh':    math.cosh,
    'degrees': math.degrees,
    'exp':     math.exp,
    'floor':   math.floor,
    'log':     math.log,
    'log10':   math.log10,
    'radians': math.radians,
    'sin':     math.sin,
    'sinh':    math.sinh,
    'sqrt':    math.sqrt,
    'tan':     math.tan,
    'tanh':    math.tanh,
    'base':    base,

    # Constants
    'e':       Decimal(str(math.e)),
    'pi':      Decimal(str(math.pi)),
}

def func(name):
    global NAMES
    try:
        return NAMES[name]
    except KeyError:
        raise SyntaxError(u'"%s" is not a recognised function or constant name' % (name,))


calcGrammar = """
expn         ::= <sum>:s <end> => s
sum          ::= <term_init>:a <term>*:b => reduce(operate, [a] + b, 0)

term_init    ::= <term_op>?:op <product>:a => (op or operator.add, a)
term         ::= <term_op>:op <product>:a => (op, a)
term_op      ::= <spaces>
                 ('+' => operator.add
                 |'-' => operator.sub):term => term

product      ::= <pow>:a <product_elem>*:b => reduce(operate, [(operator.mul, a)] + b, 1)
product_elem ::= <product_op>:op <pow>:a => (op, a)
product_op   ::= <spaces>
                 ('*'     => operator.mul
                 |'/' '/' => operator.floordiv
                 |'/'     => operator.truediv
                 |'%'     => operator.mod):product => product

pow          ::= (<atom>:a '*' '*' => a)*:xs <atom>:z => foldr(operator.pow, z, xs)

atom         ::= <spaces>
                 (<func>
                 |<constant>
                 |'(' <sum>:a ')' => a
                 |<decimal>
                 |<integer>):atom <spaces> => atom

func         ::= <name>:n '(' <func_params>:p ')' => Decimal(str(func(n)(*p)))
func_params  ::= <sum>:a (<spaces> ',' <spaces> <sum>)*:b => [a] + b
constant     ::= <name>:n => func(n)
name         ::= <letter>:x <letterOrDigit>*:xs !(xs.insert(0, x)) => ''.join(xs)
integer      ::= <digit>+:a => Decimal(''.join(a))
decimal      ::= (<digit>*:a ('.' <digit>*):b) => Decimal(''.join(a) + '.' + ''.join(b))
"""


class CalcGrammar(OMeta.makeGrammar(calcGrammar, globals())):
    pass


def evaluate(expn):
    """
    Evaluate a simple mathematical expression.

    @rtype: C{Decimal}
    """
    try:
        return CalcGrammar(expn).apply('expn')
    except ParseError:
        raise SyntaxError(u'Could not evaluate the provided mathematical expression')


class Evaluate(amp.Command):
    arguments = [('expn', amp.Unicode())]
    response = [('result', amp.Unicode())]
    errors = {decimal.Overflow:       'OVERFLOW',
              decimal.DivisionByZero: 'ZERO_DIVISION',
              SyntaxError:            'SYNTAX'}


class EvaluateChild(child.AMPChild):
    @Evaluate.responder
    def result(self, expn):
        return {'result': unicode(evaluate(expn))}


# XXX: self.pool.stop() is supposed to be called at some point?
class Calculator(object):
    def __init__(self):
        starter = main.ProcessStarter(
            packages=['twisted', 'ampoule', 'eridanusstd', 'pymeta'])
        self.pool = pool.ProcessPool(EvaluateChild,
                                     min=1, max=3,
                                     timeout=5,
                                     starter=starter)
        self.pool.start()

    def evaluate(self, expn):
        def err(f):
            f.trap(ProcessTerminated)
            raise ValueError('Calculation timeout expired')

        return self.pool.doWork(Evaluate, expn=expn
            ).addErrback(err
            ).addCallback(lambda result: result['result'])
