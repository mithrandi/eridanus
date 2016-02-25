import math, operator
from decimal import Decimal

from pymeta.grammar import OMeta
from pymeta.runtime import ParseError



def operate(res, (op, value)):
    return op(res, value)



def foldr(op, end, seq):
    if not seq:
        return end

    head = seq[0]
    tail = seq[1:]
    return op(head, foldr(op, end, tail))



DIGITS = u'0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
def base(n, b):
    """
    Convert a base-10 number to a base-N number.

    @rtype: C{unicode}
    """
    if b < 2 or b > 36:
        raise ValueError(u'Base must be between 2 and 36, inclusively')

    digits = u''
    while n:
        n, r = divmod(n, b)
        digits = DIGITS[r] + digits

    return digits



FUNCTIONS = {
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
    'tanh':    math.tanh}



CONSTANTS = {
    'e':  Decimal(str(math.e)),
    'pi': Decimal(str(math.pi))}



def func(name):
    global FUNCTIONS
    try:
        return FUNCTIONS[name]
    except KeyError:
        raise SyntaxError(u'"%s" is not a recognised function' % (name,))



def constant(name):
    global CONSTANTS
    try:
        return CONSTANTS[name]
    except KeyError:
        raise SyntaxError(u'"%s" is not a recognised constant' % (name,))



# This is to make pyflakes and such happier:
operator


calcGrammar = """
expn         ::= <sum>:s <end> => s
sum          ::= <term_init>:a <term>*:b => reduce(operate, [a] + b, 0)

term_init    ::= <term_op>?:op <product>:a => (op or operator.add, a)
term         ::= <term_op>:op <product>:a => (op, a)
term_op      ::= <spaces>
                 ('+' => operator.add
                 |'-' => operator.sub):term => term

product      ::= <pow>:a <product_elem>*:b
                 => reduce(operate, [(operator.mul, a)] + b, 1)
product_elem ::= <product_op>:op <pow>:a => (op, a)
product_op   ::= <spaces>
                 ('*'     => operator.mul
                 |'/' '/' => operator.floordiv
                 |'/'     => operator.truediv
                 |'%'     => operator.mod):product => product

pow          ::= (<atom>:a '*' '*' => a)*:xs <atom>:z
                 => foldr(operator.pow, z, xs)

atom         ::= <spaces>
                 (<func>
                 |<constant>
                 |'(' <sum>:a ')' => a
                 |<decimal>
                 |<integer>):atom <spaces> => atom

func         ::= <name>:n '(' <func_params>?:p ')'
                 => Decimal(str(func(n)(*p or [])))
func_params  ::= <sum>:a (<spaces> ',' <spaces> <sum>)*:b => [a] + b
constant     ::= <name>:n => constant(n)
name         ::= <letter>:x <letterOrDigit>*:xs => x + ''.join(xs)
integer      ::= <sign>:s <digit>+:a
                 => Decimal(s + ''.join(a))
decimal      ::= <sign>:s
                 (<digit>+:a ('.' <digit>*):b
                 |<digit>*:a ('.' <digit>+):b)
                 => Decimal(s + ''.join(a + ['.'] + b))
sign         ::= ('-' | '+')?:s => s or ''
"""



class CalcGrammar(OMeta.makeGrammar(calcGrammar, globals())):
    pass



def evaluate(expn):
    """
    Evaluate a simple mathematical expression.

    @rtype: C{Decimal}
    """
    try:
        result, err = CalcGrammar(expn).apply('expn')
        return result
    except ParseError:
        raise SyntaxError(u'Could not evaluate the provided mathematical expression')
