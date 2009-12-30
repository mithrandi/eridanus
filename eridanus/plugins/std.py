from functools import partial

from eridanus import plugin

importPlugin = partial(plugin.safePluginImport, globals())

importPlugin('eridanusstd.plugindefs.google.GooglePlugin')
importPlugin('eridanusstd.plugindefs.admin.AdminPlugin')
importPlugin('eridanusstd.plugindefs.authenticate.AuthenticatePlugin')
importPlugin('eridanusstd.plugindefs.topic.TopicPlugin')
importPlugin('eridanusstd.plugindefs.dict.DictPlugin')
importPlugin('eridanusstd.plugindefs.time.TimePlugin')
importPlugin('eridanusstd.plugindefs.urbandict.UrbanDictPlugin')
importPlugin('eridanusstd.plugindefs.factoid.FactoidPlugin')
importPlugin('eridanusstd.plugindefs.math.MathPlugin')
importPlugin('eridanusstd.plugindefs.fortune.FortunePlugin')
importPlugin('eridanusstd.plugindefs.imdb.IMDBPlugin')
importPlugin('eridanusstd.plugindefs.xboxlive.XboxLivePlugin')
importPlugin('eridanusstd.plugindefs.currency.CurrencyPlugin')
importPlugin('eridanusstd.plugindefs.memo.MemoPlugin')
importPlugin('eridanusstd.plugindefs.weather.WeatherPlugin')
importPlugin('eridanusstd.plugindefs.qdb.QDBPlugin')
importPlugin('eridanusstd.plugindefs.unicode.UnicodePlugin')
importPlugin('eridanusstd.plugindefs.random.RandomPlugin')
