"""
Eridanus standard plugin library.
"""

from functools import partial

from eridanus import plugin

importPlugin = partial(plugin.safePluginImport, globals())

importPlugin('eridanusstd.plugindefs.google.Google')
importPlugin('eridanusstd.plugindefs.admin.Admin')
importPlugin('eridanusstd.plugindefs.authenticate.Authenticate')
importPlugin('eridanusstd.plugindefs.topic.Topic')
importPlugin('eridanusstd.plugindefs.dict.Dict')
importPlugin('eridanusstd.plugindefs.time.Time')
importPlugin('eridanusstd.plugindefs.urbandict.UrbanDict')
importPlugin('eridanusstd.plugindefs.factoid.Factoid')
importPlugin('eridanusstd.plugindefs.math.Math')
importPlugin('eridanusstd.plugindefs.fortune.Fortune')
importPlugin('eridanusstd.plugindefs.imdb.IMDB')
importPlugin('eridanusstd.plugindefs.xboxlive.XboxLive')
importPlugin('eridanusstd.plugindefs.currency.Currency')
importPlugin('eridanusstd.plugindefs.memo.Memo')
importPlugin('eridanusstd.plugindefs.weather.Weather')
importPlugin('eridanusstd.plugindefs.qdb.QDB')
importPlugin('eridanusstd.plugindefs.unicode.Unicode')
importPlugin('eridanusstd.plugindefs.random.Random')
importPlugin('eridanusstd.plugindefs.linkdb.LinkDB')
importPlugin('eridanusstd.plugindefs.linkdb.LinkDBAdmin')
