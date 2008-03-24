from axiom import userbase

from xmantissa import website, offering

#from artemis import publicpage, theme, news
#from artemis.admin import NewsReporter

from eridanus import publicpage, theme

plugin = offering.Offering(
    name = u'Eridanus',
    description = u'URL tracking IRC bot',

    siteRequirements = [
        (userbase.IRealm, userbase.LoginSystem),
        (None, website.WebSite),
        ],

    appPowerups = [
        publicpage.EridanusPublicPage,
        #news.Newspaper,
        ],

    installablePowerups = [
        #(u'Reporter', u'Report news', NewsReporter),
        ],

    loginInterfaces = [],

    themes = [
        theme.Theme('eridanus-base', 0),
        ])
