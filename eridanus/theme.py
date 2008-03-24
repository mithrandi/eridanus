from nevow import tags

from xmantissa import webtheme


class Theme(webtheme.XHTMLDirectoryTheme):
    def head(self, request, website):
        def styleSheetLink(href):
            return tags.link(rel='stylesheet', type='text/css', href=href)

        root = website.cleartextRoot(request.getHeader('host'))
        styles = root.child('Eridanus').child('static').child('styles')

        yield styleSheetLink(styles.child('eridanus.css'))
        yield tags.xml(u'<!--[if IE 6]>'), styleSheetLink(styles.child('eridanus-ie6.css')), tags.xml(u'<![endif]-->')
        yield tags.xml(u'<!--[if IE 7]>'), styleSheetLink(styles.child('eridanus-ie7.css')), tags.xml(u'<![endif]-->')


class Base(webtheme.XHTMLDirectoryTheme):
    def head(self, request, website):
        pass
