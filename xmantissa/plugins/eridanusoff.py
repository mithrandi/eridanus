from axiom import userbase

from xmantissa import website, offering

from eridanus import theme

plugin = offering.Offering(
    name = u'Eridanus',
    description = u'URL tracking IRC bot',

    siteRequirements = [
        (userbase.IRealm, userbase.LoginSystem),
        (None, website.WebSite),
        ],

    appPowerups = [
        ],

    installablePowerups = [
        ],

    loginInterfaces = [],

    themes = [
        theme.Theme('eridanus-base', 0),
        ])
