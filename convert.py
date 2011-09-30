#!/usr/bin/python

import sys
import os
import shutil
from xml import sax
import re
import htmlentitydefs

from genshi.template import TemplateLoader

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

class Container(dict):
    """An object that contains members"""

    def add_member(self, name, obj):
        if name is None:
            return
        assert name not in self
        self[name] = obj

# Maps object id (int) to object
objects = {}

class Object(Container):
    def __init__(self, class_name, id):
        self.class_name = class_name
        self.id = id

    def __repr__(self):
        return self.id + ' ' + super(Container, self).__repr__()

class ObjectReference(object):
    def __init__(self, object_id):
        self.id = object_id

    def __repr__(self):
        if self.referee:
            return 'ref to ' + self.referee.__repr__()
        else:
            return 'ref to ' + self.id

    @property
    def referee(self):
        try:
            return self.dereference()
        except KeyError:
            return None

    def dereference(self):
        return objects[self.id]

def new_tracklist(parent):
    return Container()

def new_bin(parent, name):
    return str()

def new_obj(parent, ID, name=None, **attrs):
    assert not attrs or 'class' in attrs, 'Class is only optional attribute: ' + str(attrs)
    if 'class' in attrs:
        assert ID not in objects, 'Duplicate ID'
        o = Object(attrs['class'], ID)
        objects[ID] = o
    else:
        o = ObjectReference(ID)
    return o

def new_member(parent, name):
    return Container()

def new_string(parent, name, value):
    return unicode(value)

def new_int(parent, name, value):
    return int(value)

def new_float(parent, name, value):
    return float(value)

def new_item(parent, value=None):
    # TODO: should use the parent's type
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
            if not hasattr(parent, 'add_member'):
                #print('Unexpected child element to ' + str(parent))
                pass
            else:
                parent.add_member(name, obj)

    def characters(self, content):
        pass

    def skippedEntity(self, name):
        pass
        #print 'skipped entity', name


def dump(obj, members):
    members = members.split()
    for m in members:
        print m + '=' + str(obj[m]),
    print

id_counter = 1
def next_id():
    global id_counter
    id_counter += 1
    return id_counter

sources = {}
regions = {}
playlists = []
diskstreams = []
routes = []

def main(xml_file):
    source_dir, source_file = os.path.split(xml_file)
    media_dir = os.path.join(source_dir, 'Media')
    project_name, _ = os.path.splitext(source_file)

    with open(xml_file) as input:
        xml = input.read()

    # The XML may contain HTML entities which is invalid and makes the
    # parser fail. This fixes the problem:
    xml = replace_html_entities(xml)

    handler = ContentHandler()
    sax.parseString(xml, handler)


    sample_rate = 44100  # TODO: read from file

    tracklist = handler.top_object
    track_names = []

    for track_number, track in enumerate(tracklist['track'], 1):
        if track.class_name == 'MDeviceTrackEvent':
            # TODO: investigate what MDeviceTrackEvents are
            print 'IGNORING MDeviceTrackEvents'
            continue

        assert track.class_name == 'MAudioTrackEvent', 'Unexpected in tracklist: ' + track.class_name

        node = track['Node']
        track_name = node['Name']
        print 'TRACK:', track_name
        while track_name in track_names:
            print 'Warning: duplicated track name %s' % track_name
            track_name += '-' + str(track_number)
        track_names.append(track_name)

        timebase = node['Domain']['Type']  # 0=musical, 1=time
        sample_rate = 44100
        if timebase == 0:
            # Musical time base: positions are given in number of pulses.
            # There are 480 pulses in one quarter note.
            seconds_per_beat = .5  # TODO: read from file
            def timebase_to_samples(pulses):
                return int(pulses / 480.0 * seconds_per_beat * sample_rate)
        else:
            def timebase_to_samples(samples):
                return samples * sample_rate

        diskstream = {
            'id': next_id(),
            'name': track_name,
            'playlist': track_name,
        }
        diskstreams.append(diskstream)

        playlist = {
            'name': track_name,
            'diskstream_id': diskstream['id'],
            'regions': [],
        }
        playlists.append(playlist)

        route = {
            'diskstream_id': diskstream['id'],
            'io_name': track_name,
            'io_id': next_id(),
            'id1': next_id(),
            'id2': next_id(),
            'id3': next_id(),
            'id4': next_id(),
            'id5': next_id(),
            'id6': next_id(),
            'id7': next_id(),
            'id8': next_id(),
            'id9': next_id(),
        }
        routes.append(route)

        events = node['Events']
        for event_index, event in enumerate(events):
            assert event.class_name == 'MAudioEvent'
            print 'EVENT'
            dump(event, 'Start Length Offset Priority Volume')

            clip = event['AudioClip'].dereference()
            sources_key = event['AudioClip'].id
            if sources_key in sources:
                source = sources[sources_key]
            else:
                source = {
                    'id': next_id(),
                    'name': clip['Path']['Name'],
                }
                sources[sources_key] = source

            region_id = next_id()
            global_region = {
                'id': region_id,
                'name': track_name,
                'length': int(event['Length']),
                'start': 0,
                'source0': source['id'],
            }
            regions[event.id] = global_region

            playlist_region = global_region.copy()
            playlist_region['id'] = next_id()
            playlist_region['name'] = '%s %s' % (track_name, event_index + 1)
            playlist_region['position'] = timebase_to_samples(event['Start'])
            playlist_region['start'] = int(event['Offset'])
            playlist_region['flags'] = 'Opaque,DefaultFadeIn,DefaultFadeOut,WholeFile,FadeIn,FadeOut,External'
            if event['Flags'] & 2:
                playlist_region['flags'] = 'Muted,' + playlist_region['flags']

            playlist['regions'].append(playlist_region)
            print 'creating playlist region', playlist_region

    output_dir = project_name
    if os.path.exists(output_dir):
        print "Can't create directory %s: Already exists" % output_dir
        sys.exit(1)
    audio_dir = os.path.join(output_dir, 'interchange', 'session', 'audiofiles')
    os.makedirs(audio_dir)

    loader = TemplateLoader(os.path.dirname(__file__))
    tmpl = loader.load('template.ardour')
    ardour_file = tmpl.generate(
        session_name='session',
        sample_rate=sample_rate,  # TODO: read from file
        sources=sources.values(),
        regions=regions.values(),
        playlists=playlists,
        diskstreams=diskstreams,
        routes=routes,
        id_counter=id_counter,
        next_id=next_id,
        # {mathias/out 1,noise/out 1,sine/out 1}{mathias/out 2,noise/out 2,sine/out 2}
        master_inputs='{%s}{%s}' % (
            ''.join('%s/out 1' % n for n in track_names),
            ''.join('%s/out 2' % n for n in track_names),
        )
    ).render()
    
    with open(os.path.join(project_name, project_name + '.ardour'), 'w') as s:
        s.write(ardour_file)

    for source in sources.values():
        source_file = os.path.join(media_dir, source['name'])
        print 'copying', source_file
        shutil.copy(source_file, audio_dir)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print 'Usage: convert.py <xml-file>'
        sys.exit(2)
    else:
        main(sys.argv[1])
