#if 0 /*
# -----------------------------------------------------------------------
# directory.py - Directory handling
# -----------------------------------------------------------------------
# $Id$
#
# Notes:
# Todo:        
#
# -----------------------------------------------------------------------
# $Log$
# Revision 1.8  2003/04/24 19:55:45  dischi
# comment cleanup for 1.3.2-pre4
#
# Revision 1.7  2003/04/24 19:14:49  dischi
# pass xml_file to directory and videoitems
#
# Revision 1.6  2003/04/21 18:17:46  dischi
# Moved the code from interface.py for video/audio/image/games to __init__.py
#
# Revision 1.5  2003/04/21 13:01:15  dischi
# remove osd dependency
#
# Revision 1.4  2003/04/20 17:36:49  dischi
# Renamed TV_SHOW_IMAGE_DIR to TV_SHOW_DATA_DIR. This directory can contain
# images like before, but also fxd files for the tv show with global
# informations (plot/tagline/etc) and mplayer options.
#
# Revision 1.3  2003/04/20 16:08:50  dischi
# take directory image based on TV_SHOW_IMAGES
#
# Revision 1.2  2003/04/20 12:43:32  dischi
# make the rc events global in rc.py to avoid get_singleton. There is now
# a function app() to get/set the app. Also the events should be passed to
# the daemon plugins when there is no handler for them before. Please test
# it, especialy the mixer functions.
#
# Revision 1.1  2003/04/20 10:53:23  dischi
# moved identifymedia and mediamenu to plugins
#
# -----------------------------------------------------------------------
# Freevo - A Home Theater PC framework
# Copyright (C) 2002 Krister Lagerstrom, et al. 
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


import os
import traceback
import re

import util
import config
import menu as menu_module
import copy
import rc
import string
import skin

from item import Item
from playlist import Playlist, RandomPlaylist

import video
import audio
import image
import games

from item import Item

import gui.PasswordInputBox as PasswordInputBox
import gui.AlertBox as AlertBox

# XML support
from xml.utils import qp_xml
            
# Add support for bins album files
from image import bins

TRUE  = 1
FALSE = 0

skin = skin.get_singleton()

dirwatcher_thread = None


class DirItem(Playlist):
    """
    class for handling directories
    """
    def __init__(self, dir, parent, name = '', display_type = None):
        Item.__init__(self, parent)
        self.type = 'dir'
        self.media = None
        self.menuw = None
        
        # variables only for Playlist
        self.current_item = 0
        self.playlist = []
        self.autoplay = FALSE

        # variables only for DirItem
        self.dir          = dir
        self.display_type = display_type
        self.info         = {}

        # set directory variables to default
	all_variables = ('MOVIE_PLAYLISTS', 'DIRECTORY_SORT_BY_DATE',
                         'DIRECTORY_AUTOPLAY_SINGLE_ITEM', 'COVER_DIR',
                         'AUDIO_RANDOM_PLAYLIST', 'FORCE_SKIN_LAYOUT')
        for v in all_variables:
            setattr(self, v, eval('config.%s' % v))

        if name:
            self.name = name
	elif os.path.isfile(dir + '/album.xml'):
            try:
                self.name = bins.get_bins_desc(dir)['desc']['title']
            except:
                self.name = os.path.basename(dir)
        else:
            self.name = os.path.basename(dir)

        # Check for cover in COVER_DIR
        if os.path.isfile(config.COVER_DIR+os.path.basename(dir)+'.png'):
            self.image = config.COVER_DIR+os.path.basename(dir)+'.png'
            if self.display_type:
                self.handle_type = self.display_type
        if os.path.isfile(config.COVER_DIR+os.path.basename(dir)+'.jpg'):
            self.image = config.COVER_DIR+os.path.basename(dir)+'.jpg'
            if self.display_type:
                self.handle_type = self.display_type

        # Check for a cover in current dir, overide COVER_DIR if needed
        if os.path.isfile(dir+'/cover.png'): 
            self.image = dir+'/cover.png'
            if self.display_type:
                self.handle_type = self.display_type
        if os.path.isfile(dir+'/cover.jpg'): 
            self.image = dir+'/cover.jpg'
            if self.display_type:
                self.handle_type = self.display_type
            
        if not self.image and self.display_type == 'audio':
            images = ()
            covers = ()
            files =()
            def image_filter(x):
                return re.match('.*(jpg|png)$', x, re.IGNORECASE)
            def cover_filter(x):
                return re.search(config.AUDIO_COVER_REGEXP, x, re.IGNORECASE)

            # Pick an image if it is the only image in this dir, or it matches
            # the configurable regexp
            try:
                files = os.listdir(dir)
            except OSError:
                print "oops, os.listdir() error"
                traceback.print_exc()
            images = filter(image_filter, files)
            image = None
            if len(images) == 1:
                image = os.path.join(dir, images[0])
            elif len(images) > 1:
                covers = filter(cover_filter, images)
                if covers:
                    image = os.path.join(dir, covers[0])
            self.image = image

        if not self.image:
            f = os.path.join(config.TV_SHOW_DATA_DIR, os.path.basename(dir).lower())
            if os.path.isfile(f+'.png'):
                self.image = f+'.png'
            if os.path.isfile(f+'.jpg'):
                self.image = f+'.jpg'

            if config.TV_SHOW_INFORMATIONS.has_key(os.path.basename(dir).lower()):
                tvinfo = config.TV_SHOW_INFORMATIONS[os.path.basename(dir).lower()]
                self.info = tvinfo[1]
                if not self.image:
                    self.image = tvinfo[0]
                if not self.xml_file:
                    self.xml_file = tvinfo[3]

        if os.path.isfile(dir+'/folder.fxd'): 
            self.xml_file = dir+'/folder.fxd'

        # set variables to values in xml file
        if self.xml_file and os.path.isfile(self.xml_file):
            try:
                parser = qp_xml.Parser()
                var_def = parser.parse(open(self.xml_file).read())

                for top in var_def.children:
                    if top.name == 'folder':
                        for node in top.children:
                            if node.name == 'setvar':
                                for v in all_variables:
                                    if node.attrs[('', 'name')].upper() == v.upper():
                                        setattr(self, v, int(node.attrs[('', 'val')]))


            except:
                print "Skin XML file %s corrupt" % self.xml_file
                traceback.print_exc()
                return

        if self.DIRECTORY_SORT_BY_DATE == 2 and self.display_type != 'tv':
            self.DIRECTORY_SORT_BY_DATE = 0

            
    def copy(self, obj):
        """
        Special copy value DirItem
        """
        Playlist.copy(self, obj)
        if obj.type == 'dir':
            self.dir          = obj.dir
            self.display_type = obj.display_type
            self.info         = obj.info
            

    def actions(self):
        """
        return a list of actions for this item
        """
        items = [ ( self.cwd, 'Browse directory' ) ]

        # this doen't work right now because we have no playlist
        # at this point :-(
        
        # if self.playlist and len(self.playlist) > 1:
        #     items += [ (RandomPlaylist(self.playlist, self),
        #                 'Random play all items' ) ]

        if ((not self.display_type or self.display_type == 'audio') and
            config.AUDIO_RANDOM_PLAYLIST == 1):
            items += [ (RandomPlaylist((self.dir, config.SUFFIX_AUDIO_FILES),
                                       self),
                        'Recursive random play all items') ]
        return items
    

    def getattr(self, attr):
        """
        return the specific attribute as string or an empty string
        """
        a = Item.getattr(self, attr)
        if not a and self.info and self.info.has_key(attr):
            a = str(self.info[attr])
        return a


    def cwd(self, arg=None, menuw=None):
        """
        make a menu item for each file in the directory
        """
        
        if not self.menuw:
            self.menuw = menuw

        # are we on a ROM_DRIVE and have to mount it first?
        for media in config.REMOVABLE_MEDIA:
            if string.find(self.dir, media.mountdir) == 0:
                util.mount(self.dir)
                self.media = media

	if os.path.isfile(self.dir + '/.password'):
	    print 'password protected dir'
	    pb = PasswordInputBox(text='Enter Password', handler=self.pass_cmp_cb)
	    pb.show()
	    # save these so the InputBox callback can pass them to do_cwd
	    self.arg = arg
	    self.foo = "bar"
	else:
	    self.do_cwd(arg, menuw)


    def pass_cmp_cb(self, word=None):

	# read the contents of self.dir/.passwd and compare to word
	try:
	    pwfile = open(self.dir + '/.password')
	    line = pwfile.readline()
	except IOError, e:
	    print 'error %d (%s) reading password file for %s' % \
		  (e.errno, e.strerror, self.dir)
	    return

	pwfile.close()
	password = line.strip()
	if word == password:
	    self.do_cwd(self.arg, self.menuw)
	else:
	    pb = AlertBox(text='Password incorrect')
	    pb.show()
            return


    def do_cwd(self, arg=None, menuw=None):
        try:
            files = ([ os.path.join(self.dir, fname)
                       for fname in os.listdir(self.dir) ])
            self.all_files = copy.copy(files)
        except OSError:
            print 'util:match_files(): Got error on dir = "%s"' % self.dir
            return
            

        # build play_items for video, audio, image, games
        # the interface functions must remove the files they cover, they
        # can also remove directories

        play_items = []
        for t in ( 'video', 'audio', 'image', 'games' ):
            if not self.display_type or self.display_type == t:
                play_items += eval(t + '.cwd(self, files)')

        if self.display_type == 'tv':
            play_items += video.cwd(self, files)
            
        if self.DIRECTORY_SORT_BY_DATE:
            play_items.sort(lambda l, o: cmp(l.sort('date').upper(),
                                             o.sort('date').upper()))
        else:
            play_items.sort(lambda l, o: cmp(l.sort().upper(),
                                             o.sort().upper()))

        files.sort(lambda l, o: cmp(l.upper(), o.upper()))

        # add all playable items to the playlist of the directory
        # to play one files after the other
        if (not self.display_type or self.display_type == 'audio' or \
            self.display_type == 'image' or \
            (self.MOVIE_PLAYLISTS and self.display_type == 'video')):
            self.playlist = play_items

        # build items for sub-directories
        dir_items = []
        for filename in files:
            if (os.path.isdir(filename) and
                os.path.basename(filename) != 'CVS' and
                os.path.basename(filename) != '.xvpics' and
                os.path.basename(filename) != '.thumbnails' and
                os.path.basename(filename) != '.pics'):
                dir_items += [ DirItem(filename, self, display_type =
                                       self.display_type) ]

        dir_items.sort(lambda l, o: cmp(l.dir.upper(), o.dir.upper()))


        # build items for playlists
        pl_items = []
        if not self.display_type or self.display_type == 'audio':
            for pl in util.find_matches(files, config.SUFFIX_AUDIO_PLAYLISTS):
                pl_items += [ Playlist(pl, self) ]

        if not self.display_type or self.display_type == 'image':
            for file in util.find_matches(files, config.SUFFIX_IMAGE_SSHOW):
                pl = Playlist(file, self)
                pl.autoplay = TRUE
                pl_items += [ pl ]

        pl_items.sort(lambda l, o: cmp(l.name.upper(), o.name.upper()))


        # all items together
        items = []

        # random playlist (only active for audio)
        if ((not self.display_type or self.display_type == 'audio') and \
            len(play_items) > 1 and self.display_type and
            config.AUDIO_RANDOM_PLAYLIST == 1):
            pl = Playlist(play_items, self)
            pl.randomize()
            pl.autoplay = TRUE
            items += [ pl ]

        items += dir_items + pl_items + play_items

        self.dir_items  = dir_items
        self.pl_items   = pl_items
        self.play_items = play_items


        title = self.name

        # autoplay
        if len(items) == 1 and items[0].actions() and \
           self.DIRECTORY_AUTOPLAY_SINGLE_ITEM:
            items[0].actions()[0][0](menuw=menuw)
        else:
            item_menu = menu_module.Menu(title, items, reload_func=self.reload,
                                         item_types = self.display_type,
                                         force_skin_layout = self.FORCE_SKIN_LAYOUT)

            if self.xml_file:
                item_menu.skin_settings = skin.LoadSettings(self.xml_file)

            if menuw:
                menuw.pushmenu(item_menu)

            global dirwatcher_thread
            if not dirwatcher_thread:
                dirwatcher_thread = DirwatcherThread(menuw)
                dirwatcher_thread.setDaemon(1)
                dirwatcher_thread.start()

            dirwatcher_thread.cwd(self, item_menu, self.dir, self.all_files)
            self.menu = item_menu

        return items

    def reload(self):
        """
        called when we return to this menu
        """
        global dirwatcher_thread
        dirwatcher_thread.cwd(self, self.menu, self.dir, self.all_files)
        dirwatcher_thread.scan()

        # we changed the menu, don't build a new one
        return None

        
    def update(self, new_files, del_files, all_files):
        """
        update the current item set. Maybe this function can share some code
        with cwd in the future, but it's easier now the way it is
        """
        new_items = []
        del_items = []

        self.all_files = all_files

        # check modules if they know something about the deleted/new files
        for t in ( 'video', 'audio', 'image', 'games' ):
            if not self.display_type or self.display_type == t:
                eval(t + '.update')(self, new_files, del_files, \
                                              new_items, del_items, \
                                              self.play_items)
                
        if self.display_type == 'tv':
            video.update(self, new_files, del_files, 
                                   new_items, del_items, self.play_items)

        # delete play items from the menu
        for i in del_items:
            self.menu.delete_item(i)
            self.play_items.remove(i)

        # delete dir items from the menu
        for dir in del_files:
            for item in self.dir_items:
                if item.dir == dir:
                    self.menu.delete_item(item)
                    self.dir_items.remove(item)

        # delete playlist items from the menu
        for pl in del_files:
            for item in self.pl_items:
                if item.filename == pl:
                    self.menu.delete_item(item)
                    self.pl_items.remove(item)


                    
        # add new play items to the menu
        if new_items:
            self.play_items += new_items
            if self.DIRECTORY_SORT_BY_DATE:
                self.play_items.sort(lambda l, o: cmp(l.sort('date').upper(),
                                                      o.sort('date').upper()))
            else:
                self.play_items.sort(lambda l, o: cmp(l.sort().upper(),
                                                      o.sort().upper()))
                

        # add new dir items to the menu
        new_dir_items = []
        for dir in new_files:
            if (os.path.isdir(dir) and
                os.path.basename(dir) != 'CVS' and
                os.path.basename(dir) != '.xvpics' and
                os.path.basename(dir) != '.thumbnails' and
                os.path.basename(dir) != '.pics'):
                new_dir_items += [ DirItem(dir, self,
                                           display_type = self.display_type) ]

        if new_dir_items:
            self.dir_items += new_dir_items
            self.dir_items.sort(lambda l, o: cmp(l.dir.upper(), o.dir.upper()))


        # add new playlist items to the menu
        new_pl_items = []
        if not self.display_type or self.display_type == 'audio':
            for pl in util.find_matches(new_files,
                                        config.SUFFIX_AUDIO_PLAYLISTS):
                new_pl_items += [ Playlist(pl, self) ]

        if not self.display_type or self.display_type == 'image':
            for file in util.find_matches(new_files, config.SUFFIX_IMAGE_SSHOW):
                pl = Playlist(file, self)
                pl.autoplay = TRUE
                new_pl_items += [ pl ]

        if new_pl_items:
            self.pl_items += new_pl_items
            self.pl_items.sort(lambda l, o: cmp(l.name.upper(), o.name.upper()))


        
        items = []

        # random playlist (only active for audio)
        if ((not self.display_type or self.display_type == 'audio') and \
            len(self.play_items) > 1 and self.display_type and
            config.AUDIO_RANDOM_PLAYLIST == 1):

            # some files changed, rebuild playlist
            if new_items or del_items:
                pl = Playlist(self.play_items, self)
                pl.randomize()
                pl.autoplay = TRUE
                items += [ pl ]

            # reuse old playlist
            else:
                items += [ self.menu.choices[0] ]

        # build a list of all items
        items += self.dir_items + self.pl_items + self.play_items

        # finally add the items
        for i in new_items + new_dir_items + new_pl_items:
            self.menu.add_item(i, items.index(i))
                    
        # reload the menu, use an event to avoid problems because this function
        # was called by a thread
        rc.post_event(rc.REBUILD_SCREEN)



# ======================================================================

import threading
import thread
import time

class DirwatcherThread(threading.Thread):
                
    def __init__(self, menuw):
        threading.Thread.__init__(self)
        self.item = None
        self.menuw = menuw
        self.item_menu = None
        self.dir = None
        self.files = None
        self.lock = thread.allocate_lock()
        
    def cwd(self, item, item_menu, dir, files):
        self.lock.acquire()

        self.item = item
        self.item_menu = item_menu
        self.dir = dir
        self.files = files

        self.lock.release()

    def scan(self):
        self.lock.acquire()

        try:
            files = ([ os.path.join(self.dir, fname)
                       for fname in os.listdir(self.dir) ])
        except OSError:
            # the directory is gone
            print 'unable to read directory'

            # send EXIT to go one menu up:
            rc.post_event(rc.EXIT)
            self.lock.release()
            return
        
        
        new_files = []
        del_files = []
        
        for f in files:
            if not f in self.files:
                new_files += [ f ]
        for f in self.files:
            if not f in files:
                del_files += [ f ]

        if new_files or del_files:
            print 'directory has changed'
            self.item.update(new_files, del_files, files)
                    
        self.files = files
        self.lock.release()

    
    def run(self):
        while 1:
            if self.dir and self.menuw and \
               self.menuw.menustack[-1] == self.item_menu and not rc.app():
                self.scan()
            time.sleep(2)

    
