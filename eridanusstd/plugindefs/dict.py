from zope.interface import classProvides

from twisted.plugin import IPlugin

from axiom.attributes import integer
from axiom.item import Item

from eridanus.ieridanus import IEridanusPluginProvider
from eridanus.plugin import Plugin, usage, rest

from eridanusstd import dict



class Dict(Item, Plugin):
    """
    Dictionary functionality.

    Provides commands for performing tasks such  as defining words and
    checking the spelling of a word.
    """
    classProvides(IPlugin, IEridanusPluginProvider)
    typeName = 'eridanus_plugins_dict'

    dummy = integer()


    def formatResults(results):
        """
        Format dictionary definition results.
        """
        formatted = (u'\002%s\002: %s' % (db, defn) for db, defn in results)
        return u' '.join(formatted)


    def suggest(self, word, language):
        """
        Suggest spellings for a word in a specific language.
        """
        suggestions = dict.spell(word, language)
        if suggestions is None:
            msg = u'"%s" is spelled correctly.' % (word,)
        else:
            msg = u'Suggestions: ' + u', '.join(suggestions)
        return msg

    @usage(u'dicts')
    def cmd_dicts(self, source):
        """
        List available dictionaries.
        """
        def gotDicts(dicts):
            descs = (u'\002%s\002: %s' % (db, desc) for db, desc in dicts)
            source.reply(u' '.join(descs))

        return dict.getDicts().addCallback(gotDicts)


    @rest
    @usage(u'define <word>')
    def cmd_define(self, source, word):
        """
        Define a word from a dictionary.

        All available dictionaries are consulted, in order to only look up a
        word in a specific dictionary see the "definefor" command.
        """
        return dict.define(word, None
            ).addCallback(self.formatResults
            ).addCallback(source.reply)


    @rest
    @usage(u'definefor <database> <word>')
    def cmd_definefor(self, source, database, word):
        """
        Define a word for a specific dictionary.

        Look <word> up in <database>, if <database> is not specified then all
        available dictionaries are consulted.
        """
        return dict.define(word, database
            ).addCallback(self.formatResults
            ).addCallback(source.reply)


    @rest
    @usage(u'spell <word>')
    def cmd_spell(self, source, word, language=None):
        """
        Check the spelling of a word in English (UK).

        If <word> is spelt incorrectly, a list of suggestions are given.
        Checking the spelling of a word in a specific language can be done with
        the "spellfor" command.
        """
        source.reply(self.suggest(word, u'en_GB'))


    @rest
    @usage(u'spell <language> <word>')
    def cmd_spellfor(self, source, language, word):
        """
        Check the spelling of a word in a specific language.

        If <word> is spelt incorrectly, a list of suggestions are given.
        """
        source.reply(self.suggest(word, language))
