"""
A set of tools to easily build Atom 1.0 syndication feeds.

Usage sample::

    from xml.etree.ElementTree import tostring
    from epsilon.extime import Time
    from atom import Link, Summary, Entry, Author, Feed

    entries = [
        Entry(title='Atom-Powered Robots Run Amok',
              links=[Link(href='http://example.org/2003/12/13/atom03')],
              id='urn:uuid:1225c695-cfb8-4ebb-aaaa-80da344efa6a',
              updated=Time(),
              summary=Summary('Some text.'))
        ]

    feed = Feed(id='urn:uuid:60a76c80-d399-11d9-b93C-0003939e0af6',
                title='Example Feed',
                updated=Time(),
                authors=[Author(name='John Doe')],
                links=[Link(href='http://example.org/')],
                entries=entries)

    print tostring(f.serialize())
"""
try:
    from xml.etree import ElementTree as ET
except ImportError:
    from elementtree import ElementTree as ET

from epsilon.structlike import record


NAMESPACE = 'http://www.w3.org/2005/Atom'
tostring = ET.tostring


class ElementMagic(object):
    def __init__(self, elemName, **kw):
        # XXX: Argh! Etree doesn't enjoy serializing XML attributes with
        # values that are None.
        kw = dict((k, v) for k, v in kw.iteritems() if v is not None)
        self.elem = ET.Element(elemName, **kw)

    def __getitem__(self, child):
        elem = self.elem

        if child is None:
            return None
        elif isinstance(child, type(elem)):
            elem.append(child)
        elif isinstance(child, type(self)):
            elem.append(child.elem)
        elif isinstance(child, basestring):
            elem.text = child
        elif hasattr(child, 'serialize'):
            self[child.serialize()]
        else:
            try:
                for c in iter(child):
                    self[c]
            except TypeError:
                raise ValueError('Unrecognized child: %r :: %r' % (child, type(child)))

        return elem

E = ElementMagic


def magicOrElement(name, obj):
    """
    Return an L{ElementMagic} instance, with C{name} as the element name, if
    C{obj} is not an L{AtomElement}. Otherwise return C{obj}.
    """
    if isinstance(obj, AtomElement):
        return obj
    return E(name)[obj]


class AtomElement(object):
    def serialize(self):
        """
        Flattens the C{AtomElement} into an L{ElementTree.Element}.
        """
        raise NotImplementedError()


class Person(AtomElement, record('elemName name uri email',
    uri=None, email=None)):
    """
    Represents a person.

    @ivar elemName: Element name to generate
    @type name: C{str} or C{unicode}
    @type uri: C{str} or C{unicode} or C{None}
    @type email: C{str} or C{unicode} or C{None}
    """
    def serialize(self):
        return E(self.elemName)[
            E('name')[self.name],
            E('uri')[self.uri],
            E('email')[self.email]]


class Author(Person):
    def __init__(self, *a, **kw):
        kw['elemName'] = 'author'
        super(Author, self).__init__(*a, **kw)


class Contributor(Person):
    def __init__(self, *a, **kw):
        kw['elemName'] = 'contributor'
        super(Contributor, self).__init__(*a, **kw)


class Link(AtomElement, record('href rel type hreflang title length',
    rel=None, type=None, hreflang=None, title=None, length=None)):
    """
    Defines a link.

    @type href: C{str} or C{unicode} or C{None}
    @type rel: C{str} or C{unicode} or C{None}
    @type type: C{str} or C{unicode} or C{None}
    @type hreflang: C{str} or C{unicode} or C{None}
    @type title: C{str} or C{unicode} or C{None}
    @type length: C{str} or C{unicode} or C{None}
    """
    def serialize(self):
        return E('link',
            href=self.href,
            rel=self.rel,
            hreflang=self.hreflang,
            title=self.title,
            length=self.length)


class Text(AtomElement, record('content elemName type',
    type=None)):
    """
    Generic text element.

    @cvar elemName: Override the elemName argument

    @type content: C{str} or C{unicode}
    @ivar elemName: Element name to generate
    @type type: C{str}, C{unicode} or C{None}
    """
    def __init__(self, *a, **kw):
        if hasattr(self, 'elemName'):
            kw['elemName'] = self.elemName
        super(Text, self).__init__(*a, **kw)

    def serialize(self):
        return E(self.elemName, type=self.type)[self.content]


class Title(Text):
    elemName = 'title'


class Summary(Text):
    elemName = 'summary'


class Content(Text):
    elemName = 'content'


class Rights(Text):
    elemName = 'rights'


class Icon(Text):
    elemName = 'icon'


class Logo(Text):
    elemName = 'logo'


class Subtitle(Text):
    elemName = 'subtitle'


class Entry(AtomElement, record('id title updated authors content links summary categories contributors published source rights',
    authors=None, content=None, links=None, summary=None, categories=None, contributors=None, published=None, source=None, rights=None)):
    """
    An indivial entry, acting as a container for metadata and data.

    @type id: C{str} or C{unicode}
    @type title: C{str}, C{unicode}, L{Title} instance or C{None}
    @type updated: L{epsilon.extime.Time} instance
    @type authors: C{iterable} of L{Author} instances or C{None}
    @type content: C{str}, C{unicode}, L{Content} instance or C{None}
    @type links: C{iterable} of L{Link} instances or C{None}
    @type summary: C{str}, C{unicode}, L{Summary} instance or C{None}
    @type categories: C{iterable} of L{Category} instances or C{None}
    @type contributors: C{iterable} of L{Contributor} instances or C{None}
    @type published: L{epsilon.extime.Time} instance or C{None}
    @type source: L{Source} instance or C{None}
    @type rights: C{str}, C{unicode}, L{Rights} instance or C{None}
    """
    def serialize(self):
        published = None
        if self.published is not None:
            published = self.published.asISO8601TimeAndDate()

        return E('entry')[
            E('id')[self.id],
            magicOrElement('title', self.title),
            E('updated')[self.updated.asISO8601TimeAndDate()],
            self.authors,
            magicOrElement('content', self.content),
            self.links,
            magicOrElement('summary', self.summary),
            self.categories,
            self.contributors,
            E('published')[published],
            self.source,
            magicOrElement('rights', self.rights)]


class Generator(AtomElement, record('name uri version',
    uri=None, version=None)):
    """
    Identifies the software used to generate the feed.

    @type name: C{str} or C{unicode}
    @type uri: C{str} or C{unicode}
    @type version: C{str} or C{unicode}
    """
    def serialize(self):
        return E('generator', uri=self.uri, version=self.version)[self.name]


class Feed(AtomElement, record('id title updated authors links entries categories contributors generator icon logo rights subtitle',
    authors=None, links=None, entries=None, categories=None, contributors=None, generator=None, icon=None, logo=None, rights=None, subtitle=None)):
    """
    Root element of an Atom 1.0 feed.

    @type id: C{str} or C{unicode}
    @type title: C{str}, C{unicode}, L{Title} instance or C{None}
    @type updated: L{epsilon.extime.Time} instance
    @type authors: C{iterable} of L{Author} instances or C{None}
    @type links: C{iterable} of L{Link} instances or C{None}
    @type entries: C{iterable} of L{Entry} instances or C{None}
    @type categories: C{iterable} of L{Category} instances or C{None}
    @type contributors: C{iterable} of L{Contributor} instances or C{None}
    @type generator: L{Generator} instance or C{None}
    @type icon: C{str}, C{unicode}, L{Icon} instance or C{None}
    @type logo: C{str}, C{unicode}, L{Logo} instance or C{None}
    @type rights: C{str}, C{unicode}, L{Rights} instance or C{None}
    @type subtitle: C{str}, C{unicode}, L{Subtitle} instance or C{None}
    """
    def serialize(self):
        return E('feed', xmlns=NAMESPACE)[
            E('id')[self.id],
            magicOrElement('title', self.title),
            E('updated')[self.updated.asISO8601TimeAndDate()],
            self.authors,
            self.links,
            self.entries,
            self.categories,
            self.contributors,
            self.generator,
            magicOrElement('icon', self.icon),
            magicOrElement('logo', self.logo),
            magicOrElement('rights', self.rights),
            self.subtitle]


__all__ = [
    # Constants
    'NAMESPACE',

    # Core objects
    'Author', 'Content', 'Contributor', 'Entry', 'Feed', 'Generator', 'Icon',
    'Link', 'Logo', 'Rights', 'Subtitle', 'Summary', 'Title']
