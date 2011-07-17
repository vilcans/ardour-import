#!/usr/bin/python

#from xml.dom import minidom
from xml import sax
import re
import htmlentitydefs

def debug():
    import pudb
    pudb.set_trace()

def replace_html_entities(text):
   """
   Replaces HTML character entities with the a numeric entity.
   E.g. replaces '&aring;' with '&#229;'
   Keeps &lt;, &gt; and &amp; intact as they are defined in XML.

   @param text The source text that may contain HTML entities.
   @return The fixed markup.
   """
   def fixup(m):
      text = m.group(0)
      if text[:2] == "&#" or text[1:-1] in ('amp', 'gt', 'lt'):
          return text
      try:
          return '&#' + str(htmlentitydefs.name2codepoint[text[1:-1]]) + ';'
      except KeyError:
          return text
   return re.sub("&#?\w+;", fixup, text)

class Container(object):
    """An object that contains members"""

    def __init__(self):
        self.members = {}

    def add_member(self, name, obj):
        if name is None:
            print 'No name given for object', obj
            return
        if name in self.members:
            print name, 'already in', self.members
            return
        self.members[name] = obj

# Maps object id (int) to object
objects = {}

class Object(Container):
    def __init__(self, id):
        #super(Container, self).__init__()
        self.members = {}
        self.id = id

class ObjectReference(object):
    def __init__(self, object_id):
        self.id = object_id

def new_tracklist(parent):
    return Container()

def new_bin(parent, name):
    return str()

def new_obj(parent, ID, name=None, **attrs):
    assert not attrs or 'class' in attrs, 'Class is only optional attribute: ' + str(attrs)
    if 'class' in attrs:
        o = Object(ID)
        assert ID not in objects, 'Duplicate ID'
        objects[ID] = o
        #print 'found object', ID
    else:
        o = ObjectReference(ID)
    return o

def new_member(parent, name):
    return object()

def new_string(parent, name, value):
    return unicode(value)

def new_int(parent, name, value):
    return int(value)

def new_float(parent, name, value):
    return float(value)

def new_item(parent, value=None):
    return object()

class new_list(list):
    def __init__(self, parent, name, type):
        self.type = type

    def add_member(self, name, obj):
        assert name is None, 'Expected no name for a member or a list: ' + name
        self.append(obj)

def create_object(parent, type_name, attributes):
    function_name = 'new_' + type_name
    try:
        constructor = globals()[function_name]
    except KeyError:
        raise RuntimeError('No creator function with name ' + function_name)

    try:
        return constructor(parent=parent, **attributes)
    except Exception as e:
        print str(constructor) + ' failed:' + str(e)
        import pudb; pudb.set_trace()
        raise e

class ContentHandler(sax.ContentHandler):

    def startDocument(self):
        self.object_stack = []

    def startElement(self, name, attrs):
        #print 'START', name, attrs

        if self.object_stack:
            _, parent = self.object_stack[-1]
        else:
            parent = None

        obj = create_object(parent, name, attrs)
        self.object_stack.append((attrs.get('name', None), obj))

    def endElement(self, element_name):
        name, obj = self.object_stack.pop()
        if self.object_stack == []:
            self.top_object = obj
        else:
            _, parent = self.object_stack[-1]
            if hasattr(parent, 'add_member'):
                parent.add_member(name, obj)

    def characters(self, content):
        pass

    def skippedEntity(self, name):
        print 'skipped entity', name

with open('slatt.xml') as input:
    xml = input.read()

# The XML may contain HTML entities which is invalid and makes the
# parser fail. This fixes the problem:
xml = replace_html_entities(xml)

#dom = minidom.parseString(xml)

#parser = sax.make_parser()
handler = ContentHandler()
sax.parseString(xml, handler)

print 'top members', handler.top_object.members
