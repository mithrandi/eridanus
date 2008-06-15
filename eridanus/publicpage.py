import shlex
from zope.interface import implements
from datetime import timedelta

from twisted.python.filepath import FilePath

from axiom.item import Item
from axiom.attributes import integer, text
from axiom.errors import ItemNotFound

from nevow import static, tags, url
from nevow.inevow import IRequest, ICanHandleNotFound
from nevow.rend import Page
from nevow.vhost import VHostMonsterResource

from xmantissa import publicweb, website
from xmantissa.ixmantissa import IPublicPage, ISiteRootPlugin, ISessionlessSiteRootPlugin
from xmantissa.webtheme import SiteTemplateResolver

from eridanus import chart
from eridanus.bot import IRCBotService
from eridanus.util import ThemedFragment, truncate, decode
from eridanus.feeds import ChannelFeed


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


class SearchInputFragment(ThemedFragment):
    fragmentName = 'search-input'

    def __init__(self, terms=None, **kw):
        super(SearchInputFragment, self).__init__(**kw)
        self.terms = terms

    def render_input(self, ctx, data):
        tag = ctx.tag
        if self.terms is None:
            value = u''
        else:
            def quoteTerm(term):
                if u' ' in term:
                    return u'"%s"' % (term,)
                return term
            terms = [quoteTerm(term) for term in self.terms]
            value = u' '.join(terms)
        return tag.fillSlots('value', value)


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

    def navigation(self):
        return None

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

    def render_navigation(self, ctx, data):
        navItems = self.navigation()
        if not navItems:
            return []

        tag = ctx.tag
        imageRoot = url.URL.fromString('/Eridanus/static/images/')
        navItemPattern = tag.patternGenerator('navItem')

        def _navItems():
            for (title, imageName, url) in navItems:
                yield navItemPattern(
                    ).fillSlots('url', url
                    ).fillSlots('imageUrl', imageRoot.child(imageName)
                    ).fillSlots('title', title)

        return tag.fillSlots('items', _navItems())


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
                ).fillSlots('modifiedTimestamp', e.displayModifiedTimestamp,
                ).fillSlots('comments', comments(e))

        return tag[(entry(e) for e in self.entries)]


class SearchResultsFragment(EntriesFragment):
    def __init__(self, terms, **kw):
        self.terms = terms
        super(SearchResultsFragment, self).__init__(**kw)

    def render_content(self, ctx, data):
        return ctx.tag[SearchInputFragment(terms=self.terms, store=self.store)]

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


class ChannelChartsFragment(ThemedFragment):
    fragmentName = 'channel-charts'

    charts = [
        (u'Top contributors', 'contributors')]

    def __init__(self, parent, manager, **kw):
        self.parent = parent
        self.manager = manager
        super(ChannelChartsFragment, self).__init__(**kw)

    @property
    def title(self):
        return u'Charts for %s' % (self.manager.channel,)

    def render_charts(self, ctx, data):
        tag = ctx.tag
        img = tag.patternGenerator('chart')

        # XXX: ergh
        chartUrl = self.parent.trail.get('channel')[1].child('chart')

        def _charts():
            for title, chartType in self.charts:
                yield img(
                    ).fillSlots('imageUrl', chartUrl.add('type', chartType)
                    ).fillSlots('title', title)

        return tag[_charts()]


class ChannelChartsPage(EridanusPage):
    addSlash = True

    def __init__(self, manager, **kw):
        self.manager = manager
        super(ChannelChartsPage, self).__init__(**kw)

    @property
    def heading(self):
        return self.trail.render('network', 'channel', 'chart')

    def getFragment(self):
        return ChannelChartsFragment(parent=self, manager=self.manager, store=self.store)


class ChannelFragment(EntriesFragment):
    def __init__(self, manager, **kw):
        self.manager = manager
        super(ChannelFragment, self).__init__(entries=self.getEntries(), **kw)

    def getEntries(self):
        return self.manager.getEntries(limit=50)

    @property
    def title(self):
        return u'%(channel)s on %(network)s' % self.parent.trail.names

    def render_content(self, ctx, data):
        return ctx.tag[SearchInputFragment(store=self.store)]


class ChannelPage(EridanusPage):
    addSlash = True

    searchLimit = 50

    def __init__(self, manager, **kw):
        self.manager = manager
        super(ChannelPage, self).__init__(**kw)

    def head(self):
        return tags.link(rel='alternate', href='feed', type='application/atom+xml')

    def navigation(self):
        yield u'Charts', 'chart-icon.png', 'charts'

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

    def child_charts(self, ctx):
        req = IRequest(ctx)
        self.trail.add('chart', u'Charts', req.URLPath().child('charts'))
        return ChannelChartsPage(parent=self, manager=self.manager)

    def child_chart(self, ctx):
        req = IRequest(ctx)
        type = req.args.get('type', [None])[0]
        if type is None:
            return None

        data = None
        if type == 'contributors':
            data = chart.contributors(self.manager, labelColor='#ffffff', colorScheme='#7d4f02').read()

        if data is None:
            return None

        return static.Data(data=data, type='image/png', expires=timedelta(hours=1).seconds)

    def child_feed(self, ctx):
        return ChannelFeed(self.manager)

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

        return tag[(channel(m) for m in self.network.getEntryManagers())]


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


class VHost(Item, website.PrefixURLMixin):
    implements(ISessionlessSiteRootPlugin)

    typeName = 'eridanus_vhost'
    schemaVersion = 1

    sessionless = True

    prefixURL = text(default=u'vhost')

    def createResource(self):
        return VHostMonsterResource()


class FrontPage(Item, website.PrefixURLMixin):
    implements(ISiteRootPlugin)

    typeName = 'eridanus_front_page'
    schemaVersion = 1

    sessioned = True

    publicViews = integer(doc="""
        The number of times this object has been viewed in a public
        (non-authenticated) context.  This includes renderings of the front
        page only.
        """, default=0)

    privateViews = integer(doc="""
        The number of times this object has been viewed in a private
        (authenticated) context.  This only counts the number of times users
        have been redirected from "/" to "/private".
        """, default=0)

    prefixURL = text(doc="""
        See L{website.PrefixURLMixin}.
        """, default=u'', allowNone=False)

    def createResource(self):
        pfp = PublicFrontPage(self, staticContent=None, forUser=None)
        pfp.remember(FourOhFourPage(self.store), ICanHandleNotFound)
        return pfp


class PublicFrontPage(publicweb.PublicFrontPage):
    def child_(self, ctx):
        return url.URL.fromContext(ctx).child('Eridanus')


class FourOhFourPage(PublicContentPage):
    implements(ICanHandleNotFound)

    def getFragment(self):
        return FourOhFourFragment(store=self.store)

    def render_heading(self, ctx, data):
        return []

    def render_subHeading(self, ctx, data):
        return []

    def renderHTTP_notFound(self, ctx):
        return self


class FourOhFourFragment(ThemedFragment):
    fragmentName = '404'

    def render_url(self, ctx, data):
        req = IRequest(ctx)
        return ctx.tag[req.path]

