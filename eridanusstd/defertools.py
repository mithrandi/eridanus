import itertools
from collections import deque

from twisted.internet import defer

from eridanusstd import errors


class LazyQueue(object):
    """
    A lazy queue based around Deferreds.

    Inputs are enqueued by calling the filler, as the filler results become
    available, outputs are fired with results.  If the queue runs dry, the
    filler is called again to populate the input queue until the filler
    itself is empty.

    One such use for this is for lazily flattening paginated output from a web
    search:  The filler yields results for one page at a time, once all of
    these are consumed, the next result set is fetched and the process repeats.

    @type filler: C{callable} returning a deferred that fires with an
        iterable
    @ivar filler: The callable used to fill the input queue

    @type input: C{collections.deque}
    @ivar input: The input queue

    @type output: C{collections.deque}
    @ivar output: The output queue

    @type filling: C{bool}
    @ivar filling: Flag indicating whether the filler is currently running or
        not

    @type empty: C{bool}
    @ivar empty: Flag indicating whether the input queue is empty or not
    """
    def __init__(self, filler):
        """
        Initialise the queue.

        @type filler: C{callable} returning a deferred that fires with an
            iterable
        @param filler: The callable used to fill the input queue, called with
            0 arguments
        """
        self.filler = filler
        self.input = deque()
        self.output = deque()
        self.filling = False
        self.empty = False

    def fill(self):
        """
        Fill the input queue.
        """
        def _fill(data):
            self.filling = False
            data = list(data)
            if not data:
                self.empty = True
            else:
                self.input.extendleft(data)

            self.pump()

        self.filling = True
        return self.filler().addCallback(_fill)

    def pump(self):
        """
        Transform pending inputs into outputs.

        If the input queue runs dry before the output queue, L{self.fill} will
        be called to fill the input queue.  If L{self.empty} is true, any
        deferreds still in the output queue will have their errback triggered
        with L{errors.NoMoreItems}.
        """
        input = self.input
        output = self.output

        while input and output:
            output.pop().callback(input.pop())

        if output:
            if self.empty:
                while output:
                    output.pop().errback(errors.NoMoreItems())
            elif not self.filling:
                self.fill()

    def next(self):
        """
        Get a deferred that will fire with a queued input.

        @rtype: C{defer.Deferred}
        @return: A deferred that will fire with the next queued input, when it
            becomes available
        """
        d = defer.Deferred()
        self.output.appendleft(d)
        self.pump()
        return d

    def __iter__(self):
        return self


def all(queue):
    """
    Retrieve all items from C{queue}

    @type queue: L{LazyQueue}

    @rtype: C{defer.Deferred}
    @return: A deferred that fires with a list of all the items in C{queue}
    """
    items = []

    def _cb(item):
        items.append(item)
        return queue.next().addCallbacks(_cb, _eb)

    def _eb(f):
        f.trap(errors.NoMoreItems)
        return items

    return queue.next().addCallbacks(_cb, _eb)


def slice(queue, n):
    """
    Slice a L{LazyQueue}.

    @type queue: L{LazyQueue}

    @type n: C{int}
    @param n: The number of items to slice from the beginning of the queue

    @rtype: C{defer.Deferred}
    @return: A deferred that fires with a list of the sliced items
    """
    def _cb(item):
        return [item]

    def _eb(f):
        f.trap(errors.NoMoreItems)
        return []

    d = defer.gatherResults(
        [d.addCallbacks(_cb, _eb)
         for d in itertools.islice(queue, n)])

    return d.addCallback(lambda results: sum(results, []))
