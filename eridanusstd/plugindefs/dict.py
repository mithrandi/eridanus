from zope.interface import classProvides

from twisted.plugin import IPlugin

from axiom.attributes import integer
from axiom.item import Item

from eridanus.ieridanus import IEridanusPluginProvider
from eridanus.plugin import Plugin, usage

from eridanusstd import dict

class Dict(Item, Plugin):
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

