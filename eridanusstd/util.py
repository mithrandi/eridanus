import html5lib



def _parseCompat(data, **kw):
    from eridanusstd import etree
    parser = html5lib.HTMLParser(
        tree=html5lib.treebuilders.getTreeBuilder('etree', etree))
    return etree.ElementTree(parser.parse(data))



def parseHTML(data):
    parse = getattr(html5lib, 'parse', None)
    if parse is None:
        parse = _parseCompat
    return parse(data, treebuilder='lxml')
