from eridanus import plugin

def safePluginImport(name):
    plugin.safePluginImport(name, globals())

safePluginImport('eridanusstd.plugindefs.google.GooglePlugin')
safePluginImport('eridanusstd.plugindefs.admin.AdminPlugin')
safePluginImport('eridanusstd.plugindefs.authenticate.AuthenticatePlugin')
safePluginImport('eridanusstd.plugindefs.topic.TopicPlugin')
safePluginImport('eridanusstd.plugindefs.dict.DictPlugin')
safePluginImport('eridanusstd.plugindefs.time.TimePlugin')
safePluginImport('eridanusstd.plugindefs.urbandict.UrbanDictPlugin')
safePluginImport('eridanusstd.plugindefs.factoid.FactoidPlugin')
safePluginImport('eridanusstd.plugindefs.math.MathPlugin')
safePluginImport('eridanusstd.plugindefs.fortune.FortunePlugin')
safePluginImport('eridanusstd.plugindefs.imdb.IMDBPlugin')
safePluginImport('eridanusstd.plugindefs.xboxlive.XboxLivePlugin')
safePluginImport('eridanusstd.plugindefs.currency.CurrencyPlugin')
safePluginImport('eridanusstd.plugindefs.memo.MemoPlugin')
safePluginImport('eridanusstd.plugindefs.weather.WeatherPlugin')
safePluginImport('eridanusstd.plugindefs.qdb.QDBPlugin')
safePluginImport('eridanusstd.plugindefs.unicode.UnicodePlugin')
safePluginImport('eridanusstd.plugindefs.random.RandomPlugin')
