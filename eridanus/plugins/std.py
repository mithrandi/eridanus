from zope.interface import classProvides

from twisted.plugin import IPlugin

from axiom.attributes import integer
from axiom.item import Item
from axiom.userbase import getAccountNames

from eridanus import errors
from eridanus.ieridanus import IEridanusPluginProvider
from eridanus.plugin import Plugin, usage

from eridanusstd import dict, timeutil, google, defertools


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

    @usage(u'install <pluginName>')
    def cmd_install(self, source, pluginName):
        """
        Install a plugin.
        """
        source.protocol.grantPlugin(None, pluginName)
        source.reply(u'Installed plugin "%s".' % (pluginName,))

    @usage(u'uninstall <pluginName>')
    def cmd_uninstall(self, source, pluginName):
        """
        Uninstall a plugin.
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
        descs = (u'\002%s\002: %s' % (db, desc) for db, desc in dict.getDicts())
        source.reply(u' '.join(descs))

    @usage(u'define <word> [database]')
    def cmd_define(self, source, word, database=None):
        """
        Define a word from a dictionary.

        Look <word> up in <database>, if <database> is not specified then all
        available dictionaries are consulted.
        """
        defs = (u'\002%s\002: %s' % (db, defn)
                for db, defn in dict.define(word, database))
        source.reply(u' '.join(defs))

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

        dt = timeutil.convert(timeString, timezoneName)
        source.reply(timeutil.format(dt, self.timeFormat))


class GooglePlugin(Item, Plugin):
    """
    Google services.
    """
    classProvides(IPlugin, IEridanusPluginProvider)
    schemaVersion = 1
    typeName = 'eridanus_plugins_google'

    name = u'google'
    pluginName = u'Google'

    dummy = integer()

    def websearch(self, source, terms, count):
        """
        Perform a Google web search.
        """
        def formatResults(results):
            for title, url in results:
                yield u'\002%s\002: <%s>;' % (title, url)

        def displayResults(formattedResults):
            source.reply(u' '.join(formattedResults))

        q = google.WebSearchQuery(terms)
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
