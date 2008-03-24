from axiom.scripts import axiomatic
from axiom.dependency import installOn, uninstallFrom
from axiom.attributes import AND

from xmantissa import publicweb

from eridanus import publicpage
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

        if self['host']:
            config.hostname = self['host']
        if self['port']:
            config.portNumber = int(self['port'])
        if self['nick']:
            config.nickname = self['nick'].decode('utf-8')
        if self['channels']:
            config.channels = self['channels'].decode('utf-8').split(u',')
        if self['ignores']:
            config.ignores = self['ignores'].decode('utf-8').split(u',')


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


class ManageServices(axiomatic.AxiomaticSubCommand):
    longdesc = 'Manage Eridanus services'

    subCommands = [
        ('create', None, CreateService, 'Create a new service'),
        ('remove', None, RemoveService, 'Remove an existing service'),
        ('config', None, ConfigureService, 'Set service configuration data'),
        ]

    def getStore(self):
        return self.parent.getStore()


class SetupCommands(axiomatic.AxiomaticSubCommand):
    longdesc = 'Setup stuff'

    def postOptions(self):
        s = self.parent.getStore()
        s.transact(self.replaceFrontPage, s)

    def replaceFrontPage(self, store):
        store.query(publicweb.FrontPage).deleteFromStore()

        fp = store.findOrCreate(publicpage.FrontPage, prefixURL=u'')
        installOn(fp, store)


class Eridanus(axiomatic.AxiomaticCommand):
    name = 'eridanus'
    description = 'Eridanus mechanic'

    subCommands = [
        ('service', None, ManageServices, 'Manage services'),
        ('setup', None, SetupCommands, 'Setup stuff'),
        ]

    def getStore(self):
        return self.parent.getStore()
