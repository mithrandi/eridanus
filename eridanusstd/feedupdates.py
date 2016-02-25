from axiom.item import Item
from axiom.attributes import text, inmemory



class SubscribedFeed(Item):
    """
    Persistent state for subscribed feeds.

    Subscription identifiers must be unique to the subscriber.
    """
    id = text(doc="""
    Subscription identifier unique to C{subscriber}.
    """, allowNone=False)

    url = text(doc="""
    URL of the subscribed feed.
    """, allowNone=False)

    subscriber = text(doc="""
    Application specific subscriber identifier.
    """, allowNone=False)

    formatting = text(doc="""
    Entry formatting type.
    """, allowNone=False)

    source = inmemory()
    _unsubscribe = inmemory()

    def activate(self):
        self.source = None
        self._unsubscribe = None


    def subscribe(self, service, callback):
        """
        Subscribe to notifications for this item's URL.
        """
        d = service.subscribe(self.url, callback)

        @d.addCallback
        def subscribed(unsubscribe):
            self._unsubscribe = unsubscribe
            return self

        return d


    def unsubscribe(self, service):
        """
        Unsubscribe from notifications for this item's URL and delete the item.
        """
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None

        def _unsubscribe(dummy):
            self.deleteFromStore()
            self.source = None

        return service.unsubscribe(self.url).addCallback(_unsubscribe)
