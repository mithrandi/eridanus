from itertools import chain

from nevow.url import URL

from eridanus.util import PerseverantDownloader
from eridanus.soap import getValueFromXSIType
from eridanusstd import errors, etree


API_URL = URL.fromString('http://duncanmackenzie.net/services/GetXboxInfo.aspx')


def getGamertagInfo(gamertag):
    """
    Retrieve information about a gamertag.

    @type gamertag: C{unicode}
    @param gamertag: The gamertag to retrieve an overview for

    @raises errors.InvalidGamertag: If C{gamertag} is invalid or unknown

    @rtype: C{Deferred} firing with a C{etree.Element}
    @return: A deferred that fires with the root node for the response document
    """
    def parseResponse((data, headers)):
        root = etree.fromstring(data)
        state = root.find('State')
        if state is None or state.text != 'Valid':
            raise errors.InvalidGamertag(u'%r is not a valid gamertag' % (gamertag,))

        return root

    url = API_URL.add('GamerTag', gamertag)
    return PerseverantDownloader(url).go(
        ).addCallback(parseResponse)


def _extractElems(parent, validElems):
    for elem in parent.getchildren():
        tag = elem.tag
        if tag in validElems:
            yield tag, getValueFromXSIType(elem, validElems[tag])


def getGamertagOverview(gamertag):
    """
    Get a general overview of the given gamertag.

    @type gamertag: C{unicode}
    @param gamertag: The gamertag to retrieve an overview for

    @rtype: C{Deferred} firing with a C{dict}
    @return: A deferred that fires with a dictionary filled with useful
        information
    """
    def extractGame(elem):
        return dict(chain(
            _extractElems(elem, {
                'LastPlayed':   u'xsd:dateTime',
                'Achievements': u'xsd:int',
                'GamerScore':   u'xsd:int'}),

            _extractElems(elem.find('Game'), {
                'Name':              u'xsd:string',
                'TotalAchievements': u'xsd:int',
                'TotalGamerScore':   u'xsd:int'})))


    def makeOverview(root):
        overview = dict(chain(
            _extractElems(root, {
                'Gamertag':   u'xsd:string',
                'GamerScore': u'xsd:int'}),

            _extractElems(root.find('PresenceInfo'), {
                'Info':       u'xsd:string',
                'Online':     u'xsd:boolean',
                'StatusText': u'xsd:string',
                'Title':      u'xsd:string'})))

        overview['RecentGames'] = [extractGame(e) for e in root.findall('RecentGames/XboxUserGameInfo')]
        return overview

    return getGamertagInfo(gamertag
        ).addCallback(makeOverview)
