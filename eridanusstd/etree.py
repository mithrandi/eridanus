"""
Helper module that imports ElementTree stuff from wherever we can find it.
"""

try:
    # Python 2.5 stdlib
    from xml.etree.ElementTree import *
    from xml.etree.ElementTree import _namespace_map
except ImportError:
    # External elementtree library
    from elementtree.ElementTree import *
    from elementtree.ElementTree import _namespace_map
