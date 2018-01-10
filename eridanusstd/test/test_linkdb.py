from StringIO import StringIO

from twisted.trial import unittest
from twisted.python.filepath import FilePath
from twisted.web.http_headers import Headers

from eridanus import util
from eridanusstd import linkdb



class MetadataExtractionTests(unittest.TestCase):
    """
    Tests for metadata extraction for the LinkDB plugin.
    """
    def setUp(self):
        self.pngStream = StringIO(
            '\x89\x50\x4e\x47\x0d\x0a\x1a\x0a\x00\x00\x00\x0d\x49\x48\x44\x52'
            '\x00\x00\x01\x00\x00\x00\x01\x00\x08\x06\x00\x00\x00\x5c\x72\xa8'
            '\x66\x00\x00\x00\x09\x70\x48\x59\x73\x00\x00\x0b\x13\x00\x00\x0b'
            '\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\x20\x63\x48\x52\x4d\x00\x00'
            '\x7a\x2d\x00\x00\x80\x95\x00\x00\xf8\xd6\x00\x00\x88\x52\x00\x00'
            '\x71\x45\x00\x00\xea\x65\x00\x00\x39\x09\x00\x00\x21\xfb\xf4\x4e'
            '\xe5\x40\x00\x01\x60\xd4\x49\x44\x41\x54\x78\xda\xec\xfd\x67\x94'
            '\xad\xe9\x75\xdf\x89\xfd\x9e\xf0\xa6\x13\x2b\xd7\xad\x9b\xfb\x86'
            '\xbe\x1d\x6e\xe7\x46\xa3\x1b\x0d\x10\x04\x08\x10\x24\x41\x0e\xc5'
            '\x30\xa2\xd2\x88\xa2\x97\x46\xb2\x24\x7b\x79\xd9\xe3\x30\xcb\xf6'
            '\x5a\xa6\xe7\x83\xfd\x61\xec\xf1\x8c\x47\xb2\x86\x1a\xd9\x4a\x5e'
            '\x1e\x51\x62\x04\x48\x02\x22\x40\x04\x22\x87\xce\xf9\xe6\x5c\x39'
            '\x9d\xf4\xa6\x27\xf8\xc3\xf3\x56\xf5\xed\x46\x27\x90\xfa\x30\x22'
            '\xfa\xf4\xaa\x7b\xfb\x56\x9d\x3a\x55\xe7\x9c\x77\xef\x67\xef\xff'
            '\xfe\xff\xff\x5b\x0c\xaf\x6f\xfa\x48\x28\xf0\x12\x90\x80\x43\x78'
            '\x10\x4a\xe2\xbd\x07\x40\x08\x81\xf7\x1e\xe7\xdc\xfe\xe7\xa4\xf0'
            '\x78\x3c\xce\x0a\x24\x0a\x2d\x04\xb5\xa9\x29\x6c\xc9\xd8\x95\xb8')


    def test_extractImageMetadata(self):
        """
        When the Python Imaging Library is available, image metadata is
        extracted from a valid image stream.
        """
        if linkdb.PIL is None:
            raise unittest.SkipTest('PIL is not available')

        info = dict(linkdb._extractImageMetadata(self.pngStream))
        self.assertEquals({
            u'dimensions': u'256x256'}, info)


    def test_extractBogusImageMetadata(self):
        """
        Attempting to extract metadata from a bogus image stream results in no
        metadata being extracted.
        """
        if linkdb.PIL is None:
            raise unittest.SkipTest('PIL is not available')

        info = dict(linkdb._extractImageMetadata(StringIO('boo')))
        self.assertEquals({}, info)


    def test_noPIL(self):
        """
        If the Python Imaging Library is missing, no image metadata is
        extracted.
        """
        self.patch(linkdb, 'PIL', None)
        info = dict(linkdb._extractImageMetadata(self.pngStream))
        self.assertEquals({}, info)


    def test_buildMetadata(self):
        """
        Metadata for an HTTP resource is extracted from the HTTP headers and
        any available resource data.
        """
        data = self.pngStream.read()

        md = dict(linkdb._buildMetadata(data, Headers()))
        self.assertEquals({}, md)

        md = dict(linkdb._buildMetadata(data, Headers({
            'content-type': ['text/plain']})))
        self.assertEquals({
            u'contentType': u'text/plain'}, md)

        md = dict(linkdb._buildMetadata(
            data, Headers({'content-range': ['bytes 10240/20480']})))
        self.assertEquals({
            u'size': util.humanReadableFileSize(20480)}, md)


    def test_buildMetadataForImage(self):
        """
        When an HTTP resource has an image MIME type,
        L{eridanusstd.linkdb._extractImageMetadata} is called to process the
        resource.
        """
        data = self.pngStream.read()

        self.patch(
            linkdb, '_extractImageMetadata', lambda stream: [(u'foo', u'bar')])
        md = dict(linkdb._buildMetadata(
            data, Headers({'content-type': ['image/png']})))
        self.assertEquals({
            u'contentType': u'image/png',
            u'foo': u'bar'}, md)



class TitleExtractionTests(unittest.TestCase):
    """
    Tests for title extraction in L{eridanusstd.linkdb}.
    """
    def setUp(self):
        self.path = FilePath(__file__)


    def test_extractTitle(self):
        data = self.path.sibling('index.html').open().read()
        self.assertEquals(
            linkdb._extractTitle(data),
            u'Google')
