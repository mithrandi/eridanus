import cairo
from itertools import izip
from StringIO import StringIO

from pycha.chart import Option
from pycha.pie import PieChart
from pycha.color import DEFAULT_COLOR

from twisted.python import log

from nevow.inevow import IRequest
from nevow.rend import Page


def pieChart(fd, width, height, title, data, labels, bgColor=None, labelColor='#000000', colorScheme=DEFAULT_COLOR):
    dataSet = [(name, [[0, value]]) for name, value in izip(labels, data)]
    axisLabels = [dict(v=i, label=label) for i, label in enumerate(labels)]

    options = Option(
        title=title,
        titleFont='Times',
        titleFontSize=24,
        pieRadius=0.35,

        legend=Option(hide=True),
        colorScheme=colorScheme,
        background=Option(baseColor=bgColor),
        axis=Option(labelColor=labelColor,
                    x=Option(ticks=axisLabels)))

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    chart = PieChart(surface, options)
    chart.addDataset(dataSet)
    chart.render()

    surface.write_to_png(fd)


def contributors(manager, limit=10, **kw):
    labels, data = zip(*sorted(manager.topContributors(limit=limit), key=lambda x: x[1]))
    fd = StringIO()

    title = u'Top %d %s contributors' % (len(data), manager.channel)
    pieChart(fd=fd,
             width=700,
             height=700,
             title=title,
             data=data,
             labels=labels,
             **kw)

    fd.seek(0)
    return fd
