import shlex
from zope.interface import implements

from twisted.python.filepath import FilePath

from axiom.item import Item
from axiom.attributes import integer
from axiom.errors import ItemNotFound

from nevow import static, tags, url
from nevow.inevow import IRequest
from nevow.rend import Page

from xmantissa import publicweb
from xmantissa.ixmantissa import IPublicPage
from xmantissa.webtheme import SiteTemplateResolver

from eridanus.bot import IRCBotService
from eridanus.util import ThemedFragment, truncate, decode


class Trail(object):
    def __init__(self):
        self.names = {}
        self.urls = {}

    def add(self, key, name, url):
        self.names[key] = name
        self.urls[key] = url.clear()

    def get(self, key):
        return self.names[key], self.urls[key]

    def render(self, *keys):
        def _render((name, url)):
            return tags.a(href=url)[name]

        data = [self.get(key) for key in keys]
        return [(_render(d), ' / ') for d in data[:-1]] + [_render(data[-1])]


class EridanusPublicPage(Item):
    implements(IPublicPage)

    typeName = 'eridanus_public_page'
    schemaVersion = 1
    powerupInterfaces = [IPublicPage]

    dummy = integer()

    def getResource(self):
        return PublicIndexPage(self.store)


class PublicContentPage(publicweb.PublicPage):
    def __init__(self, store, **kw):
        assert store is not None, (self, store)
        super(PublicContentPage, self).__init__(None, store, staticContent=None, forUser=None, fragment=None, **kw)
        resolver = SiteTemplateResolver(store)
        self.docFactory = resolver.getDocFactory('public-shell')
        assert self.docFactory is not None, (self, store)
        self.fragment = self.getFragment()


class EridanusPage(PublicContentPage):
    heading = None
    subHeading = None

    def __init__(self, parent):
        self.parent = parent
        self.trail = self.parent.trail
        super(EridanusPage, self).__init__(store=self.parent.store)

    def getFragment(self):
        return None

    def tagOrEmpty(self, tag, content):
        if content is None:
            return []
        return tag[content]

    def render_heading(self, ctx, data):
        return self.tagOrEmpty(ctx.tag, self.heading)

    def render_subHeading(self, ctx, data):
        return self.tagOrEmpty(ctx.tag, self.subHeading)


class EntriesFragment(ThemedFragment):
    fragmentName = 'entries'

    def __init__(self, parent, entries, **kw):
        self.parent = parent
        self.store = self.parent.store
        super(EntriesFragment, self).__init__(store=self.store, **kw)
        self.entries = list(entries)

    def render_content(self, ctx, data):
        return ctx.tag

    def render_entries(self, ctx, data):
        tag = ctx.tag

        if not self.entries:
            return tag[tag.onePattern('noEntries')]

        entryPattern = tag.patternGenerator('entry')
        commentPattern = tag.patternGenerator('comment')
        commentSectionPattern = tag.patternGenerator('commentSection')

        def comment(c):
            return commentPattern(
                ).fillSlots('timestamp', c.displayTimestamp
                ).fillSlots('name', c.nick
                ).fillSlots('comment', c.comment)

        def comments(e):
            comments = e.comments
            if comments:
                return commentSectionPattern(
                    ).fillSlots('content', (comment(c) for c in comments))
            return []

        def titleComment(e):
            c = e.initialComment
            if c is not None:
                return tag.onePattern('titleComment'
                         ).fillSlots('initialComment', c.comment)
            return []

        def entry(e):
            title = e.displayTitle
            return entryPattern(
                ).fillSlots('intUrl', e.eid # XXX: maybe use an absolute URL?
                ).fillSlots('id', e.eid
                ).fillSlots('extUrl', e.url
                ).fillSlots('displayTitle', truncate(title, 55)
                ).fillSlots('title', title
                ).fillSlots('titleComment', titleComment(e)
                ).fillSlots('creator', e.nick
                ).fillSlots('occurences', e.occurences
                ).fillSlots('timestamp', e.displayTimestamp
                ).fillSlots('comments', comments(e))

        return tag[(entry(e) for e in self.entries)]


class SearchResultsFragment(EntriesFragment):
    def __init__(self, terms, **kw):
        self.terms = terms
        super(SearchResultsFragment, self).__init__(**kw)

    @property
    def title(self):
        return u'Search results: ' + u' '.join(self.terms)


class SearchResultsPage(EridanusPage):
    def __init__(self, terms, entries, **kw):
        self.terms = terms
        self.entries = entries
        super(SearchResultsPage, self).__init__(**kw)

    @property
    def heading(self):
        return self.trail.render('network', 'channel')

    @property
    def subHeading(self):
        return u'%d results for: %s' % (len(self.entries), u' '.join(self.terms))

    def getFragment(self):
        return SearchResultsFragment(parent=self, terms=self.terms, entries=self.entries)


class EntryFragment(EntriesFragment):
    @property
    def title(self):
        return u'%(eid)s in %(channel)s on %(network)s' % self.parent.trail.names


class EntryPage(EridanusPage):
    def __init__(self, entry, **kw):
        self.entry = entry
        super(EntryPage, self).__init__(**kw)

    @property
    def heading(self):
        return self.trail.render('network', 'channel', 'eid')

    def getFragment(self):
        return EntryFragment(parent=self, entries=[self.entry])


class SearchInputFragment(ThemedFragment):
    fragmentName = 'search-input'


class ChannelFragment(EntriesFragment):
    def __init__(self, manager, **kw):
        self.manager = manager
        super(ChannelFragment, self).__init__(entries=self.getEntries(), **kw)

    def getEntries(self):
        return self.manager.allEntries(limit=50)

    @property
    def title(self):
        return u'%(channel)s on %(network)s' % self.parent.trail.names

    def render_content(self, ctx, data):
        return ctx.tag[SearchInputFragment(store=self.store)]

    # XXX: leet google chart
    # http://chart.apis.google.com/chart?chd=s%3AEFFILNSVs9&chs=900x300&cht=p&chtt=Top 10 URL contributors for %23code&chl=yegz (8)|Karl (10)|HelfiX (11)|nim (16)|pjd (23)|Karnaugh (26)|Shrimp (36)|Zelphar (43)|k4y (89)|mithrandi (121)&chf=bg,s,222233&chts=ffffff&chxs=0,ffffff&chxt=x


class ChannelPage(EridanusPage):
    addSlash = True

    searchLimit = 50

    def __init__(self, manager, **kw):
        self.manager = manager
        super(ChannelPage, self).__init__(**kw)

    @property
    def heading(self):
        return self.trail.render('network', 'channel')

    def getFragment(self):
        return ChannelFragment(parent=self, manager=self.manager)

    def child_search(self, ctx):
        req = IRequest(ctx)
        # XXX: ergh
        terms = [decode(term) for arg in req.args.get('q', []) for term in shlex.split(arg)]
        entries = list(self.manager.search(terms, limit=self.searchLimit))
        return SearchResultsPage(parent=self, terms=terms, entries=entries)

    def childFactory(self, ctx, name):
        req = IRequest(ctx)
        try:
            eid = int(name)
            entry = self.manager.entryById(eid)
            if entry is not None:
                self.trail.add('eid', eid, req.URLPath().child(eid))
                return EntryPage(parent=self, entry=entry)
        except ValueError:
            pass

        return None


class NetworkFragment(ThemedFragment):
    fragmentName = 'channels'

    def __init__(self, network, **kw):
        self.network = network
        super(NetworkFragment, self).__init__(**kw)

    @property
    def title(self):
        return u'Channels on %s' % (self.network.name,)

    def render_channels(self, ctx, data):
        tag = ctx.tag
        channelPattern = tag.patternGenerator('channel')

        def channel(manager):
            channel = manager.channel
            return channelPattern(
                ).fillSlots('url', channel[1:]
                ).fillSlots('name', channel)

        return tag[(channel(m) for m in self.network.allEntryManagers())]


class NetworkPage(EridanusPage):
    addSlash = True

    def __init__(self, network, **kw):
        self.network = network
        super(NetworkPage, self).__init__(**kw)

    @property
    def heading(self):
        return self.network.name

    def getFragment(self):
        return NetworkFragment(network=self.network, store=self.parent.store)

    def childFactory(self, ctx, name):
        req = IRequest(ctx)
        try:
            channel = u'#' + name.decode('utf-8')
            manager = self.network.managerByChannel(channel)
            self.trail.add('channel', manager.channel, req.URLPath().child(name))
            return ChannelPage(parent=self, manager=manager)
        except ItemNotFound:
            return None


class PublicIndexPage(Page):
    addSlash = True

    def __init__(self, store):
        super(PublicIndexPage, self).__init__()
        self.store = store.parent
        self.trail = Trail()

    def child_static(self, ctx):
        s = FilePath(__file__).parent().child('static')
        return static.File(s.path)

    def childFactory(self, ctx, name):
        req = IRequest(ctx)
        try:
            network = self.store.findUnique(IRCBotService, IRCBotService.serviceID == name).config
            self.trail.add('network', network.name, req.URLPath().child(name))
            return NetworkPage(parent=self, network=network)
        except ItemNotFound:
            return None

    def child_(self, ctx):
        # XXX: don't hardcode this
        return url.URL.fromContext(ctx).child('shadowfire')
