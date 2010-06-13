from twisted.cred.portal import IRealm

from axiom.scripts import axiomatic
from axiom.dependency import installOn, uninstallFrom
from axiom.attributes import AND

from eridanus import plugin, util
from eridanus.ieridanus import IIRCAvatar
from eridanus.bot import IRCBotService, IRCBotFactoryFactory, IRCBotConfig
from eridanus.avatar import AuthenticatedAvatar
from eridanus.superfeedr import SuperfeedrService



class ConfigureService(axiomatic.AxiomaticSubCommand):
    longdesc = 'Configure an Eridanus service'

    optParameters = [
        ('id',       None, None, 'Service identifier'),
        ('name',     None, None, 'Network name'),
        ('host',     'h',  None, 'Service hostname'),
        ('port',     'p',  6667, 'Service port number'),
        ('nick',     'n',  None, 'Bot nickname'),
        ('channels', 'c',  None, 'Channels to join'),
        ('ignores',  'i',  None, 'Nicknames to ignore'),
        ]

    def getStore(self):
        return self.parent.getStore()

    def postOptions(self):
        store = self.getStore()

        svc = store.findUnique(IRCBotService, IRCBotService.serviceID == self['id'])
        if svc.config is None:
            svc.config = config = IRCBotConfig(store=store)
        else:
            config = svc.config

        if self['name']:
            config.name = self.decodeCommandLine(self['name'])
        if self['host']:
            config.hostname = self['host']
        if self['port']:
            config.portNumber = int(self['port'])
        if self['nick']:
            config.nickname = self.decodeCommandLine(self['nick'])
        if self['channels']:
            config.channels = self.decodeCommandLine(self['channels']).split(u',')
        if self['ignores']:
            config.ignores = self.decodeCommandLine(self['ignores']).split(u',')




class CreateService(axiomatic.AxiomaticSubCommand):
    longdesc = 'Create a new Eridanus service'

    optParameters = [
        ('id', None, None, 'Service identifier'),
        ]

    def getStore(self):
        return self.parent.getStore()

    def postOptions(self):
        store = self.getStore()
        fact = store.findOrCreate(IRCBotFactoryFactory)
        svc = store.findOrCreate(IRCBotService,
                                 serviceID=self['id'],
                                 factory=fact)
        installOn(svc, store)



class RemoveService(axiomatic.AxiomaticSubCommand):
    longdesc = 'Remove an existing Eridanus service'

    optParameters = [
        ('id', None, None, 'Service identifier'),
        ]

    def getStore(self):
        return self.parent.getStore()

    def postOptions(self):
        store = self.getStore()

        fact = store.findUnique(IRCBotFactoryFactory)
        svc = store.findUnique(IRCBotService,
                               AND(IRCBotService.serviceID == self['id'],
                                   IRCBotService.factory == fact));

        uninstallFrom(svc, store)



class ListServices(axiomatic.AxiomaticSubCommand):
    longdesc = 'List available Eridanus services'

    def getStore(self):
        return self.parent.getStore()

    def postOptions(self):
        store = self.getStore()
        print '\n'.join(store.query(IRCBotService).getColumn('serviceID'))



class ManageServices(axiomatic.AxiomaticSubCommand):
    longdesc = 'Manage Eridanus services'

    subCommands = [
        ('create', None, CreateService, 'Create a new service'),
        ('remove', None, RemoveService, 'Remove an existing service'),
        ('config', None, ConfigureService, 'Set service configuration data'),
        ('list',   None, ListServices, 'List available services'),
        ]

    def getStore(self):
        return self.parent.getStore()

    def getAppStore(self):
        return self.parent.getAppStore()



class ListAvailablePlugins(axiomatic.AxiomaticSubCommand):
    longdesc = 'List available plugins, in the form "<PluginName> (<botcommand>)"'

    def getStore(self):
        return self.parent.getStore()

    def postOptions(self):
        pluginstrs = ['    %s (%s)' % (p.pluginName, p.name)
                      for p in plugin.getAllPlugins()]
        print 'Available plugins:'
        print '\n'.join(sorted(pluginstrs))



class InstallPlugin(axiomatic.AxiomaticSubCommand):
    longdesc = 'Install a plugin'

    synopsis = '<pluginName>'

    def getStore(self):
        return self.parent.getStore()

    def getAppStore(self):
        return self.parent.getAppStore()

    def parseArgs(self, pluginName):
        self['pluginName'] = self.decodeCommandLine(pluginName)

    def postOptions(self):
        plugin.installPlugin(self.getAppStore(), self['pluginName'])



class GrantPlugin(axiomatic.AxiomaticSubCommand):
    longdesc = 'Grant a user with access to a plugin'

    synopsis = '<user> <domain> <pluginName>'

    def parseArgs(self, username, domain, pluginName):
        self['username'] = self.decodeCommandLine(username)
        self['domain'] = self.decodeCommandLine(domain)
        self['pluginName'] = self.decodeCommandLine(pluginName)

    def postOptions(self):
        loginSystem = self.parent.getLoginSystem()
        loginAccount = loginSystem.accountByAddress(self['username'], self['domain'])
        assert loginAccount is not None, 'No such user'
        userStore = loginAccount.avatars.open()
        avatar = IIRCAvatar(userStore, None)
        if avatar is None:
            userStore.powerUp(AuthenticatedAvatar(store=userStore))
        plugin.installPlugin(userStore, self['pluginName'])



class ListBrokenPlugins(axiomatic.AxiomaticSubCommand):
    longdesc = 'List broken plugins'

    def getStore(self):
        return self.parent.getStore()

    def postOptions(self):
        pluginstrs = ['    %s' % (p.pluginName,)
                      for p in plugin.getBrokenPlugins()]
        print 'Broken plugins:'
        print '\n'.join(sorted(pluginstrs))



class DiagnosePlugin(axiomatic.AxiomaticSubCommand):
    longdesc = 'Explain why a plugin is unusable'

    synopsis = '<pluginName>'

    def getStore(self):
        return self.parent.getStore()

    def parseArgs(self, pluginName):
        self['pluginName'] = self.decodeCommandLine(pluginName)

    def postOptions(self):
        trace = plugin.diagnoseBrokenPlugin(self['pluginName']).getTraceback()
        print "Exception caught while trying to load %s:\n" % (self['pluginName'],)
        print '\n'.join(['>>  '+ln for ln in trace.splitlines()]) + '\n'



class ManagePlugins(axiomatic.AxiomaticSubCommand):
    longdesc = 'Manage plugins'

    subCommands = [
        ('available', None, ListAvailablePlugins, 'List available plugins'),
        ('install', None, InstallPlugin, 'Install a plugin'),
        ('grant', None, GrantPlugin, 'Endow a user with access to a plugin'),
        ('broken', None, ListBrokenPlugins, 'List unusable plugins'),
        ('diagnose', None, DiagnosePlugin, 'Explain why a plugin is unusable'),
        ]

    def getStore(self):
        return self.parent.getStore()

    def getAppStore(self):
        return self.parent.getAppStore()

    def getLoginSystem(self):
        return self.parent.getLoginSystem()



class PluginCommands(axiomatic.AxiomaticSubCommand):
    longdesc = 'Plugin-provided commands'

    @property
    def subCommands(self):
        for pin in plugin.getInstalledPlugins(self.getAppStore()):
            if pin.axiomCommands:
                class PluginSubCommand(axiomatic.AxiomaticSubCommand):
                    subCommands = pin.axiomCommands
                    getStore = lambda s: s.parent.getStore()
                    getAppStore = lambda s: s.parent.getAppStore()
                    getLoginSystem = lambda s: s.parent.getLoginSystem()
                yield (pin.pluginName, None, PluginSubCommand, 'Commands for '+pin.pluginName)

    def getStore(self):
        return self.parent.getStore()

    def getAppStore(self):
        return self.parent.getAppStore()

    def getLoginSystem(self):
        return self.parent.getLoginSystem()



class CreateSuperfeedrService(axiomatic.AxiomaticSubCommand):
    longdesc = 'Create a new Superfeedr service'
    synopsis = '<apiKey>'

    def parseArgs(self, key):
        self['key'] = self.decodeCommandLine(key)


    def postOptions(self):
        store = self.parent.getStore()

        util.setAPIKey(store, SuperfeedrService.apiKeyName, self['key'])

        svc = store.findOrCreate(SuperfeedrService)
        installOn(svc, store)



class Eridanus(axiomatic.AxiomaticCommand):
    name = 'eridanus'
    description = 'Eridanus mechanic'

    subCommands = [
        ('service',    None, ManageServices, 'Manage services'),
        ('plugins',    None, ManagePlugins,  'Manage plugins'),
        ('plugincmd',  None, PluginCommands, 'Plugin-specific commands'),
        ('superfeedr', None, CreateSuperfeedrService, 'Create Superfeedr service'),
        ]

    def getStore(self):
        return self.parent.getStore()

    def getAppStore(self):
        return self.getLoginSystem().accountByAddress(u'Eridanus', None).avatars.open()

    def getLoginSystem(self):
        return IRealm(self.getStore())
