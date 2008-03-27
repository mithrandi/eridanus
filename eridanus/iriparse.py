import string

from pymeta.grammar import OMeta

# http://www.ietf.org/rfc/rfc3987.txt


def isInRange(c, ranges):
    o = ord(c)
    for start, end in ranges:
        if start <= o <= end:
            return True
    return False


def checkIPv6(xs):
    return len([x for x in xs if x is None]) <= 1


iriGrammar = """
hexdigit       ::= :x ?(x in string.hexdigits) => x

IRI            ::= !(self.markURLStart()) <scheme> ':' <ihier_part> ('?' <iquery>)? ('#' <ifragment>)? !(self.markURLEnd()) => self.input.original[self.urlStart:self.urlEnd]

ihier_part     ::= '/' '/' <iauthority> (<ipath_abempty> | <ipath_absolute> | <ipath_rootless>)?

IRI_reference  ::= <IRI> | <irelative_ref>

absolute_IRI   ::= !(self.markURLStart()) <scheme> ':' <ihier_part> ('?' <iquery>)? !(self.markURLEnd()) => self.input.original[self.urlStart:self.urlEnd]

irelative_ref  ::= <irelative_part> ('?' <iquery>)? ('#' <ifragment>)?
irelative_part ::= '/' '/' <iauthority> (<ipath_abempty> | <ipath_absolute> | <ipath_noscheme>)

iauthority     ::= (<iuserinfo> '@')? <ihost> (':' <port>)?

iuserinfo      ::= (<iunreserved> | <pct_encoded> | <sub_delims> | ':')*

ihost          ::= <IP_literal> | <IPv4address> | <ireg_name>

ireg_name      ::= (<iunreserved> | <pct_encoded> | <sub_delims>)*

ipath          ::= <ipath_abempty> | <ipath_absolute> | <ipath_noscheme> | <ipath_rootless>

ipath_abempty  ::= ('/' <isegment>)*
ipath_absolute ::= '/' (<isegment_nz> <ipath_abempty>)?
ipath_noscheme ::= <isegment_nz_nc> <ipath_abempty>
ipath_rootless ::= <isegment_nz> <ipath_abempty>

isegment       ::= <ipchar>*
isegment_nz    ::= <ipchar>+
isegment_nz_nc ::= (<iunreserved> | <pct_encoded> | <sub_delims> | '@')+

ipchar         ::= <iunreserved> | <pct_encoded> | <sub_delims> | ':' | '@'

iquery         ::= (<ipchar> | <iprivate> | '/' | '?')+

ifragment      ::= (<ipchar> | '/' | '?')+

iunreserved    ::= <unreserved> | <ucschar>

ucschar        ::= :x ?(isInRange(x, self.ucscharRanges)) => x

iprivate       ::= :x ?(isInRange(x, self.iprivateRanges)) => x

scheme         ::= <letter> (<letterOrDigit> | '+' | '-' | '.')+

port           ::= <digit>+

IP_literal     ::= '[' (<IPv6address> | <IPvFuture>) ']'

IPvFuture      ::= 'v' <hexdigit>+ '.' (<unreserved> | <sub_delims> | ':')+

IPv6address    ::= (<h16>?:x ':' => x)*:xs ?(checkIPv6(xs)) <h16>

h16            ::= <hexdigit>*:hs ?(1 <= len(hs) <= 4) => ''.join(hs)
ls32           ::= (<h16> ':' <h16>) | <IPv4address>

IPv4address    ::= <dec_octet> '.' <dec_octet> '.' <dec_octet> '.' <dec_octet>

dec_octet      ::= :x ?(0 <= x <= 255) => x

pct_encoded    ::= '%' <hexdigit> <hexdigit>

unreserved     ::= <letterOrDigit> | '-' | '.' | '_' | '~'
reserved       ::= <gen_delims> | <sub_delims>
gen_delims     ::= ':' | '/' | '?' | '#' | '[' | ']' | '@'
sub_delims     ::= '!' | '$' | '&' | '\'' | '(' | ')' | '*' | '+' | ',' | ';' | '='
"""


class IRIGrammar(OMeta.makeGrammar(iriGrammar, globals())):
    iprivateRanges = [(0x0000e000, 0x0000f8ff),
                      (0x000f0000, 0x000ffffd),
                      (0x00100000, 0x0010fffd)]

    ucscharRanges  = [(0x000000a0, 0x0000d7ff),
                      (0x0000f900, 0x0000fdcf),
                      (0x0000fdf0, 0x0000ffef),
                      (0x00010000, 0x0001fffd),
                      (0x00020000, 0x0002fffd),
                      (0x00030000, 0x0003fffd),
                      (0x00040000, 0x0004fffd),
                      (0x00050000, 0x0005fffd),
                      (0x00060000, 0x0006fffd),
                      (0x00070000, 0x0007fffd),
                      (0x00080000, 0x0008fffd),
                      (0x00090000, 0x0009fffd),
                      (0x000a0000, 0x000afffd),
                      (0x000b0000, 0x000bfffd),
                      (0x000c0000, 0x000cfffd),
                      (0x000d0000, 0x000dfffd),
                      (0x000e0000, 0x000efffd)]

    def markURLStart(self):
        self.urlStart = self.input.position

    def markURLEnd(self):
        self.urlEnd = self.input.position


def extractURL(input):
    g = IRIGrammar(input)
    uri = g.apply('IRI')
    return uri, g.urlEnd


def extractURLsWithPosition(input, supportedSchemes=None):
    if supportedSchemes is None:
        supportedSchemes = ['http']

    for scheme in supportedSchemes:
        pos = 0
        while True:
            try:
                pos = input.index(scheme, pos)
                uri, inc = extractURL(input[pos:])
                pos += inc
                yield uri, pos
            except ValueError:
                break


def extractURLs(input, supportedSchemes=None):
    for uri, _ in extractURLsWithPosition(input, supportedSchemes):
        yield uri


def parseURL(input):
    uri, = extractURL(input)
    # TODO: Actually parse the URL components ourself.
    return url.URL.fromString(uri)


def parseURLs(input, supportedSchemes=None):
    for uri in extractURLs(input, supportedSchemes):
        yield url.URL.fromString(uri)
