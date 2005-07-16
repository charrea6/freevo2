# -*- coding: iso-8859-1 -*-
# -----------------------------------------------------------------------------
# theme.py - xml based theme engine
# -----------------------------------------------------------------------------
# $Id$
#
# This module handles the current theme for Freevo based on the fxd settings.
# Besides getting the current theme and changing it, there are also functions
# to get a font, an image or an icon based on the name. All functions for the
# interface to Freevo are on the top of this file.
#
# TODO: o major cleanup
#       o make fxd parsing faster
#       o respect coding guidelines
#
# -----------------------------------------------------------------------------
# Freevo - A Home Theater PC framework
# Copyright (C) 2002-2004 Krister Lagerstrom, Dirk Meyer, et al.
#
# First Version: Dirk Meyer <dmeyer@tzi.de>
# Maintainer:    Dirk Meyer <dmeyer@tzi.de>
#
# Please see the file freevo/Docs/CREDITS for a complete list of authors.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MER-
# CHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
#
# -----------------------------------------------------------------------------

# list of functions this module provides
__all__ = [ 'get', 'set', 'font', 'image', 'icon', 'set_base_fxd' ]

# python imports
import os
import copy
import re

# freevo imports
import config
import util
import plugin
from event import THEME_CHANGE

# gui imports
from font import get as get_font_object

import logging
log = logging.getLogger('gui')

# Internal fxd file version
FXD_FORMAT_VERSION = 2


# -------------- Interface for Freevo ---------------------------------------

current_theme = None

def get():
    """
    get current fxd theme
    """
    global current_theme
    if not current_theme:
        init_module()
    return current_theme


def set(new):
    """
    set current fxd theme
    """
    global current_theme
    if not current_theme:
        init_module()
    if new == current_theme:
        # new and old theme are the same,
        # don't do anything
        return current_theme
    if isinstance(new, str):
        # new theme is only a string, load the theme file
        # based on the current theme
        log.info('loading new theme %s', new)
        filename = new
        if new and vfs.isfile(os.path.join(new, 'folder.fxd')):
            new = vfs.abspath(os.path.join(new, 'folder.fxd'))
        elif new and vfs.isfile(new):
            new = vfs.abspath(new)
        theme = copy.copy(current_theme)
        try:
            theme.load(new)
            theme.prepare()
        except:
            log.exception('XML file corrupt:')
            theme = copy.copy(current_theme)
        theme.filename = new
        current_theme = theme
    else:
        # set the global theme variable
        current_theme = new
    # notify other parts of Freevo about the theme change
    # FIXME: maybe this is a signal.
    THEME_CHANGE.post()
    # return new theme in case the new one was given to this
    # function as string and the caller wants the object
    return current_theme


def font(name):
    """
    Get the font with the given name. If the font is not found,
    the default font will be returned
    """
    return current_theme.get_font(name)


def image(name):
    """
    Get the image filename with the given name. If no image is found
    this function will return None.
    """
    return current_theme.get_image(name)


def icon(name):
    """
    Get the icon filename with the given name. This function will
    search the icon in the theme icon directory. If no icon is found
    this function will return None.
    """
    return current_theme.get_icon(name)




# -------------- Private classes and functions ------------------------------

#
# Help functions
#

def attr_int(node, attr, default, scale=0.0):
    """
    return the attribute as integer
    """
    try:
        if node.attrs.has_key(('', attr)):
            val = node.attrs[('', attr)]
            if val == 'line_height':
                return -1
            if not scale:
                return int(val)
            
            new_val = ''

            while val:
                ppos = val[1:].find('+') + 1
                mpos = val[1:].find('-') + 1
                if ppos and mpos:
                    pos = min(ppos, mpos)
                elif ppos or mpos:
                    pos = max(ppos, mpos)
                else:
                    pos = len(val)

                try:
                    i = int(round(scale*int(val[:pos])))
                    if i < 0:
                        new_val += str(i)
                    else:
                        new_val += '+' + str(i)
                except ValueError:
                    if val[:pos].upper() in ( '+MAX', 'MAX', '-MAX' ):
                        new_val += val[:pos].upper()
                    elif val[:pos].lower() in ( '+font_h', 'font_h',
                                                '-font_h' ):
                        new_val += val[:pos].lower()
                    else:
                        log.error('unsupported value %s' % val[:pos])
                val = val[pos:]

            try:
                return int(new_val)
            except ValueError:
                return str(new_val)

    except ValueError:
        pass
    return default


def attr_float(node, attr, default):
    """
    return the attribute as integer
    """
    try:
        if node.attrs.has_key(('', attr)):
            return float(node.attrs[('', attr)])
    except ValueError:
        pass
    return default


def attr_col(node, attr, default):
    """
    return the attribute in hex as integer or str for color name
    """
    try:
        if node.attrs.has_key(('', attr)):
            if node.attrs[('', attr)][:2] == '0x':
                return long(node.attrs[('', attr)], 16)
            else:
                return node.attrs[('', attr)].encode(config.LOCALE)
    except ValueError:
        pass
    return default


def attr_visible(node, attr, default):
    """
    return True or False based in the attribute values 'yes' or 'no'
    """
    if node.attrs.has_key(('', attr)):
        if node.attrs[('', attr)] == "no":
            return ''
        return node.attrs[('', attr)].encode(config.LOCALE)
    return default


def attr_str(node, attr, default):
    """
    return the attribute as string
    """
    if node.attrs.has_key(('', attr)):
        return node.attrs[('', attr)].encode(config.LOCALE)
    return default


def search_file(file, search_dirs):
    for s_dir in search_dirs:
        dfile=os.path.join(s_dir, file)

        if vfs.isfile(dfile):
            return vfs.abspath(dfile)

        if vfs.isfile("%s.png" % dfile):
            return vfs.abspath("%s.png" % dfile)

        if vfs.isfile("%s.jpg" % dfile):
            return vfs.abspath("%s.jpg" % dfile)

    log.error('skin error: can\'t find image %s' % file)
    log.info('image search path is:')
    for s in search_dirs:
        log.info(s)
    return ''


def get_expression(expression):
    """
    create the python expression
    """
    exp = ''
    for b in expression.split(' '):
        if b in ( 'and', 'or', 'not', '==', '!=' ):
            # valid operator
            exp += ' %s' % ( b )

        elif b.startswith('\'') and b.endswith('\''):
            # string
            exp += ' %s' % ( b )

        elif b.startswith('function:'):
            exp += ' %s()' % b[9:]

        elif b[ :4 ] == 'len(' and b.find( ')' ) > 0 and \
                 len(b) - b.find(')') < 5:
            # lenght of something
            exp += ' attr("%s") %s' % ( b[ : ( b.find(')') + 1 ) ],
                                        b[ ( b.find(')') + 1 ) : ])
        else:
            # an attribute
            exp += ' attr("%s")' % b
    return exp.strip()

# ======================================================================

#
# data structures
#


# ======================================================================

class MainMenuItem(object):
    def __init__(self):
        self.label   = ''
        self.name    = ''
        self.icon    = ''
        self.image   = ''
        self.outicon = ''

    def parse(self, node, scale, c_dir=''):
        self.label    = attr_str(node, "label", self.label)
        self.name     = attr_str(node, "name",  self.name)
        self.icon     = attr_str(node, "icon",  self.icon)
        self.image    = attr_str(node, "image", self.image)
        self.outicon  = attr_str(node, "outicon",  self.outicon)

    def prepare(self, search_dirs, image_names):
        if self.image:
            self.image = search_file(self.image, search_dirs)


# ======================================================================

class MainMenu(object):
    def __init__(self):
        self.items    = {}
        self.imagedir = ''

    def parse(self, menu_node, scale, c_dir=''):
        self.imagedir = attr_str(menu_node, "imagedir", self.imagedir)
        for node in menu_node.children:
            if node.name == u'item':
                item = MainMenuItem()
                item.parse(node, scale, c_dir)
                self.items[item.label] = item

    def prepare(self, search_dirs, image_names):
        self.imagedir = os.path.join(config.IMAGE_DIR, self.imagedir)
        for i in self.items:
            self.items[i].prepare(search_dirs, image_names)

# ======================================================================
# ======================================================================

XML_types = {
    'x'        : ('int',  1),
    'y'        : ('int',  2),
    'width'    : ('int',  1),
    'height'   : ('int',  2),
    'spacing'  : ('int',  3),
    'hours_per_page': ('int',  3),
    'color'    : ('col',  0),
    'alpha'    : ('int',  0),
    'bgcolor'  : ('col',  0),
    'size'     : ('int',  3),
    'radius'   : ('int',  3),
    'label'    : ('str',  0),
    'font'     : ('str',  0),
    'layout'   : ('str',  0),
    'type'     : ('str',  0),
    'align'    : ('str',  0),
    'valign'   : ('str',  0),
    'filename' : ('str', 0),
    'image'    : ('str', 0),
    'name'     : ('str',  0),
    'visible'  : ('visible', 0),
    'border'   : ('visible', 0),
    'icon'     : ('str', 0),
    'ellipses' : ('str', 0),
    'dim'      : ('visible', 0),
}

def int2col(col):
    """
    Convert a 32-bit TRGB color to a 4 element tuple
    """
    if isinstance(col, tuple):
        return col
    if col == None:
        return (0,0,0,255)
    a = 255 - ((col >> 24) & 0xff)
    r = (col >> 16) & 0xff
    g = (col >> 8) & 0xff
    b = (col >> 0) & 0xff
    if a == 255:
        return (r, g, b)
    return (r, g, b, a)



class XML_data(object):
    """
    a basic data element for parsing the attributes
    """

    def __init__(self, content):
        """
        create all object variables for this type
        """
        self.content = content
        for c in content:
            if XML_types[c][0] in ('str', 'file', 'font'):
                setattr(self, c, '')
            elif XML_types[c][0] in ('visible',):
                setattr(self, c, 'yes')
            else:
                setattr(self, c, 0)


    def parse(self, node, scale, current_dir):
        """
        parse the node
        """
        for attr in node.attrs:
            c = attr[1]

            if c in self.content:
                this_scale = 0
                if XML_types[c][1] == 1:
                    this_scale = scale[0]
                if XML_types[c][1] == 2:
                    this_scale = scale[1]
                if XML_types[c][1] == 3:
                    this_scale = min(scale[0], scale[1])

                if this_scale:
                    setattr(self, c, attr_int(node, c, getattr(self, c),
                                              this_scale))
                else:
                    e = 'attr_%s(node, "%s", self.%s)' % \
                        (XML_types[c][0], c, c)
                    setattr(self, c, eval(e))


    def prepare(self, font_dict=None, color_dict=None):
        """
        basic prepare function
        """
        try:
            if self.visible not in ('', 'yes'):
                if len(self.visible) > 4 and self.visible[:4] == 'not ':
                    p = plugin.getbyname(self.visible[4:])
                else:
                    p = plugin.getbyname(self.visible)
                if len(self.visible) > 4 and self.visible[:4] == 'not ':
                    self.visible = not p
                else:
                    self.visible = p
        except (TypeError, AttributeError):
            pass
        # Brute force, maybe this item has no font or color attributes.
        # But catching exceptions is faster than searching first
        if font_dict:
            try:
                self.font = font_dict[self.font]
            except (TypeError, KeyError):
                self.font = font_dict['default']
            except AttributeError:
                pass
        if color_dict:
            try:
                self.color = color_dict[self.color]
            except (TypeError, KeyError, AttributeError):
                pass
            try:
                self.bgcolor = color_dict[self.bgcolor]
            except (TypeError, KeyError, AttributeError):
                pass

        try:
            self.color = int2col(self.color)
        except (TypeError, AttributeError):
            pass
        try:
            self.bgcolor = int2col(self.bgcolor)
        except (TypeError, AttributeError):
            pass


# ======================================================================


class Menu(object):
    """
    the menu style definitions
    """
    def __init__(self):
        self.style = []
        pass

    def parse(self, node, scale, current_dir):
        for subnode in node.children:
            if subnode.name == 'style':
                self.style += [ [ attr_str(subnode, 'image', ''),
                                  attr_str(subnode, 'text', '') ] ]

    def prepare(self, menuset, layout):
        for s in self.style:
            for i in range(2):
                if s[i]:
                    s[i] = copy.deepcopy(menuset[s[i]])
                    s[i].prepare(layout)
                else:
                    s[i] = None



class MenuSet(object):
    """
    the complete menu with the areas screen, title, subtitle, view, listing
    and info in it
    """
    def __init__(self):
        self.areas = [ 'screen', 'title', 'subtitle', 'view', 'listing',
                       'info', 'progress' ]
        for c in self.areas:
            setattr(self, c, Area(c))


    def parse(self, node, scale, current_dir):
        for subnode in node.children:
            if not hasattr(self, subnode.name):
                setattr(self, subnode.name, Area(subnode.name))
                self.areas.append(subnode.name)
            getattr(self, subnode.name).parse(subnode, scale, current_dir)


    def prepare(self, layout):
        for c in self.areas:
            getattr(self, c).prepare(layout)


class Area(XML_data):
    """
    area class (inside menu)
    """
    def __init__(self, name):
        XML_data.__init__(self, ('visible', 'layout', 'x', 'y', 'width',
                                 'height'))
        self.name = name
        if name == 'listing':
            self.images = {}
        self.x = -1
        self.y = -1
        self.visible = False
        self.images = {}

    def parse(self, node, scale, current_dir):
        if self.x == -1:
            self.visible = True

        x = self.x
        y = self.y
        XML_data.parse(self, node, scale, current_dir)
        if x != self.x:
            try:
                self.x += config.GUI_OVERSCAN_X
            except TypeError:
                pass
        if y != self.y:
            try:
                self.y += config.GUI_OVERSCAN_Y
            except TypeError:
                pass
        for subnode in node.children:
            if subnode.name == u'image' and self.name == 'listing':
                label = attr_str(subnode, 'label', '')
                if label:
                    if not label in self.images:
                        self.images[label] = Image()
                    x,y = self.images[label].x, self.images[label].y
                    self.images[label].parse(subnode, scale, current_dir)
                    if x != self.images[label].x:
                        try:
                            self.images[label].x += config.GUI_OVERSCAN_X
                        except TypeError:
                            pass
                    if y != self.images[label].y:
                        try:
                            self.images[label].y += config.GUI_OVERSCAN_Y
                        except TypeError:
                            pass

    def prepare(self, layout):
        XML_data.prepare(self)
        if self.visible:
            self.layout = layout[self.layout]
        else:
            self.layout = None

    def rect(self, type):
        if type == 'screen':
            return (self.x - config.GUI_OVERSCAN_X,
                    self.y - config.GUI_OVERSCAN_X,
                    self.width + 2 * config.GUI_OVERSCAN_X,
                    self.height + 2 * config.GUI_OVERSCAN_X)
        return (self.x, self.y, self.width, self.height)

    def pos(self, type):
        if type == 'screen':
            return (self.x - config.GUI_OVERSCAN_X,
                    self.y - config.GUI_OVERSCAN_X)
        return (self.x, self.y)


# ======================================================================

class Layout(object):
    """
    layout tag
    """
    def __init__(self, label):
        self.label = label
        self.background = ()
        self.content = Content()

    def parse(self, node, scale, current_dir):
        for subnode in node.children:
            if subnode.name == u'background':
                self.background = []
                for bg in subnode.children:
                    if bg.name == 'image':
                        b = Image()
                    elif bg.name == 'rectangle':
                        b = Rectangle()
                    else:
                        continue
                    b.parse(bg, scale, current_dir)
                    self.background += [ b ]

            if subnode.name == u'content':
                self.content.parse(subnode, scale, current_dir)

    def prepare(self, font, color, search_dirs, image_names):
        self.content.prepare(font, color, search_dirs)
        for b in self.background:
            b.prepare(color, search_dirs, image_names)


class ContentItem(XML_data):
    """
    class for <item> inside content
    """
    def __init__(self):
        XML_data.__init__(self, ('font', 'align', 'valign', 'height',
                                 'width', 'icon'))
        self.rectangle = None
        self.shadow    = None
        self.cdata     = ''
        self.fcontent  = []
        

class Content(XML_data):
    """
    content inside a layout
    """
    def __init__(self):
        XML_data.__init__(self, ('type', 'spacing', 'x', 'y', 'width',
                                 'height', 'font', 'align', 'valign', 'color',
                                 'hours_per_page'))
        self.types = {}
        self.cdata = ''
        self.hours_per_page = 2

    def parse(self, node, scale, current_dir):
        XML_data.parse(self, node, scale, current_dir)
        self.cdata = node.textof()
        for subnode in node.children:
            if subnode.name == u'item':
                type = attr_str(subnode, "type", '')
                if type and not self.types.has_key(type):
                    self.types[type] = ContentItem()
                if type:
                    self.types[type].parse(subnode, scale, current_dir)
                    self.types[type].cdata = subnode.textof()
                    delete_fcontent = True
                    for rnode in subnode.children:
                        if rnode.name == u'rectangle':
                            self.types[type].rectangle = Rectangle()
                            self.types[type].rectangle.parse(rnode, scale,
                                                             current_dir)
                        if rnode.name == u'shadow':
                            self.types[type].shadow = XML_data(('visible',
                                                                'color', 'x',
                                                                'y'))
                            self.types[type].shadow.parse(rnode, scale,
                                                          current_dir)

                        elif rnode.name in ( u'if', u'text', u'newline',
                                             u'goto_pos', u'img' ):
                            if delete_fcontent:
                                self.types[ type ].fcontent = [ ]
                            delete_fcontent = False
                            child = None
                            if rnode.name == u'if':
                                child = FormatIf()
                            elif rnode.name == u'text':
                                child = FormatText()
                            elif rnode.name == u'newline':
                                child = FormatNewline()
                            elif rnode.name == u'goto_pos':
                                child = FormatGotopos()
                            elif rnode.name == u'img':
                                child = FormatImg()

                            self.types[ type ].fcontent += [ child ]
                            self.types[ type ].fcontent[-1].parse(rnode, scale,
                                                                  current_dir)

        if not self.types.has_key('default'):
            self.types['default'] = ContentItem()


    def prepare(self, font, color, search_dirs):
        XML_data.prepare(self, font, color)
        for type in self.types:
            if self.types[type].font:
                self.types[type].font = font[self.types[type].font]
            else:
                self.types[type].font = None
            if self.types[type].rectangle:
                self.types[type].rectangle.prepare(color)
            if self.types[type].shadow:
                self.types[type].shadow.prepare(None, color)
            for i in self.types[type].fcontent:
                i.prepare( font, color, search_dirs )



# ======================================================================
# Formating

i18n_re = re.compile('^( ?)(.*?)([:,]?)( ?)$')

class FormatText(XML_data):
    def __init__( self ):
        XML_data.__init__( self, ( 'align', 'valign', 'font', 'width',
                                   'height', 'ellipses', 'dim') )
        self.mode     = 'hard'
        self.align    = 'left'
        self.ellipses = '...'
        self.dim      = True
        self.height   = -1
        self.text     = ''
        self.expression = None
        self.x = 0
        self.y = 0
        self.type = 'text'

    def __str__( self ):
        str = "FormatText( Text: '%s', Expression: '%s', "+\
              "Mode: %s, Font: %s, Width: %s, "+\
              "Height: %s, x: %s, y: %s ) "
        str = str % ( self.text, self.expression,
                      self.mode, self.font, self.width, self.height,
                      self.x, self.y )
        return str


    def parse( self, node, scale, c_dir = '' ):
        XML_data.parse( self, node, scale, c_dir )
        self.text = node.textof()
        if self.text:
            m = i18n_re.match(self.text).groups()
            # translate
            self.text = m[0] + _(m[1]) + m[2] + m[3]
        self.mode = attr_str( node, 'mode', self.mode )
        if self.mode != 'hard' and self.mode != 'soft':
            self.mode = 'hard'
        self.expression = attr_str( node, 'expression', self.expression )
        if self.expression:
            self.expression = get_expression(self.expression.strip())



    def prepare(self, font, color, search_dirs):
        if self.font:
            if font.has_key(self.font):
                self.font = font[self.font]
            else:
                log.error('skin error: can\'t find font %s' % self.font)
                self.font = font['default']
        else:
            self.font = font['default']



class FormatGotopos(XML_data):
    def __init__( self ):
        XML_data.__init__( self, ( 'x', 'y' ) )
        self.mode = 'relative'
        self.x = None
        self.y = None
        self.type = 'goto'

    def parse( self, node, scale, c_dir = '' ):
        XML_data.parse( self, node, scale, c_dir )
        self.mode = attr_str( node, 'mode', self.mode )
        if self.mode != 'relative' and self.mode != 'absolute':
            self.mode = 'relative'

    def prepare(self, font, color, search_dirs):
        pass


class FormatNewline(object):
    def __init__( self ):
        self.type = 'newline'
        pass

    def parse( self, node, scale, c_dir = '' ):
        pass

    def prepare(self, font, color, search_dirs):
        pass

class FormatImg( XML_data ):
    def __init__( self ):
        XML_data.__init__( self, ( 'x', 'y', 'width', 'height' ) )
        self.x = None
        self.y = None
        self.width = None
        self.height = None
        self.src = ''
        self.type = 'image'

    def parse( self, node, scale, c_dir = '' ):
        XML_data.parse( self, node, scale, c_dir )
        self.src = attr_str( node, 'src', self.src )

    def prepare(self, font, color, search_dirs ):
        self.src = search_file( self.src, search_dirs )



class FormatIf(object):
    def __init__( self ):
        self.expression = ''
        self.content = [ ]
        self.type = 'if'

    def parse( self, node, scale, c_dir = '' ):
        self.expression = attr_str( node, 'expression', self.expression )
        if self.expression:
            self.expression = get_expression(self.expression)

        for subnode in node.children:
            if subnode.name == u'if':
                child = FormatIf()
            elif subnode.name == u'text':
                child = FormatText()
            elif subnode.name == u'newline':
                child = FormatNewline()
            elif subnode.name == u'goto_pos':
                child = FormatGotopos()
            elif subnode.name == u'img':
                child = FormatImg()

            child.parse( subnode, scale, c_dir )
            self.content += [ child ]

    def prepare(self, font, color, search_dirs):
        for i in self.content:
            i.prepare( font, color, search_dirs )



# ======================================================================

class Image(XML_data):
    """
    an image
    """
    def __init__(self):
        self.type = 'image'
        XML_data.__init__(self, ('x', 'y', 'width', 'height', 'image',
                                 'filename', 'label', 'visible', 'alpha'))
        self.alpha = None

        
    def prepare(self, color, search_dirs, image_names):
        """
        try to guess the image localtion
        """
        XML_data.prepare(self)
        if self.image:
            if image_names.has_key(self.image):
                self.filename = image_names[self.image]
            else:
                log.error('skin error: can\'t find image definition %s' % \
                          self.image)

        if self.filename:
            self.filename = search_file(self.filename, search_dirs)


class Rectangle(XML_data):
    """
    a Rectangle
    """
    def __init__(self, color=None, bgcolor=None, size=None, radius = None):
        self.type = 'rectangle'
        XML_data.__init__(self, ('x', 'y', 'width', 'height', 'color',
                                 'bgcolor', 'size', 'radius' ))
        if not color == None:
            self.color = color
        if not bgcolor == None:
            self.bgcolor = bgcolor
        if not size == None:
            self.size = size
        if not radius == None:
            self.radius = radius


    def prepare(self, color, search_dirs=None, image_names=None):
        XML_data.prepare(self, None, color)


    def calculate(self, width, height):
        """
        Calculates the values for the rectangle to fit width and height
        inside it.
        """
        r = copy.copy(self)

        # get the x and y value, based on MAX
        if isinstance(r.x, str):
            r.x = int(eval(r.x, {'MAX':width}))
        if isinstance(r.y, str):
            r.y = int(eval(r.y, {'MAX':height}))

        # set rect width and height to something
        if not r.width:
            r.width = width

        if not r.height:
            r.height = height

        # calc width and height based on MAX settings
        if isinstance(r.width, str):
            r.width = int(eval(r.width, {'MAX':width}))

        if isinstance(r.height, str):
            r.height = int(eval(r.height, {'MAX':height}))

        # correct width and height to fit the rect
        width = max(width, r.width)
        height = max(height, r.height)
        if r.x < 0:
            width -= r.x
        if r.y < 0:
            height -= r.y

        # return needed width and height to fit original width and height
        # and the rectangle attributes
        return max(width, r.width), max(height, r.height), r


    def __str__(self):
        return 'theme.Rectangle at %s,%s %sx%s' % \
               (self.x, self.y, self.width, self.height)



class Font(XML_data):
    """
    Font tag. The prepared object is a font object that can
    be used in the text widgets for drawing texts.
    """
    def __init__(self, label):
        XML_data.__init__(self, ('name', 'size', 'color', 'bgcolor'))
        self.label = label
        self.shadow = XML_data(('visible', 'color', 'x', 'y', 'border'))
        self.shadow.visible = False
        self.shadow.border = False


    def parse(self, node, scale, current_dir):
        XML_data.parse(self, node, scale, current_dir)
        for subnode in node.children:
            if subnode.name == u'shadow':
                self.shadow.parse(subnode, scale, current_dir)


    def stringsize(self, text):
        size = self.font.stringsize(text)
        if self.shadow.visible:
            if self.shadow.border:
                return size + (self.size / 10) * 2
            else:
                return size + abs(self.shadow.x)
        return size


    def prepare(self, color, search_dirs=None, image_names=None, scale=1.0):
        if color.has_key(self.color):
            self.color = color[self.color]
        self.color = int2col(self.color)
        self.size = int(float(self.size) * scale)
        self.font = get_font_object(self.name, self.size)
        self.height = self.font.height
        if self.shadow.visible:
            if color.has_key(self.shadow.color):
                self.shadow.color = color[self.shadow.color]
            if self.shadow.border:
                self.height += (self.size / 10) * 2
            else:
                self.height += abs(self.shadow.y)
            self.shadow.color = int2col(self.shadow.color)



# ======================================================================


class AreaSet(object):
    """
    A tag with different area pointer in it, e.g. used for <player>
    """
    def __init__(self):
        self.areas = {}

    def parse(self, node, scale, current_dir):
        """
        parse an area node
        """
        for subnode in node.children:
            try:
                self.areas[subnode.name].parse(subnode, scale, current_dir)
            except KeyError:
                a = Area(subnode.name)
                a.visible = True
                a.parse(subnode, scale, current_dir)
                self.areas[subnode.name] = a

    def prepare(self, layout):
        """
        prepare all areas
        """
        map(lambda a: a[1].prepare(layout), self.areas.items())


# ======================================================================


class FXDSettings(object):
    """
    skin main settings class
    """
    def __init__(self, filename):
        self.__layout   = {}
        self.__font     = {}
        self.__color    = {}
        self.__images   = {}
        self.__menuset  = {}
        self.__menu     = {}
        self.__popup    = ''
        self.__sets     = {}
        self.__mainmenu = MainMenu()

        self.skindirs  = []
        self.icon_dir  = ""

        self.fxd_files = []

        # variables set by set_var
        self.all_variables    = ('box_under_icon', )
        self.box_under_icon   = 0

        # load plugin skin files:
        pdir = os.path.join(config.SHARE_DIR, 'skins/plugins')
        if os.path.isdir(pdir):
            for p in util.match_files(pdir, [ 'fxd' ]):
                self.load(p)

        self.load(filename)


    def parse(self, children, scale, c_dir):
        """
        parse the skin root node
        """
        for node in children:
            if node.name == u'main':
                self.__mainmenu.parse(node, scale, c_dir)

            elif node.name == u'menu':
                type = attr_str(node, 'type', 'default')

                if type == 'all':
                    # if type is all, all types except default are deleted and
                    # the settings will be loaded for default
                    self.__menu = {}
                    type       = 'default'

                self.__menu[type] = Menu()
                self.__menu[type].parse(node, scale, c_dir)


            elif node.name == u'menuset':
                label   = attr_str(node, 'label', '')
                inherit = attr_str(node, 'inherits', '')
                if inherit:
                    m = copy.deepcopy(self.__menuset[inherit])
                    self.__menuset[label] = m
                elif not self.__menuset.has_key(label):
                    self.__menuset[label] = MenuSet()
                self.__menuset[label].parse(node, scale, c_dir)


            elif node.name == u'layout':
                label = attr_str(node, 'label', '')
                if label:
                    if not self.__layout.has_key(label):
                        self.__layout[label] = Layout(label)
                    self.__layout[label].parse(node, scale, c_dir)


            elif node.name == u'font':
                label = attr_str(node, 'label', '')
                if label:
                    if not self.__font.has_key(label):
                        self.__font[label] = Font(label)
                    self.__font[label].parse(node, scale, c_dir)


            elif node.name == u'color':
                try:
                    value = attr_col(node, 'value', '')
                    self.__color[node.attrs[('', 'label')]] = int2col(value)
                except KeyError:
                    pass


            elif node.name == u'image':
                try:
                    value = attr_col(node, 'filename', '')
                    self.__images[node.attrs[('', 'label')]] = value
                except KeyError:
                    pass


            elif node.name == u'iconset':
                self.icon_dir = attr_str(node, 'theme', self.icon_dir)


            elif node.name == u'popup':
                self.__popup = attr_str(node, 'layout', self.__popup)


            elif node.name == u'setvar':
                for v in self.all_variables:
                    if node.attrs[('', 'name')].upper() == v.upper():
                        try:
                            setattr(self, v, int(node.attrs[('', 'val')]))
                        except ValueError:
                            setattr(self, v, node.attrs[('', 'val')])

            else:
                if node.children and node.children[0].name == 'style':
                    self.__sets[node.name] = Menu()
                elif not self.__sets.has_key(node.name):
                    self.__sets[node.name] = AreaSet()
                self.__sets[node.name].parse(node, scale, c_dir)


    def prepare(self):
        log.info('preparing skin settings')

        self.prepared = True

        # copy internal structures to prepare the copy
        self.sets = copy.deepcopy(self.__sets)
        all_menus = copy.deepcopy(self.__menu)
        self.font = copy.deepcopy(self.__font)
        layout    = copy.deepcopy(self.__layout)

        if not os.path.isdir(self.icon_dir):
            self.icon_dir = os.path.join(config.ICON_DIR, 'themes',
                                         self.icon_dir)
        search_dirs = self.skindirs + [ config.IMAGE_DIR, self.icon_dir, '.' ]

        for f in self.font:
            self.font[f].prepare(self.__color, scale=self.font_scale)

        for l in layout:
            layout[l].prepare(self.font, self.__color, search_dirs,
                              self.__images)

        for menu in all_menus:
            all_menus[menu].prepare(self.__menuset, layout)

            # prepare listing area images
            for s in all_menus[menu].style:
                for i in range(2):
                    if s[i] and hasattr(s[i], 'listing'):
                        for image in s[i].listing.images:
                            s[i].listing.images[image].prepare(None,
                                                               search_dirs,
                                                               self.__images)

        # menu structures
        self.default_menu = {}
        self.special_menu = {}

        for k in all_menus:
            if k.startswith('default'):
                self.default_menu[k] = all_menus[k]
            else:
                self.special_menu[k] = all_menus[k]

        types = []
        for k in self.special_menu:
            if k.find('main menu') == -1:
                types.append(k)

        for t in types:
            if not self.special_menu.has_key(t + ' main menu'):
                self.special_menu[t + ' main menu'] = self.special_menu[t]

        for t in ('default no image', 'default description'):
            if not self.default_menu.has_key(t):
                self.default_menu[t] = self.default_menu['default']

        t = 'default description'
        if not self.default_menu.has_key(t + ' no image'):
            self.default_menu[t + ' no image'] = self.default_menu[t]

        for s in self.sets:
            if isinstance(self.sets[s], AreaSet):
                # prepare an areaset
                self.sets[s].prepare(layout)
            else:
                # prepare a menu
                self.sets[s].prepare(self.__menuset, layout)
                for s in self.sets[s].style:
                    for i in range(2):
                        if s[i] and hasattr(s[i], 'listing'):
                            sli = s[i].listing.images
                            for image in sli:
                                sli[image].prepare(None, search_dirs,
                                                   self.__images)

        self.popup = layout[self.__popup]

        self.mainmenu = copy.deepcopy(self.__mainmenu)
        self.mainmenu.prepare(search_dirs, self.__images)

        self.images = {}
        for name in self.__images:
            self.images[name] = search_file(self.__images[name], search_dirs)


    def fxd_callback(self, fxd, node):
        """
        callback for the 'skin' tag
        """
        # get args back
        filename = fxd.getattr(None, 'args')

        self.font_scale = attr_float(node, "fontscale", 1.0)
        file_geometry   = attr_str(node, "geometry", '')

        if file_geometry:
            w, h = file_geometry.split('x')
        else:
            w, h = config.CONF.width, config.CONF.height

        scale = (float(config.CONF.width-2*config.GUI_OVERSCAN_X)/float(w),
                 float(config.CONF.height-2*config.GUI_OVERSCAN_Y)/float(h))

        include = attr_str(node, 'include', '')

        if include:
            self.load(include)

        self.parse(node.children, scale, os.path.dirname(filename))
        if not os.path.dirname(filename) in self.skindirs:
            self.skindirs = [ os.path.dirname(filename) ] + self.skindirs
        return


    def get_font(self, name):
        """
        Get the skin font object 'name'. Return the default object if
        a font with this name doesn't exists.
        """
        try:
            return self.font[name]
        except:
            return self.font['default']


    def get_image(self, name):
        """
        Get the skin image object 'name'. Return None if
        an image with this name doesn't exists.
        """
        try:
            return self.images[name]
        except:
            return None


    def get_icon(self, name):
        """
        Get the icon object 'name'. Return the icon in the theme dir if it
        exists, else try the normal image dir. If not found, return ''
        """
        icon = util.getimage(os.path.join(self.icon_dir, name))
        if icon:
            return icon
        return util.getimage(os.path.join(config.ICON_DIR, name), '')


    def load(self, file):
        """
        load and parse the skin file
        """
        self.prepared = False

        if not vfs.isfile(file):
            if vfs.isfile(file+".fxd"):
                file += ".fxd"

            elif vfs.isfile(os.path.join(config.SKIN_DIR, '%s/%s.fxd' % \
                                     (file, file))):
                file = os.path.join(config.SKIN_DIR, '%s/%s.fxd' % (file, file))

            else:
                file = os.path.join(config.SKIN_DIR, 'main/%s' % file)
                if vfs.isfile(file+".fxd"):
                    file += ".fxd"

        if not vfs.isfile(file):
            return 0

        parser = util.fxdparser.FXD(file)
        parser.setattr(None, 'args', (file))
        parser.set_handler('skin', self.fxd_callback)
        parser.parse()
        self.fxd_files.append(file)



def set_base_fxd(name):
    """
    Set the basic skin fxd file and store it
    """
    config.GUI_XML_FILE = os.path.splitext(os.path.basename(name))[0]
    log.info('load basic skin settings: %s' % config.GUI_XML_FILE)

    try:
        # try to load the new skin
        settings = FXDSettings(name)
    except:
        # something went wrong, print trace and load the
        # default skin (basic.fxd). This skin works
        # (if not, Freevo is broken)
        log.exception('XML file %s corrupt, using default skin' % name)
        settings = FXDSettings('basic.fxd')

    # search for personal skin settings additions
    # (this feature needs more doc outside this file)
    for dir in config.cfgfilepath:
        local_skin = '%s/local_skin.fxd' % dir
        if os.path.isfile(local_skin):
            log.debug('add local config %s to skin' % local_skin)
            settings.load(local_skin)
            break

    # prepare the skin for usage
    settings.prepare()
    return settings



def init_module():
    """
    On startup, Freevo will search for the theme the user used
    the last time, loads it and sets 'current_theme' for access
    from the public functions at the top of this file
    """
    global current_theme
    cachefile = os.path.join(config.FREEVO_CACHEDIR, 'skin-%s' % os.getuid())
    storage = {}
    if vfs.isfile(cachefile):
        storage = util.cache.load(cachefile)
        if not storage.has_key('GUI_XML_FILE'):
            # storage file too old
            storage = {}
    if storage:
        if not config.GUI_XML_FILE:
            config.GUI_XML_FILE = storage['GUI_XML_FILE']
        else:
            log.debug('skin forced to %s' % config.GUI_XML_FILE)
    else:
        if not config.GUI_XML_FILE:
            config.GUI_XML_FILE = config.GUI_DEFAULT_XML_FILE
        storage = {}
    # load the fxd file at set current_theme
    current_theme = set_base_fxd(config.GUI_XML_FILE)
    current_theme.filename = config.GUI_XML_FILE
