import random
from decimal import Decimal

from zope.interface import classProvides

from twisted.plugin import IPlugin

from axiom.attributes import integer, inmemory
from axiom.item import Item
from axiom.userbase import getAccountNames

from eridanus import errors, util as eutil, reparse
from eridanus.ieridanus import IEridanusPluginProvider
from eridanus.plugin import Plugin, usage, SubCommand

from eridanusstd import (dict, timeutil, google, defertools, urbandict,
    factoid, calc, fortune, imdb, xboxlive, yahoo, currency)


class APICommand(SubCommand):
    """
    Manage API keys.
    """
    name = u'api'

    @usage(u'get <apiName>')
    def cmd_get(self, source, apiName):
        """
        Get the API key for <apiName>.
        """
        apiKey = eutil.getAPIKey(self.parent.store, apiName)
        source.reply(apiKey)

    @usage(u'set <apiName> <key>')
    def cmd_set(self, source, apiName, key):
        """
        Set the API key for <apiName>.
        """
        apiKey = eutil.setAPIKey(self.parent.store, apiName, key)
        source.reply(u'Set key for "%s".' % (apiName,))


class AdminPlugin(Item, Plugin):
    """
    Provides access to various admin functions.

    Which includes things such as installing/uninstalling plugins,
    joining/leaving channels and ignoring users.
    """
    classProvides(IPlugin, IEridanusPluginProvider)
    schemaVersion = 1
    typeName = 'eridanus_plugins_admin'

    name = u'admin'
    pluginName = u'Admin'

    dummy = integer()

    cmd_api = APICommand()

    @usage(u'install <pluginName>')
    def cmd_install(self, source, pluginName):
        """
        Globally install a plugin.
        """
        source.protocol.grantPlugin(None, pluginName)
        source.reply(u'Installed plugin "%s".' % (pluginName,))

    @usage(u'uninstall <pluginName>')
    def cmd_uninstall(self, source, pluginName):
        """
        Uninstall a globally installed plugin.
        """
        if pluginName == self.pluginName:
            msg = u'Can\'t uninstall "%s".' % (pluginName,)
        else:
            source.protocol.revokePlugin(None, pluginName)
            msg = u'Uninstalled plugin "%s".' % (pluginName,)
        source.reply(msg)

    @usage(u'grant <nickname> <pluginName>')
    def cmd_grant(self, source, nickname, pluginName):
        """
        Grant an authenticated <nickname> access to <pluginName>.
        """
        source.protocol.grantPlugin(nickname, pluginName)
        source.reply(u'Granted "%s" with access to "%s".' % (nickname, pluginName))

    @usage(u'revoke <nickname> <pluginName>')
    def cmd_revoke(self, source, nickname, pluginName):
        """
        Revoke <nickname>'s access to <pluginName>.
        """
        source.protocol.revokePlugin(nickname, pluginName)
        source.reply(u'Revoked access to "%s" from "%s".' % (pluginName, nickname))

    @usage(u'join <channel>')
    def cmd_join(self, source, name):
        """
        Join <channel>.
        """
        source.join(name)

    @usage(u'part [channel]')
    def cmd_part(self, source, name=None):
        """
        Part the current channel or <channel>.
        """
        source.part(name)

    @usage(u'ignores')
    def cmd_ignores(self, source):
        """
        Show the current ignore list.
        """
        # XXX: HACK: abstract this away
        ignores = source.protocol.config.ignores
        if ignores:
            msg = u', '.join(ignores)
        else:
            msg = u'Ignore list is empty.'
        source.reply(msg)

    @usage(u'ignore <usermask>')
    def cmd_ignore(self, source, usermask):
        """
        Ignore input from users matching <usermask>.

        If <usermask> is a partial mask then it will be normalized. e.g.
        "bob" becomes "bob!*@*".
        """
        mask = source.ignore(usermask)
        if mask is not None:
            msg = u'Ignoring "%s".' % (mask,)
        else:
            msg = u'Already ignoring "%s".' % (usermask,)
        source.reply(msg)

    @usage(u'unignore <usermask>')
    def cmd_unignore(self, source, usermask):
        """
        Stop ignoring input from <usermask>.

        If <usermask> is a partial mask then it will be normalized. e.g.
        "bob" becomes "bob!*@*".
        """
        removedIgnores = source.unignore(usermask)
        if removedIgnores is not None:
            msg = u'Stopped ignoring: ' + u', '.join(removedIgnores)
        else:
            msg = u'No ignores matched "%s".' % (usermask,)
        source.reply(msg)

    @usage(u'plugins')
    def cmd_plugins(self, source):
        """
        List plugins available to install.

        Not all plugins should be installed with the `install` command, plugins
        that end with the word `Admin` should be granted (`admin grant`) to a
        particular user instead of installed for the whole world.
        """
        msg = u', '.join(sorted(source.protocol.getAvailablePlugins(source.user.nickname)))
        if not msg:
            msg = u'No available plugins'
        source.reply(msg)


class AuthenticatePlugin(Item, Plugin):
    """
    Authentication related commands.
    """
    classProvides(IPlugin, IEridanusPluginProvider)
    schemaVersion = 1
    typeName = 'eridanus_plugins_authenticate'

    name = u'auth'
    pluginName = u'Authenticate'

    dummy = integer()

    @usage(u'login <password>')
    def cmd_login(self, source, password):
        """
        Authenticate yourself to the service.
        """
        def loginDone(dummy):
            source.reply(u'Successfully authenticated.')

        return source.protocol.login(source.user.nickname, password
            ).addCallbacks(loginDone)

    @usage(u'logout')
    def cmd_logout(self, source):
        """
        Unauthenticate yourself to the service.
        """
        if source.protocol.logout(source.user.nickname):
            source.reply(u'Unauthenticated.')

    @usage(u'whoami')
    def cmd_whoami(self, source):
        """
        Find out who you are authenticated as.
        """
        nickname = source.user.nickname
        try:
            avatar = source.protocol.getAuthenticatedAvatar(nickname)
            username, domain = getAccountNames(avatar.store).next()
            msg = u'Authenticated as "%s@%s".' % (username, domain)
        except errors.AuthenticationError:
            msg = u'Not authenticated.'
        source.reply(msg)


class TopicPlugin(Item, Plugin):
    """
    Manage channel topics in a structured fashion.
    """
    classProvides(IPlugin, IEridanusPluginProvider)
    schemaVersion = 1
    typeName = 'eridanus_plugins_topic'

    name = u'topic'
    pluginName = u'Topic'

    dummy = integer()

    # XXX: should be a channel config variable
    separator = u' | '

    def getTopics(self, source):
        def splitTopic(topic):
            return [part for part in topic.split(self.separator) if part]

        return source.getTopic(
            ).addCallback(splitTopic)

    def setTopics(self, source, topics):
        topic = self.separator.join(topics)

        topicLength = len(topic)
        maxTopicLength = source.maxTopicLength
        if maxTopicLength is not None and topicLength > maxTopicLength:
            raise ValueError(u'Topic length (%d) would exceed maximum topic length (%d)' % (topicLength, maxTopicLength))

        source.setTopic(topic)

    @usage(u'add <topic>')
    def cmd_add(self, source, *topic):
        """
        Add the sub-topic <topic> to the channel topic.
        """
        def addTopic(topics):
            subtopic = u' '.join(topic)
            topics.append(subtopic)
            self.setTopics(source, topics)

        return self.getTopics(source
            ).addCallback(addTopic)

    @usage(u'remove <index>')
    def cmd_remove(self, source, index):
        """
        Remove the sub-topic at <index> from the channel topic.

        <index> starts from 0 and may be negative to represent elements from
        the end of the topic.
        """
        def removeTopic(topics):
            if topics:
                try:
                    topics.pop(int(index))
                    self.setTopics(source, topics)
                except IndexError:
                    # No more topics left to remove.
                    pass

        return self.getTopics(source
            ).addCallback(removeTopic)


class DictPlugin(Item, Plugin):
    """
    Dictionary functionality.

    Provides commands for performing tasks such  as defining words and
    checking the spelling of a word.
    """
    classProvides(IPlugin, IEridanusPluginProvider)
    schemaVersion = 1
    typeName = 'eridanus_plugins_dict'

    name = u'dict'
    pluginName = u'Dict'

    dummy = integer()

    @usage(u'dicts')
    def cmd_dicts(self, source):
        """
        List available dictionaries.
        """
        def gotDicts(dicts):
            descs = (u'\002%s\002: %s' % (db, desc) for db, desc in dicts)
            source.reply(u' '.join(descs))

        return dict.getDicts().addCallback(gotDicts)

    @usage(u'define <word> [database]')
    def cmd_define(self, source, word, database=None):
        """
        Define a word from a dictionary.

        Look <word> up in <database>, if <database> is not specified then all
        available dictionaries are consulted.
        """
        def gotDefs(result):
            defs = (u'\002%s\002: %s' % (db, defn)
                    for db, defn in result)
            source.reply(u' '.join(defs))

        return dict.define(word, database).addCallback(gotDefs)

    @usage(u'spell <word> [language]')
    def cmd_spell(self, source, word, language=None):
        """
        Check the spelling of a word.

        If <word> is spelt incorrectly, a list of suggestions are given.
        <language> defaults to 'en_GB'.
        """
        if language is None:
            language = 'en_GB'

        suggestions = dict.spell(word, language)
        if suggestions is None:
            msg = u'"%s" is spelled correctly.' % (word,)
        else:
            msg = u'Suggestions: ' + u', '.join(suggestions)
        source.reply(msg)


class TimePlugin(Item, Plugin):
    """
    Time-related functions.
    """
    classProvides(IPlugin, IEridanusPluginProvider)
    schemaVersion = 1
    typeName = 'eridanus_plugins_time'

    name = u'time'
    pluginName = u'Time'

    dummy = integer()

    # XXX: should be a network config variables probably
    timeFormat = '%a, %Y-%m-%d %H:%M:%S %Z (%z)'
    defaultTimezoneName = u'Africa/Johannesburg'

    @usage(u'now [timezoneName]')
    def cmd_now(self, source, timezoneName=None):
        """
        Show the current time in the default timezone, or <timezoneName>.
        """
        if timezoneName is None:
            timezoneName = self.defaultTimezoneName

        dt = timeutil.now(timezoneName)
        source.reply(timeutil.format(dt, self.timeFormat))

    @usage(u'convert <timeString> [timezoneName]')
    def cmd_convert(self, source, timeString, timezoneName=None):
        """
        Convert <timeString> to the default timezone, or <timezoneName>.

        <timeString> should be a valid time string, the format of which is
        fairly flexible but care should be taken to quote <timeString> if it
        includes spaces. e.g. time convert "10:00 JST" Europe/Paris
        """
        if timezoneName is None:
            timezoneName = self.defaultTimezoneName

        dt = timeutil.convert(timeString, timezoneName, self.defaultTimezoneName)
        source.reply(timeutil.format(dt, self.timeFormat))


class GooglePlugin(Item, Plugin):
    """
    Google services.

    It is recommended you set an API key for `googleAjaxSearch`.
    """
    classProvides(IPlugin, IEridanusPluginProvider)
    schemaVersion = 1
    typeName = 'eridanus_plugins_google'

    name = u'google'
    pluginName = u'Google'

    dummy = integer()

    apiKey = inmemory()

    def activate(self):
        self.apiKey = eutil.getAPIKey(self.store, u'googleAjaxSearch', default=None)

    def websearch(self, source, terms, count):
        """
        Perform a Google web search.
        """
        def formatResults(results):
            for title, url in results:
                yield u'\002%s\002: <%s>;' % (title, url)

        def displayResults(formattedResults):
            source.reply(u' '.join(formattedResults))

        q = google.WebSearchQuery(terms, apiKey=self.apiKey)
        return defertools.slice(q.queue, count
            ).addCallback(formatResults
            ).addCallback(displayResults)

    @usage(u'search <term> [term ...]')
    def cmd_search(self, source, term, *terms):
        """
        Perform a Google web search.
        """
        terms = [term] + list(terms)
        return self.websearch(source, terms, 4)

    @usage(u'lucky <term> [term ...]')
    def cmd_lucky(self, source, term, *terms):
        """
        Perform an "I'm feeling lucky" Google web search.
        """
        terms = [term] + list(terms)
        return self.websearch(source, terms, 1)


class UrbanDict(Item, Plugin):
    """
    Urban Dictionary.

    An API key for `urbandict` is required in order for this plugin to work.
    """
    classProvides(IPlugin, IEridanusPluginProvider)
    schemaVersion = 1
    typeName = 'eridanus_plugins_urbandict'

    name = u'urbandict'
    pluginName = u'UrbanDict'

    dummy = integer()

    S = inmemory()

    def activate(self):
        apiKey = eutil.getAPIKey(self.store, u'urbandict')
        self.S = urbandict.UrbanDictService(apiKey)

    @usage(u'define <term>')
    def cmd_define(self, source, term):
        """
        Get all definitions for <term> on Urban Dictionary.
        """
        def formatResults(results):
            for i, result in enumerate(results):
                word = result[u'word']
                # XXX: this should be a paginated/multiline output
                dfn = u' '.join(result[u'definition'].splitlines())
                yield u'\002%d. %s\002: %s;' % (i + 1, word, dfn)

        def displayResults(formattedResults):
            source.reply(u' '.join(formattedResults))

        return self.S.lookup(term
            ).addCallback(formatResults
            ).addCallback(displayResults)

    @usage(u'verifyKey')
    def cmd_verifykey(self, source):
        """
        Verify that the currently set API key is valid.
        """
        def gotResult(isValid):
            result = (u'is not', 'is')[isValid]
            msg = u'The API key %s valid.' % (result,)
            source.reply(msg)

        return self.S.verify_key().addCallback(gotResult)


class FactoidPlugin(Item, Plugin):
    classProvides(IPlugin, IEridanusPluginProvider)
    schemaVersion = 1
    typeName = 'eridanus_plugins_factoid'

    name = u'factoid'
    pluginName = u'Factoid'

    dummy = integer()

    @usage(u'list <key>')
    def cmd_list(self, source, key):
        """
        List all factoids for <key>.
        """
        def formatFactoid(fact, n):
            return u'\002%d\002: %s' % (n, fact.value)

        factoids = factoid.getFactoids(self.store, key)
        factoidText = (eutil.truncate(formatFactoid(fact, i), 40)
                       for i, fact in enumerate(factoids))
        msg = u'  '.join(factoidText)
        source.reply(msg)

    @usage(u'get <key> [index]')
    def cmd_get(self, source, key, index=None):
        """
        Retrieve a factoid for <key>.

        If <index> is omitted, a random factoid for <key> is retrieved.
        """
        if index is not None:
            fac = factoid.getFactoid(self.store, key, int(index))
        else:
            factoids = list(factoid.getFactoids(self.store, key))
            fac = random.sample(factoids, 1)[0]
        source.reply(u'%s \002is\002 %s' % (fac.key, fac.value))

    @usage(u'set <key> <value>')
    def cmd_set(self, source, key, value):
        """
        Replace all factoids for <key> with <value>.
        """
        factoid.setFactoid(self.store, source.user.nickname, key, value)
        source.reply(u'Set factoid for "%s".' % (key,))

    @usage(u'add <key> <value>')
    def cmd_add(self, source, key, value):
        """
        Add a new factoid for <key>.
        """
        factoid.createFactoid(self.store, source.user.nickname, key, value)
        source.reply(u'Added a factoid for "%s".' % (key,))

    @usage(u'delete <key> <index>')
    def cmd_delete(self, source, key, index):
        """
        Delete a factoid for <key>.

        If `*` is supplied for <index>, all factoids for <key> are deleted.
        """
        if index == u'*':
            index = None
            msg = u'Deleted all factoids for "%s".' % (key,)
        else:
            index = int(index)
            msg = u'Deleted %d for factoid "%s".' % (index, key)
        factoid.deleteFactoid(self.store, key, index)
        source.reply(msg)

    @usage(u'replace <key> <index> <value>')
    def cmd_replace(self, source, key, index, value):
        """
        Replace a specific factoid for <key>.
        """
        index = int(index)
        factoid.replaceFactoid(self.store,
                               source.user.nickname,
                               key,
                               index,
                               value)
        source.reply(u'Replaced %d for factoid "%s".' % (index, key))

    @usage(u'change <key> <regexp>')
    def cmd_change(self, source, key, regexp):
        """
        Change factoids for <key> based on a regular expression.

        <regexp> should be of the form `s/foo/bar/`, `g` and `i` flags are
        accepted.  If <regexp> matches multiple factoids for <key>, the global
        (`g`) flag must be specified.
        """
        subst = reparse.parseRegex(regexp)
        numChanged = factoid.changeFactoids(self.store,
                                            source.user.nickname,
                                            key,
                                            subst)
        source.reply(u'Changed %d factoid(s).' % (numChanged,))


# XXX: This really should not be a command itself but until some kind of
# command aliasing is available this is the most convenient.
class CalcPlugin(Item, Plugin):
    """
    calc <\002expression\002> [...] -- Evaluate a simple mathematical expression.
    """
    classProvides(IPlugin, IEridanusPluginProvider)
    schemaVersion = 1
    typeName = 'eridanus_plugins_calc'

    name = u'calc'
    pluginName = u'Calc'

    dummy = integer()

    expn = inmemory()

    def locateCommand(self, params):
        self.expn = u' '.join(params)
        return self, []

    def invoke(self, source):
        source.reply(calc.evaluate(self.expn))


class FortunePlugin(Item, Plugin):
    classProvides(IPlugin, IEridanusPluginProvider)
    schemaVersion = 1
    typeName = 'eridanus_plugins_fortune'

    name = u'fortune'
    pluginName = u'Fortune'

    dummy = integer()

    def outputFortunes(self, fortunes, source):
        fortunes = (u'\002%s\002: %s' % (db, u' '.join(msg))
                    for db, msg in fortunes)
        source.reply(u' '.join(fortunes))

    def fortune(self, source, **kw):
        if kw.get('db') == u'*':
            kw['db'] = None

        return fortune.fortune(**kw).addCallback(self.outputFortunes, source)

    @usage(u'short [db] [match]')
    def cmd_short(self, source, db=u'*', match=None):
        """
        Retrieve a short fortune.

        <db> can be "*" to match all available fortune databases.
        """
        return self.fortune(source,
                            short=True,
                            db=db,
                            match=match)

    @usage(u'fortune [db] [match]')
    def cmd_fortune(self, source, db=u'*', match=None):
        """
        Retrieve a fortune.

        <db> can be "*" to match all available fortune databases.
        """
        return self.fortune(source,
                            db=db,
                            match=match)


class IMDBPlugin(Item, Plugin):
    classProvides(IPlugin, IEridanusPluginProvider)
    schemaVersion = 1
    typeName = 'eridanus_plugins_imdb'

    name = u'imdb'
    pluginName = u'IMDB'

    dummy = integer()

    @usage(u'search <title>')
    def cmd_search(self, source, title):
        """
        Search IMDB for artifacts whose titles match <title>.
        """
        def gotResults(results):
            for name, url, id in results:
                yield u'\002%s\002: <%s>;' % (name, url)

        def outputResults(results):
            source.reply(u' '.join(results))

        # XXX: Exact and the artifacts to search should maybe be configurable.
        # XXX: On the other hand, IMDB's search sucks badly, something more
        # useful should be written on top of the search.
        return imdb.searchByTitle(title, exact=False
            ).addCallback(gotResults
            ).addCallback(outputResults)

    @usage(u'plot <id>')
    def cmd_plot(self, source, id):
        """
        Retrieve the plot information for an IMDB title with <id>.
        """
        def gotInfo(info):
            source.reply(u'\002%(title)s (%(year)s)\002: %(summary)s' % info)

        return imdb.getInfoByID(id
            ).addCallback(gotInfo)


class XboxLivePlugin(Item, Plugin):
    classProvides(IPlugin, IEridanusPluginProvider)
    schemaVersion = 1
    typeName = 'eridanus_plugins_xboxliveplugin'

    name = u'xbl'
    pluginName = u'XboxLive'

    dummy = integer()

    @usage(u'gamertag <gamertag>')
    def cmd_gamertag(self, source, gamertag):
        """
        Display a brief gamertag for <gamertag>.
        """
        def gotOverview(overview):
            def _getFields():
                yield u'Gamertag', overview['Gamertag']
                yield u'Gamerscore', overview['GamerScore']
                recentGames = overview['RecentGames']
                if recentGames:
                    game = recentGames[0]
                    yield u'Last played', u'%s (%s/%s gamerscore from %s/%s achievements)' % (
                        game['Name'], game['GamerScore'], game['TotalGamerScore'],
                        game['Achievements'], game['TotalAchievements'])

            msg = u'; '.join(u'\002%s\002: %s' % (key, value) for key, value in _getFields())
            source.reply(msg)

        return xboxlive.getGamertagOverview(gamertag
            ).addCallback(gotOverview)


class CurrencyPlugin(Item, Plugin):
    classProvides(IPlugin, IEridanusPluginProvider)
    schemaVersion = 1
    typeName = 'eridanus_plugins_currencyplugin'

    name = u'currency'
    pluginName = u'Currency'

    dummy = integer()

    @usage(u'convert <amount> <from> <to>')
    def cmd_convert(self, source, amount, currencyFrom, currencyTo):
        """
        Convert <amount> from currency <from> to currency <to>.

        Currencies should be specified using their 3-digit currency codes.
        """
        amount = Decimal(amount)
        currencyFrom = currencyFrom.upper()
        currencyTo = currencyTo.upper()

        def convert((rate, tradeTime)):
            convertedAmount = rate * amount
            source.reply(unicode(convertedAmount))

        return yahoo.currencyExchange(currencyFrom, currencyTo
            ).addCallback(convert)

    @usage(u'name <code>')
    def cmd_name(self, source, code):
        """
        Get the currency name from a currency code.
        """
        code = code.upper()
        name = currency.currencyNames.get(code)
        if name is None:
            raise errors.InvalidCurrency(u'%r is not a recognised currency code' % (code,))

        source.reply(name)
