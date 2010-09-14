import html5lib



def parseHTML(data):
    return html5lib.parse(data, treebuilder='lxml')
