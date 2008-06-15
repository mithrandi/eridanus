from eridanus.util import encode


class IRCUser(object):
    """
    Representation of an IRC user.

    @ivar usermask: Complete user mask as originally supplied
    @type usermask: C{str}

    @ivar nickname: User's nickname
    @type nickname: C{str}

    @ivar realname: User's ident/realname
    @type realname: C{str}

    @ivar host: User's host
    @type host: C{str}
    """
    def __init__(self, usermask):
        """
        Break C{host} up into it's parts.

        @param usermask: The user mask of the form C{nick!user@host}
        @type usermask: C{str}
        """
        if '!' in usermask:
            nickname, realname = usermask.split('!', 1)
            realname, host = realname.split('@', 1)
        else:
            # If we get messages from the server (or something) these generally
            # don't look like the messages we get from regular users, so let's
            # rather not explode when that happens.
            nickname = realname = None
            host = usermask

        self.usermask = usermask
        self.nickname = unicode(nickname, 'ascii') # XXX: is this a good idea?
        self.realname = realname
        self.host = host

    def __repr__(self):
        return '<%s %s>' % (type(self).__name__, self.usermask)


class IRCSource(object):
    """
    An IRC message source.

    @ivar protocol: The protocol that data will travel back over

    @ivar channel: The channel the message originated from
    @type channel: C{str}

    @ivar user: The user representation this message originated from
    @type user: L{IRCUser}
    """
    def __init__(self, protocol, channel, user):
        self.protocol = protocol
        self.channel = channel
        self.user = user

        # XXX: somewhat of a hack, something else should probably be doing this
        self.isPrivate = self.protocol.nickname == channel

    def __repr__(self):
        return '<%s %s %s>' % (type(self).__name__, self.channel, self.user)

    # XXX: use something more generic and extendable than this
    @property
    def maxTopicLength(self):
        topicLength = self.protocol.isupported.get('TOPICLEN', None)
        if topicLength is not None:
            return int(topicLength[0])

        return None

    def _getTarget(self, privateSay, publicSay):
        if self.isPrivate:
            f = privateSay
            target = encode(self.user.nickname)
        else:
            f = publicSay
            target = encode(self.channel)

        return f, target

    def notice(self, text):
        """
        Notice C{text} to the current channel.
        """
        f, target = self._getTarget(self.protocol.notice, self.protocol.notice)
        f(target, encode(text))

    def say(self, text):
        """
        Say C{text} in the current channel (or private) over the protocol.
        """
        f, target = self._getTarget(self.protocol.msg, self.protocol.say)
        f(target, encode(text))

    def reply(self, text):
        """
        Reply to L{self.user} with C{text}.
        """
        self.tell(self.user.nickname, text)

    def tell(self, nickname, text):
        """
        Address C{text} to C{nickname}.
        """
        msg = u'%s: %s' % (nickname, text)
        self.say(msg)

    def join(self, channel):
        """
        Join the IRC channel named C{channel}.
        """
        self.protocol.join(channel)

    def part(self, channel=None):
        """
        Part C{channel} or the current IRC channel if not specified.
        """
        if channel is None:
            channel = self.channel
        self.protocol.part(channel)

    def getTopic(self):
        """
        Retrieve the topic for the current IRC channel.
        """
        def gotTopic((user, channel, topic)):
            return topic

        return self.protocol.topic(self.channel
            ).addCallback(gotTopic)

    def setTopic(self, topic):
        """
        Set the topic for the current IRC channel.
        """
        self.protocol.topic(self.channel, topic)

    def ignore(self, mask):
        """
        Start ignoring a user mask.
        """
        self.protocol.ignore(mask)

    def unignore(self, mask):
        """
        Stop ignoring a user mask.
        """
        self.protocol.unignore(mask)
