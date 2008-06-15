from epsilon.extime import Time

from twisted.cred.portal import IRealm
from twisted.python.filepath import FilePath

from axiom.scripts import axiomatic
from axiom.dependency import installOn, uninstallFrom
from axiom.attributes import AND

from xmantissa import publicweb

from eridanus import publicpage, plugin, util
from eridanus.bot import IRCBotService, IRCBotFactoryFactory, IRCBotConfig
from eridanus.entry import EntryManager, Entry, Comment, EntryMetadata


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


def createService(siteStore, serviceID):
    fact = siteStore.findOrCreate(IRCBotFactoryFactory)
    svc = siteStore.findOrCreate(IRCBotService,
                             serviceID=serviceID,
                             factory=fact)
    installOn(svc, siteStore)
    return svc


class CreateService(axiomatic.AxiomaticSubCommand):
    longdesc = 'Create a new Eridanus service'

    optParameters = [
        ('id', None, None, 'Service identifier'),
        ]

    def getStore(self):
        return self.parent.getStore()

    def postOptions(self):
        store = self.getStore()
        createService(store, self['id'])


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


class SetupCommands(axiomatic.AxiomaticSubCommand):
    longdesc = 'Setup stuff'

    optFlags = [
        ('vhost', None, 'Setup vhost stuff'),
        ]

    def postOptions(self):
        s = self.parent.getStore()
        s.transact(self.replaceFrontPage, s)

        if self['vhost']:
            s.transact(self.setupVHost, s)

    def setupVHost(self, store):
        store.query(publicpage.VHost).deleteFromStore()
        vh = store.findOrCreate(publicpage.VHost)
        installOn(vh, store)

    def replaceFrontPage(self, store):
        store.query(publicweb.FrontPage).deleteFromStore()

        fp = store.findOrCreate(publicpage.FrontPage, prefixURL=u'')
        installOn(fp, store)


class ImportExportFile(object):
    encoding = 'utf-8'

    def __init__(self, fd):
        self.fd = fd
        self.eof = False
        self.count = 0
        self._typeConverters = {'bytes':     (self.writeline, self.readline),
                                'text':      (self.writeText, self.readText),
                                'timestamp': (self.writeTimestamp, self.readTimestamp),
                                'integer':   (self.writeInteger, self.readInteger),
                                'textlist':  (self.writeTextList, self.readTextList),
                                'boolean':   (self.writeBoolean, self.readBoolean)}

    def write(self, s):
        self.fd.write(s)

    def writeline(self, s):
        self.write(s + '\n')

    def readline(self):
        self.count += 1
        line = self.fd.readline()
        if not line:
            self.eof = True

        return line.rstrip()

    def writeInteger(self, value):
        self.writeline(str(value))

    def readInteger(self):
        return int(self.readline())

    def writeTimestamp(self, value):
        self.writeline(str(value.asPOSIXTimestamp()))

    def readTimestamp(self):
        return Time.fromPOSIXTimestamp(float(self.readline()))

    def writeText(self, value):
        if value is None:
            data = ''
        else:
            data = value.encode(self.encoding)
        self.writeline(data)

    def readText(self):
        data = self.readline()
        if not data:
            return None
        return data.decode(self.encoding)

    def writeBoolean(self, value):
        return self.writeline(str(int(value)))

    def readBoolean(self):
        return bool(int(self.readline()))

    def writeTextList(self, value):
        data = '\1'.join(t.encode(self.encoding) for t in value)
        self.writeline(data)

    def readTextList(self):
        return [t.decode(self.encoding) for t in self.readline().split('\1')]

    def writeItem(self, item, attrs):
        for attrName in attrs:
             typeName = getattr(type(item), attrName).__class__.__name__
             writer = self._typeConverters[typeName][0]
             writer(getattr(item, attrName))

    def readItem(self, itemType, attrs):
        def _readAttributes():
            for attrName in attrs:
                typeName = getattr(itemType, attrName).__class__.__name__
                reader = self._typeConverters[typeName][1]
                yield attrName, reader()

        return dict(_readAttributes())

    serviceAttrs = ['serviceID']

    def writeService(self, service):
        self.writeline('service')
        self.writeItem(service, self.serviceAttrs)

        self.writeConfig(service.config)

    def readService(self):
        return self.readItem(IRCBotService, self.serviceAttrs)

    configAttrs = ['name', 'hostname', 'portNumber', 'nickname', 'channels', 'ignores']

    def writeConfig(self, config):
        self.writeline('config')
        self.writeItem(config, self.configAttrs)

        for entryManager in config.getEntryManagers():
            self.writeEntryManager(entryManager)

    def readConfig(self):
        return self.readItem(IRCBotConfig, self.configAttrs)

    entryManagerAttrs = ['channel', 'lastEid']

    def writeEntryManager(self, entryManager):
        self.writeline('entrymanager')
        self.writeItem(entryManager, self.entryManagerAttrs)

        for entry in entryManager.getEntries(discarded=None, deleted=None):
            self.writeEntry(entry)

    def readEntryManager(self):
        return self.readItem(EntryManager, self.entryManagerAttrs)

    entryAttrs = ['eid', 'created', 'modified', 'channel', 'nick', 'url', 'title', 'occurences', 'isDiscarded', 'isDeleted']

    def writeEntry(self, entry):
        self.writeline('entry')
        self.writeItem(entry, self.entryAttrs)

        for comment in entry.allComments:
            self.writeComment(comment)

        for metadata in entry.getAllMetadata():
            self.writeMetadata(metadata)

    def readEntry(self):
        return self.readItem(Entry, self.entryAttrs)

    commentAttrs = ['created', 'nick', 'comment', 'initial']

    def writeComment(self, comment):
        self.writeline('comment')
        self.writeItem(comment, self.commentAttrs)

    def readComment(self):
        return self.readItem(Comment, self.commentAttrs)

    metadataAttrs = ['kind', 'data']

    def writeMetadata(self, metadata):
        self.writeline('metadata')
        self.writeItem(metadata, self.metadataAttrs)

    def readMetadata(self):
        return self.readItem(EntryMetadata, self.metadataAttrs)


class ExportEntries(axiomatic.AxiomaticSubCommand):
    longdesc = 'Export linkdb entries to disk'

    optParameters = [
        ('path', 'p', None, 'Path to output export data to'),
        ]

    def getStore(self):
        return self.parent.getStore()

    def getAppStore(self):
        return self.parent.getAppStore()

    def postOptions(self):
        appStore = self.getAppStore()
        store = self.getStore()
        # XXX: old stuff is in the wrong damn store
        appStore = store

        outroot = FilePath(self['path'])
        if not outroot.exists():
            outroot.makedirs()

        for i, service in enumerate(appStore.query(IRCBotService)):
            print 'Processing service %r...' % (service.serviceID,)

            fd = outroot.child(str(i)).open('wb')
            ief = ImportExportFile(fd)
            ief.writeService(service)


class ImportEntries(axiomatic.AxiomaticSubCommand):
    longdesc = 'Import linkdb entries from an export'

    optParameters = [
        ('path', 'p', None, 'Path to read export data from'),
        ]

    def getStore(self):
        return self.parent.getStore()

    def getAppStore(self):
        return self.parent.getAppStore()

    def postOptions(self):
        appStore = self.getAppStore()
        siteStore = self.getStore()

        inroot = FilePath(self['path'])

        availableModes = ['service', 'config', 'entrymanager', 'entry', 'comment', 'metadata']

        mode = None
        service = None
        config = None
        entryManager = None
        entry = None

        for fp in inroot.globChildren('*'):
            fd = fp.open()
            ief = ImportExportFile(fd)

            while True:
                line = ief.readline()
                if ief.eof:
                    break

                if line in availableModes:
                    mode = line

                if mode == 'service':
                    kw = ief.readService()
                    service = createService(siteStore, **kw)
                elif mode == 'config':
                    kw = ief.readConfig()
                    config = IRCBotConfig(store=siteStore, **kw)
                    service.configID = config.storeID
                elif mode == 'entrymanager':
                    assert config is not None
                    kw = ief.readEntryManager()
                    entryManager = EntryManager(store=appStore, config=config, **kw)
                elif mode == 'entry':
                    assert entryManager is not None
                    kw = ief.readEntry()
                    print 'Creating entry #%(eid)s for %(channel)s...' % kw
                    entry = Entry(store=appStore, **kw)
                elif mode == 'comment':
                    assert entry is not None
                    kw = ief.readComment()
                    Comment(store=appStore, parent=entry, **kw)
                elif mode == 'metadata':
                    assert entry is not None
                    kw = ief.readMetadata()
                    EntryMetadata(store=appStore, entry=entry, **kw)


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


class EndowPlugin(axiomatic.AxiomaticSubCommand):
    longdesc = 'Endow a user with a plugin'

    synopsis = '<user@domain> <pluginName>'

    def parseArgs(self, userdomain, pluginName):
        username, domain = self.decodeCommandLine(userdomain).split(u'@', 1)
        self['username'] = username
        self['domain'] = domain
        self['pluginName'] = self.decodeCommandLine(pluginName)

    def postOptions(self):
        loginSystem = self.parent.getLoginSystem()
        loginAccount = loginSystem.accountByAddress(self['username'], self['domain'])
        assert loginAccount is not None, 'No such user'
        userStore = loginAccount.avatars.open()
        plugin.installPlugin(userStore, self['pluginName'])


class ManagePlugins(axiomatic.AxiomaticSubCommand):
    longdesc = 'Manage plugins'

    subCommands = [
        ('install', None, InstallPlugin, 'Install a plugin'),
        ('endow', None, EndowPlugin, 'Endow a user with a plugin'),
        ]

    def getStore(self):
        return self.parent.getStore()

    def getAppStore(self):
        return self.parent.getAppStore()

    def getLoginSystem(self):
        return self.parent.getLoginSystem()


class Eridanus(axiomatic.AxiomaticCommand):
    name = 'eridanus'
    description = 'Eridanus mechanic'

    subCommands = [
        ('service', None, ManageServices, 'Manage services'),
        ('setup',   None, SetupCommands,  'Setup stuff'),
        ('export',  None, ExportEntries,  'Export entries'),
        ('import',  None, ImportEntries,  'Import entries'),
        ('plugins', None, ManagePlugins,  'Manage plugins'),
        ]

    def getStore(self):
        return self.parent.getStore()

    def getAppStore(self):
        return self.getLoginSystem().accountByAddress(u'Eridanus', None).avatars.open()

    def getLoginSystem(self):
        return IRealm(self.getStore())
