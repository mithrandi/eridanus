import math, operator

from pymeta.grammar import OMeta
from pymeta.runtime import ParseError


def operate(res, (op, value)):
    return op(res, value)


def foldr(op, end, seq):
    if not seq:
        return end

    head = seq[0]
    tail = seq[1:]
    if not tail:
        return op(head, end)
    else:
        return op(head, foldr(op, end, tail))


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

    # Constants
    'e':       math.e,
    'pi':      math.pi,
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
                 ('*' => operator.mul
                 |'/' => operator.div
                 |'%' => operator.mod):product => product

pow          ::= (<atom>:a '*' '*' => a)*:xs <atom>:z => foldr(operator.pow, z, xs)

atom         ::= <spaces>
                 (<func>
                 |<constant>
                 |'(' <sum>:a ')' => a
                 |<decimal>
                 |<integer>):atom <spaces> => atom

func         ::= <name>:n '(' <sum>:e ')' => func(n)(e)
constant     ::= <name>:n => func(n)
name         ::= <letter>:x <letterOrDigit>*:xs !(xs.insert(0, x)) => ''.join(xs)
integer      ::= <digit>+:a => int(''.join(a))
decimal      ::= (<digit>*:a ('.' <digit>*):b) => float(''.join(a) + '.' + ''.join(b))
"""


class CalcGrammar(OMeta.makeGrammar(calcGrammar, globals())):
    pass


def evaluate(expn):
    """
    Evaluate a simple mathematical expression.
    """
    try:
        return CalcGrammar(expn).apply('expn')
    except ParseError:
        raise SyntaxError(u'Could not evaluate the provided mathematical expression')
