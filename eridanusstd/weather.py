import pytz
from datetime import datetime

from epsilon.extime import Time
from epsilon.structlike import record

from nevow.url import URL

from eridanus import util
from eridanusstd import etree


class WundergroundConditions(record('location observationTime condition temperature humidity pressure windSpeed windDirection windChill dewPoint heatIndex')):
    @classmethod
    def fromElement(cls, node):
        location = node.findtext('display_location/full')
        observationTime = Time.fromRFC2822(node.findtext('observation_time_rfc822'))
        condition = node.findtext('weather')
        temp = int(node.findtext('temp_c'))
        humidity = node.findtext('relative_humidity')
        pressure = node.findtext('pressure_string')
        windSpeed = int(node.findtext('wind_mph')) * 1.609344
        windDirection = node.findtext('wind_dir')
        dewPoint = int(node.findtext('dewpoint_c'))

        heatIndex = node.findtext('heat_index_c')
        if heatIndex is None or heatIndex == 'NA':
            heatIndex = None
        else:
            heatIndex = int(heatIndex)

        windChill = node.findtext('windchill_c')
        if windChill is None or windChill == 'NA':
            windChill = None
        else:
            windChill = int(windChill)

        return cls(location=location,
                   observationTime=observationTime,
                   condition=condition,
                   temperature=temp,
                   humidity=humidity,
                   pressure=pressure,
                   windSpeed=windSpeed,
                   windDirection=windDirection,
                   windChill=windChill,
                   dewPoint=dewPoint,
                   heatIndex=heatIndex)

    @property
    def display(self):
        def temp(v):
            return u'%d\N{DEGREE SIGN}C' % (v,)

        def attrs():
            if self.temperature is not None:
                yield u'Temperature', temp(self.temperature)
            if self.condition:
                yield u'Conditions', self.condition
            if self.humidity:
                yield u'Humidity', self.humidity
            if self.dewPoint:
                yield u'Dew point', temp(self.dewPoint)
            if self.pressure:
                yield u'Pressure', self.pressure
            if self.windSpeed and self.windDirection:
                yield u'Wind', u'%s at %0.2fkm/h' % (self.windDirection, self.windSpeed)
            if self.windChill:
                yield u'Wind chill', temp(self.windChill)

        timestring = unicode(self.observationTime.asDatetime(tzinfo=pytz.utc).strftime('%H:%M %Z on %d %B %Y'))
        params = u'; '.join(u'\002%s\002: %s' % (key, value) for key, value in attrs())
        return u'In %s at %s: %s' % (self.location, timestring, params)


class Wunderground(object):
    API_ROOT = URL.fromString('http://api.wunderground.com/auto/wui/geo')

    @classmethod
    def current(cls, query):
        url = cls.API_ROOT.child('WXCurrentObXML').child('index.xml').add('query', query)
        return util.PerseverantDownloader(url).go(
            ).addCallback(lambda (data, headers): etree.fromstring(data)
            ).addCallback(WundergroundConditions.fromElement)
