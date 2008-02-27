from axiom.scripts import axiomatic
from axiom.dependency import installOn

#from xmantissa import publicweb

#from eridanus import publicpage
from eridanus.bot import IRCBotService, IRCBotFactoryFactory, IRCBotConfig


class ConfigureService(axiomatic.AxiomaticSubCommand):
    longdesc = 'Configure an Eridanus service'

    optParameters = [
        ('id',       None, None, 'Service identifier'),
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

        if 'host' in self:
            config.hostname = self['host']
        if 'port' in self:
            config.portNumber = int(self['port'])
        if 'nick' in self:
            config.nickname = self['nick'].decode('utf-8')
        if 'channels' in self:
            config._channels = self['channels'].decode('utf-8')
        if 'ignores' in self:
            config._ignores = self['ignores'].decode('utf-8')


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


class ManageServices(axiomatic.AxiomaticSubCommand):
    longdesc = 'Manage Eridanus services'

    subCommands = [
        ('create', None, CreateService, 'Create a new service'),
        ('config', None, ConfigureService, 'Set service configuration data'),
        ]

    def getStore(self):
        return self.parent.getStore()


class Eridanus(axiomatic.AxiomaticCommand):
    name = 'eridanus'
    description = 'Eridanus mechanic'

    subCommands = [
        ('service', None, ManageServices, 'Manage services'),
        ]

    def getStore(self):
        return self.parent.getStore()

    #def postOptions(self):
    #    s = self.parent.getStore()
    #    s.transact(self.installServices, s)
    #    #s.transact(self.replaceFrontPage, s)

    #def replaceFrontPage(self, store):
    #    store.query(publicweb.FrontPage).deleteFromStore()
    #
    #    fp = store.findOrCreate(publicpage.FrontPage, prefixURL=u'')
    #    installOn(fp, store)
