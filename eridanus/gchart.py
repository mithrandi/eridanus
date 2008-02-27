import string
import fpformat

from nevow import url


# Data encoding types
SIMPLE = 's'
TEXT = 't'
EXTENDED = 'e'


class DataEncoding(object):
    setSeparator = None
    valueSeparator = None
    missingValue = None
    maxRange = None

    def __init__(self, data):
        self.data = data

    def normalize(self):
        return ((v / float(max(dataSet)) * self.maxRange for v in dataSet) for dataSet in self.data)

    def _mapValue(self, value):
        if value is None:
            return self.missingValue
        return self.mapValue(value)

    def mapValue(self, value):
        raise NotImplementedError()

    def encode(self):
        return self.setSeparator.join(self.valueSeparator.join(self._mapValue(v) for v in dataSet) for dataSet in self.normalize())


class SimpleDataEncoding(DataEncoding):
    setSeparator = ','
    valueSeparator = ''
    missingValue = '_'
    dataMap = string.uppercase + string.lowercase + string.digits
    maxRange = len(dataMap) - 1

    def mapValue(self, value):
        return self.dataMap[int(value)]


class TextDataEncoding(DataEncoding):
    setSeparator = '|'
    valueSeparator = ','
    missingValue = '-1'
    maxRange = 100

    def mapValue(self, value):
        return fpformat.fix(value, 1)


class ExtendedDataEncoding(DataEncoding):
    setSeparator = ','
    valueSeparator = ''
    missingValue = '__'
    dataMap = string.uppercase + string.lowercase + string.digits + '-.'
    maxRange = len(dataMap) - 1

    def mapValue(self, value):
        l = len(self.dataMap)
        return self.dataMap[int(value / l)] + self.dataMap[int(value % l)]


def Color(r, g, b, a=None):
    c = chr(r) + chr(g) + chr(b)
    if a is not None:
        c += chr(a)
    return c.encode('hex')


class Chart(object):
    API = 'http://chart.apis.google.com/chart'

    chartType = None
    dataEncodingTypes = {
        SIMPLE: SimpleDataEncoding,
        TEXT: TextDataEncoding,
        EXTENDED: ExtendedDataEncoding}

    def __init__(self, size, data, title=None, legends=None, dataColors=None, dataEncoding=SIMPLE):
        super(Chart, self).__init__()
        self.size = size
        self.data = data
        self.title = title
        self.legends = legends
        self.dataColors = dataColors
        self.dataEncoding = dataEncoding

    def encodeData(self):
        return self.dataEncoding + ':' + self.dataEncodingTypes[self.dataEncoding](self.data).encode()

    def encodeSize(self):
        return '%sx%s' % (self.size)

    def encodeTitle(self):
        return self.title.replace('\n', '|')

    def encodeLegends(self):
        return '|'.join(self.legends)

    def encodeDataColors(self):
        return ','.join(self.dataColors)

    def getParams(self):
        params = {'cht': self.chartType,
                  'chs': self.encodeSize(),
                  'chd': self.encodeData()}
        if self.title is not None:
            params['chtt'] = self.encodeTitle()
        if self.legends is not None:
            params['chdl'] = self.encodeLegends()
        if self.dataColors:
            params['chco'] = self.encodeDataColors()
        return params

    @property
    def url(self):
        u = url.URL.fromString(self.API)

        for param, value in self.getParams().iteritems():
            if value is not None:
                u = u.add(param, value)

        return u


class Pie(Chart):
    chartType = 'p'

    def __init__(self, labels=None, **kw):
        super(Pie, self).__init__(**kw)
        self.labels = labels

    def encodeLabels(self):
        labels = self.labels
        if labels is None:
            return None

        return '|'.join(labels)

    def getParams(self):
        params = super(Pie, self).getParams()
        params.update({
            'chl': self.encodeLabels()})
        return params


class Pie3D(Chart):
    chartType = 'p3'


if __name__ == '__main__':
    size = (900, 300)
    data = [
        [40, 74, 124, 5]]

    labels = ['Foo', 'Bar', 'Baz', 'Quux']
    c = Pie(size=size, data=data, labels=labels)
    print str(c.url)
