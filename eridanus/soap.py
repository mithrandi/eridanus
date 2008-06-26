import base64, StringIO, time
from xml.parsers.expat import ExpatError

from lxml import etree, builder

from twisted.python import util
from twisted.web import client, error as eweb

from eridanus import errors


def getqname(namespaces, qname):
    """
    Convert a namespaced text value element to James Clark's universal form.

    For example::

        (Assuming the prefix "p" corresponds to "http://my.ns")

        p:foo => {http://my.ns}foo

    @type namespaces: C{iterable} of C{(str, str)}
    @param namespaces: An iterable of C{(prefix, url)} pairs for all the
        relevant namespaces

    @type qname: C{str}
    @param qname: The XML namespace prefix to convert

    @rtype: C{str}
    @return: Converted namespace value
    """
    names = qname.split(':', 1)
    if len(names) < 2:
        return names[0]

    prefix, local = names
    for p, url in namespaces:
        if prefix == p:
            return '{%s}%s' % (url, local)
    raise ValueError('Unknown namespace prefix: "%s"' % (prefix,))


def fixqname(element, namespaces):
    element.text = getqname(reversed(namespaces), element.text)
    return element


def Namespace(ns, prefix=None):
    if prefix is not None:
        nsmap = {prefix: ns}
    else:
        nsmap = None
    return builder.ElementMaker(namespace=ns, nsmap=nsmap)

Local = builder.ElementMaker()


SOAP_ENV = Namespace('http://schemas.xmlsoap.org/soap/envelope/', 'SOAP-ENV')
SOAP_ENC = Namespace('http://schemas.xmlsoap.org/soap/encoding/', 'SOAP-ENC')
SOAP_WSDL = Namespace('http://schemas.xmlsoap.org/wsdl/soap/', 'SOAP')
XSI = Namespace('http://www.w3.org/1999/XMLSchema-instance', 'xsi')
XSI2001 = Namespace('http://www.w3.org/2001/XMLSchema-instance', 'xsi')
XSD = Namespace('http://www.w3.org/1999/XMLSchema', 'xsd')
WSDL = Namespace('http://schemas.xmlsoap.org/wsdl/', 'wsdl')

def parseSOAPFault(f):
    """
    Parse a SOAP fault response.

    @rtype: C{(unicode, unicode, unicode, unicode)}
    @return: (faultcode, faultstring, faultactor, detail)
    """
    events = ('end', 'start-ns', 'end-ns')
    namespaces = []
    err = f.value
    if err.status != '500':
        f.raiseException()

    data = StringIO.StringIO(err.response)
    try:
        for event, elem in etree.iterparse(data, events=events):
            if event == 'start-ns':
                namespaces.insert(0, elem)
            elif event == 'end-ns':
                namespaces.pop(0)
            else:
                if elem.tag == 'faultcode':
                    fixqname(elem, namespaces)
                elif elem.tag == SOAP_ENV._namespace + 'Fault':
                    return (elem.findtext('faultcode'),
                            elem.findtext('faultstring'),
                            elem.findtext('faultactor'),
                            elem.find('detail'))
    except ExpatError:
        pass

    raise errors.InvalidSOAPFault(unicode(err.response, 'ascii'))


class Surfactant(object):
    """
    Document-style SOAP service wrapper.

    Surfactant is meant to be used as a base class for wrapping a SOAP service
    that uses document-style methods, although it can also be used directly.

    @type creds: C{(username, password)}
    @cvar creds: Credentials to use for HTTP basic authorisation

    @type url: C{unicode} or C{str}
    @ivar url: The default service url
    """

    creds = None

    def __init__(self, url=None, creds=None):
        if url is not None:
            self.url = url

        if creds is not None:
            self.creds = creds

    def call(self, action, request):
        envelope = SOAP_ENV.Envelope(
            SOAP_ENV.Body(request,
                **{SOAP_ENV._namespace + 'encodingStyle': 'http://schemas.xmlsoap.org/soap/encoding/'}))

        data = etree.tostring(envelope, encoding='utf-8')
        file('soap_req.xml', 'wb').write(data)
        headers = {'content-type': 'text/xml; charset=utf-8',
                   'SOAPAction':   action}

        if self.creds is not None:
            username, password = self.creds
            auth = base64.b64encode('%s:%s' % (username, password))
            headers['Authorization'] = 'Basic %s' % (auth,)

        return client.getPage(self.url, postdata=data, method='POST', headers=headers, timeout=60 * 10
            ).addCallbacks(self.parseResult, self.parseFault)

    def parseResult(self, data):
        file('soap_res.xml', 'wb').write(data)
        envelope = etree.fromstring(data)
        return envelope.find(SOAP_ENV._namespace + 'Body')

    def parseFault(self, f):
        f.trap(eweb.Error)
        file('soap_err.xml', 'wb').write(f.value.response)
        faultcode, faultstring, faultactor, detail = parseSOAPFault(f)
        raise errors.SOAPFault(faultcode,
                               faultstring,
                               faultactor,
                               etree.tostring(detail, encoding='utf-8'))


def _uj(a, b):
    if a[-1] != '/':
        a = a + '/'
    return a + b


def _nsuri(NS):
    return NS._namespace[1:-1]


def simpleMethod(NS):
    def _deco(meth):
        methodName = meth.__name__
        def _soapMethod(self, *args, **kwargs):
            def _parse(body):
                return body[0]
            request = getattr(NS, methodName)
            request, parser = meth(self, request, *args, **kwargs)
            return self.call(_uj(_nsuri(NS), methodName), request).addCallback(_parse).addCallback(parser)
        return util.mergeFunctionMetadata(meth, _soapMethod)
    return _deco


def dateTime(t):
    ts = t.asStructTime()
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', ts)


def boolean(b):
    return ('false', 'true')[bool(b)]


def getXSIType(elem):
    xsiType = elem.get(XSI._namespace + 'type')
    if xsiType is None:
        xsiType = elem.get(XSI2001._namespace + 'type')

    if xsiType is not None:
        return xsiType

    raise ValueError(u'"%s" has no XSI type information' % (elem.tag,))


_xsiTypes = {
    'xsd:string': unicode,
    'xsd:int': int,
    }

def getValueFromXSIType(elem):
    xsiType = getXSIType(elem)
    return _xsiTypes[xsiType](elem.text)
