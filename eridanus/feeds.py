from nevow.rend import Page
from nevow.inevow import IRequest

from eridanus.atom import tostring, Feed, Entry, Link, Author, Content, E


class FeedPage(Page):
    maxItems = 50
    feedId = None

    def __init__(self):
        super(FeedPage, self).__init__()

    def getFeed(self):
        raise NotImplementedError()

    def renderHTTP(self, ctx):
        req = IRequest(ctx)
        req.setHeader('Content-Type', 'application/atom+xml')
        data = tostring(self.getFeed().serialize())
        req.write(data)
        return ''


class ChannelFeed(FeedPage):
    feedId = 'http://linkdb.slipgate.za.net/'

    def __init__(self, manager, **kw):
        super(ChannelFeed, self).__init__(**kw)
        self.manager = manager

    def entryContent(self, entry):
        initialComment = entry.initialComment
        if initialComment is not None:
            initialComment = E('span')[u' \u2013 \u201c%s\u201d' % (entry.initialComment.comment,)]

        comments = entry.comments
        if comments is not None:
            comments = E('ul')[
                [E('li')[u'\u201c%s\u201d \u2013 %s' % (c.comment, c.nick)] for c in comments]]

        network = self.manager.config.service.serviceID
        channel = entry.channel.strip('#')
        href = '/Eridanus/%s/%s/%s' % (network, channel, entry.eid)

        return E('div', xmlns='http://www.w3.org/1999/xhtml')[
            E('a', href=href)['#%s' % (entry.eid,)],
            E('span')[u': Posted by %s.' % (entry.nick,)],
            initialComment,
            comments]


    def entryFromEntry(self, entry):
        content = self.entryContent(entry)
        return Entry(id=unicode(entry.eid),
                     title=entry.displayTitle,
                     updated=entry.modified,
                     links=[Link(rel='alternate', href=entry.url)],
                     authors=[Author(name=entry.nick)],
                     content=Content(content, type='xhtml'))

    def getFeed(self):
        entries = list(self.manager.getEntries(limit=self.maxItems))
        atomEntries = (self.entryFromEntry(e) for e in entries)

        title = u'%s links' % (self.manager.channel,)
        href = '/Eridanus/feeds/%s' % (self.manager.channel.strip('#'),)
        return Feed(id=self.feedId,
                    title=title,
                    updated=entries[0].modified,
                    links=[Link(rel='self', href=href)],
                    entries=atomEntries)
