from zope.interface import classProvides

from twisted.plugin import IPlugin

from axiom.attributes import integer
from axiom.item import Item

from eridanus.ieridanus import IEridanusPluginProvider
from eridanus.plugin import Plugin, usage

class Topic(Item, Plugin):
    """
    Manage channel topics in a structured fashion.
    """
    classProvides(IPlugin, IEridanusPluginProvider)
    schemaVersion = 1
    typeName = 'eridanus_plugins_topic'

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
