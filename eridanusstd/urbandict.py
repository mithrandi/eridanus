"""
Implementation for retrieving Urban Dictionary information (definitions, etc.)
via the SOAP interface.

The following documentation may be useful::

    http://api.urbandictionary.com/soap
    http://wiki.urbandictionary.com/
"""
from eridanus import soap


URBANDICT = soap.Namespace('urn:UrbanSearch')


class UrbanDictService(soap.Surfactant):
    """
    Client for communicating with Urban Dictionary's SOAP interface.

    @type apiKey: C{unicode}
    @ivar apiKey: A valid Urban Dictionary API key
    """
    url = 'http://api.urbandictionary.com/soap'

    def __init__(self, apiKey, **kw):
        """
        Initialise the service.

        @type apiKey: C{unicode}
        @param apiKey: A valid Urban Dictionary API key, use
            L{UrbanDictService.verify_key} to check the validity of this key
        """
        super(UrbanDictService, self).__init__(**kw)
        self.apiKey = apiKey

    def parseLookupResponse(self, response):
        """
        Convert a C{lookup} response into an iterable of C{dict}s.
        """
        def parseItem(elem):
            for child in item.getchildren():
                value = soap.getValueFromXSIType(child)
                yield child.tag, value

        for item in response.findall('return/item'):
            yield dict(parseItem(item))

    @soap.simpleMethod(URBANDICT)
    def lookup(self, request, term):
        """
        Lookup C{term} on Urban Dictionary.
        """
        kw = {soap.XSI + 'type': 'xsd:string'}
        request = request(URBANDICT.key(self.apiKey, **kw),
                          URBANDICT.term(term, **kw))
        return request, lambda response: self.parseLookupResponse(response)

    @soap.simpleMethod(URBANDICT)
    def verify_key(self, request):
        """
        Verify C{self.apiKey}.
        """
        kw = {soap.XSI + 'type': 'xsd:string'}
        request = request(URBANDICT.key(self.apiKey, **kw))
        return request, lambda response: soap.getValueFromXSIType(response.find('return'))
