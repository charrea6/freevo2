#if 0 /*
# -----------------------------------------------------------------------
# headlines.py - a simple plugin to listen to headlines
# -----------------------------------------------------------------------
# $Id$
#
# Notes: 
# Todo: 
# activate:
# plugin.activate('headlines', level=45)
# HEADLINES_LOCATIONS = [ ("Advogato", "http://advogato.org/rss/articles.xml"),
#  ("Dictionary.com Word of the Day", "http://www.dictionary.com/wordoftheday/wotd.rss"),
#  ("DVD Review", "http://www.dvdreview.com/rss/newschannel.rss") ]
#
# for a full list of tested sites see Docs/plugins/headlines.txt
# -----------------------------------------------------------------------
# $Log$
# Revision 1.9  2003/10/16 16:05:31  dischi
# small i18n patch
#
# Revision 1.8  2003/10/04 18:37:29  dischi
# i18n changes and True/False usage
#
# Revision 1.7  2003/09/30 17:21:22  mikeruelle
# add some default news sites
#
# Revision 1.6  2003/09/21 16:47:15  dischi
# use utils html2txt function now
#
# Revision 1.5  2003/09/14 20:09:36  dischi
# removed some TRUE=1 and FALSE=0 add changed some debugs to _debug_
#
# Revision 1.4  2003/09/14 11:12:47  dischi
# Show details when selecting the item. The cache dir is now a subdir of
# CACHE_DIR.
#
# Revision 1.3  2003/09/09 18:55:00  dischi
# Add some doc
#
# Revision 1.2  2003/09/03 21:40:38  dischi
# o use util pickle function
# o show popup while getting the data
#
# Revision 1.1  2003/08/30 15:23:39  mikeruelle
# RDF headlines plugin. does pretty much anysite listed in evolution's summary section
#
#
# -----------------------------------------------------------------------
# Freevo - A Home Theater PC framework
# Copyright (C) 2003 Krister Lagerstrom, et al. 
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
# ----------------------------------------------------------------------- */
#endif

#python modules
import os, time, stat, re, copy

# rdf modules
from xml.dom.ext.reader import Sax2
import urllib

#freevo modules
import config, menu, rc, plugin, skin, osd, util
from gui.PopupBox import PopupBox
from item import Item


#get the singletons so we get skin info and access the osd
skin = skin.get_singleton()
osd  = osd.get_singleton()

#check every 30 minutes
MAX_HEADLINE_AGE = 1800

class PluginInterface(plugin.MainMenuPlugin):
    """
    A plugin to list headlines from an XML (RSS) feed.

    To activate, put the following lines in local_conf.py:

    plugin.activate('headlines', level=45) 
    HEADLINES_LOCATIONS = [
          ('Advogato', 'http://advogato.org/rss/articles.xml'), 
          ('DVD Review', 'http://www.dvdreview.com/rss/newschannel.rss') ] 

    For a full list of tested sites, see 'Docs/plugins/headlines.txt'. 
    """
    # make an init func that creates the cache dir if it don't exist
    def __init__(self):
        if not hasattr(config, 'HEADLINES_LOCATIONS'):
            self.reason = 'HEADLINES_LOCATIONS not defined'
            return
        plugin.MainMenuPlugin.__init__(self)
        
    def config(self):
        return [('HEADLINES_LOCATIONS', [ ("DVD Review", "http://www.dvdreview.com/rss/newschannel.rss"), ("Freshmeat", "http://freshmeat.net/backend/fm.rdf") ], 'where to get the news')]

    def items(self, parent):
        menu_items = skin.settings.mainmenu.items

        item = HeadlinesMainMenuItem()
        item.name = _('Headlines')
        if menu_items.has_key('headlines') and menu_items['headlines'].icon:
            item.icon = os.path.join(skin.settings.icon_dir, menu_items['headlines'].icon)
        if menu_items.has_key('headlines') and menu_items['headlines'].image:
            item.image = menu_items['headlines'].image

        item.parent = parent
        return [ item ]


class ShowHeadlineDetails(skin.BlankScreen):
    """
    Screen to show the details of the headline items
    """
    def __init__(self, (item, menuw)):
        skin.BlankScreen.__init__(self)
        skin.force_redraw = True
        menuw.visible = False
        self.item = item
        self.menuw = menuw

        rc.app(self)
        self.refresh()


    def render(self, string):
        """
        Basic renderer. Remove all tags, replace <p> and <br> with a newline.
        """
        string = string.replace('\n\n', '&#xxx;').replace('\n', ' ').\
                 replace('&#xxx;', '\n')
        string = string.replace('<p>', '\n').replace('<bt>', '\n')
        string = util.htmlenties2txt(string)
        return re.sub('<.*?>', '', string)
        

    def draw(self, x0, y0, x1, y1):
        """
        draw the description
        """
        font = skin.GetFont('default')
        titlefont = skin.GetFont('title')
        x0 += 10
        y0 += 10
        x1 -= 10
        y1 -= 10
        
        y0 = osd.drawstringframed(self.item.name, x0, y0, x1-x0, -1,
                                  titlefont.font, titlefont.color,
                                  mode='hard')[1][3] + 30

        y0 = osd.drawstringframed(self.render(self.item.description), x0, y0, x1-x0, y1-y0,
                                  font.font, font.color, mode='soft')[1][3] + 30
        if y0 < y1:
            osd.drawstringframed('Link: %s' % self.item.link, x0, y0, x1-x0, y1-y0,
                                 font.font, font.color, mode='soft')
            


    def eventhandler(self, event, menuw=None):
        """
        eventhandler
        """
        if event in ('MENU_SELECT', 'MENU_BACK_ONE_MENU'):
            rc.app(None)
            self.menuw.show()
            return True
        
        return False

        
class HeadlinesSiteItem(Item):
    """
    Item for the menu for one rss feed
    """
    def __init__(self, parent):
        Item.__init__(self, parent)
        self.url = ''
        self.cachedir = '%s/headlines' % config.FREEVO_CACHEDIR
        if not os.path.isdir(self.cachedir):
            os.mkdir(self.cachedir,
                     stat.S_IMODE(os.stat(config.FREEVO_CACHEDIR)[stat.ST_MODE]))
        self.location_index = None
        

    def actions(self):
        """
        return a list of actions for this item
        """
        items = [ ( self.getheadlines , _('Show Sites Headlines') ) ]
        return items

    
    def getsiteheadlines(self):
        headlines = []
        pfile = os.path.join(self.cachedir, 'headlines-%i' % self.location_index)
        if (os.path.isfile(pfile) == 0 or \
            (abs(time.time() - os.path.getmtime(pfile)) > MAX_HEADLINE_AGE)):
            #print 'Fresh Headlines'
            headlines = self.fetchheadlinesfromurl()
        else:
            #print 'Cache Headlines'
            headlines = util.read_pickle(pfile)
        return headlines


    def fetchheadlinesfromurl(self):
        headlines = []
        # create Reader object
        reader = Sax2.Reader()

        popup = PopupBox(text=_('Fetching headlines...'))
        popup.show()

        # parse the document
        try:
            myfile=urllib.urlopen(self.url)
            doc = reader.fromStream(myfile)
            items = doc.getElementsByTagName('item')
            for item in items:
                title = ''
                link  = ''
                description = ''
                
                if item.hasChildNodes():
                    for c in item.childNodes:
                        if c.localName == 'title':
                            title = c.firstChild.data
                        if c.localName == 'link':
                            link = c.firstChild.data
                        if c.localName == 'description':
                            description = c.firstChild.data
                if title:
                    headlines.append((title, link, description))

        except:
            #unreachable or url error
            print 'HEADLINES ERROR: could not open %s' % self.url
            pass

        #write the file
        if len(headlines) > 0:
            pfile = os.path.join(self.cachedir, 'headlines-%i' % self.location_index)
            util.save_pickle(headlines, pfile)

        popup.destroy()
        return headlines


    def show_details(self, arg=None, menuw=None):
        ShowHeadlineDetails(arg)

    def getheadlines(self, arg=None, menuw=None):
        headlines = [] 
        rawheadlines = []
        rawheadlines = self.getsiteheadlines()
        for title, link, description in rawheadlines:
            mi = menu.MenuItem('%s' % title, self.show_details, 0)
            mi.arg = (mi, menuw)
            mi.link = link
            mi.description = description
            headlines.append(mi)

        if (len(headlines) == 0):
            headlines += [menu.MenuItem(_('No Headlines found'), menuw.goto_prev_page, 0)]

        headlines_menu = menu.Menu(_('Headlines'), headlines)
        rc.app(None)
        menuw.pushmenu(headlines_menu)
        menuw.refresh()


class HeadlinesMainMenuItem(Item):
    """
    this is the item for the main menu and creates the list
    of Headlines Sites in a submenu.
    """
    def actions(self):
        """
        return a list of actions for this item
        """
        items = [ ( self.create_locations_menu , _('Headlines Sites' )) ]
        return items
 
    def create_locations_menu(self, arg=None, menuw=None):
        headlines_sites = []
        for location in config.HEADLINES_LOCATIONS:
            headlines_site_item = HeadlinesSiteItem(self)
            headlines_site_item.name = location[0]
            headlines_site_item.url = location[1]
            headlines_site_item.location_index = config.HEADLINES_LOCATIONS.index(location)
            headlines_sites += [ headlines_site_item ]
        if (len(headlines_sites) == 0):
            headlines_sites += [menu.MenuItem(_('No Headlines Sites found'),
                                              menuw.goto_prev_page, 0)]
        headlines_site_menu = menu.Menu(_('Headlines Sites'), headlines_sites)
        menuw.pushmenu(headlines_site_menu)
        menuw.refresh()


