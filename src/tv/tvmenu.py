#if 0 /*
# -----------------------------------------------------------------------
# tv.py - This is the Freevo TV module. 
# -----------------------------------------------------------------------
# $Id$
#
# Notes:
# Todo:        
#
# -----------------------------------------------------------------------
# $Log$
# Revision 1.12  2004/01/11 15:44:01  dischi
# changed menu display type to 'x main menu'
#
# Revision 1.11  2004/01/09 02:10:00  rshortt
# Patch from Matthieu Weber to revive add/edit favorites support from the
# TV interface.
#
# Revision 1.10  2003/12/31 16:10:30  rshortt
# Make it possible to have a tv mainmenu plugin.
#
# Revision 1.9  2003/11/28 19:26:37  dischi
# renamed some config variables
#
# Revision 1.8  2003/11/06 06:08:38  krister
# Added testcode for viewing the VCR/Composite1 input on the TV card
#
# Revision 1.7  2003/10/20 01:41:55  rshortt
# Moving tv_util from src/tv/ to src/util/.
#
# Revision 1.6  2003/09/13 10:08:23  dischi
# i18n support
#
# Revision 1.5  2003/09/05 20:07:08  dischi
# don't show tv guide item when there are no channels
#
# Revision 1.4  2003/09/05 02:06:36  rshortt
# renaming tv.py to tvmenu.py because it is already in the 'tv.' namespace
# and that breaks things. also added tv. namespace usage.
#
# This file is from tv.py on the new_record branch which I am merging to the head.
#
# Revision 1.13.2.4  2003/08/21 00:52:36  rshortt
# Minor update from the main branch.
#
# Revision 1.13.2.3  2003/08/11 19:37:26  rshortt
# Adding changes from the main branch.  Preparing to merge.
#
# Revision 1.17  2003/08/20 22:29:37  gsbarbieri
# UPPER CASE TEXT IS UGLY! :)
#
# Revision 1.16  2003/08/03 11:10:26  dischi
# Added TVGUIDE_HOURS_PER_PAGE
#
# Revision 1.15  2003/07/13 19:46:21  rshortt
# Move the work portion of get_friendly_channel() into tv_util.
#
# Revision 1.14  2003/06/29 15:01:31  outlyer
# Display the channel's friendly (display name) in the tuner popupbox.
#
# Since XMLTV 0.6.11 uses what they call "RFC" channel names which are
# very long and don't reveal much about the channel.
#
# This will obviously have no regressive effect, since users had the
# friendly name before.
#
# Revision 1.13.2.2  2003/07/13 19:38:02  rshortt
# Remove the 'View Favorites' screen until I fix some nasties with regard
# to the edit favorites screen.
#
# Revision 1.13.2.1  2003/06/03 02:11:48  rshortt
# Committing to a branch tag: new_record
# These changes enable the new program recording / informations popups which
# use record_server.
#
# Revision 1.13  2003/06/02 21:29:22  outlyer
# Changed the "Schedule Editor" to show up in the TV Submenu, along with "Guide" and
# "Recorded Shows" which makes a lot more sense then where it was before, which was
# also exceptionally well hidden.
#
# To do this properly, I also had to move record_schedule into a class, subclassing
# from Item, and so problems may and possibly will arise. I've tested it a little,
# but please bang on this, because while it's a relatively minor change, it does
# get things working inside the properly model, at least for a start.
#
# Bug reports are expected and welcome :)
#
# Revision 1.12  2003/04/24 19:56:42  dischi
# comment cleanup for 1.3.2-pre4
#
# Revision 1.11  2003/04/22 19:34:12  dischi
# mplayer and tvtime are now plugins
#
# Revision 1.10  2003/04/21 18:20:44  dischi
# make tv itself and not tv.tv the plugin (using __init__.py)
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


import time

# Configuration file. Determines where to look for AVI/MP3 files, etc
import config

# The menu widget class
import menu

# The RemoteControl class, sets up a UDP daemon that the remote control client
# sends commands to
import rc

import plugin

import util.tv_util as tv_util

# The Electronic Program Guide
import tv.epg_xmltv

from item import Item

from tv.tvguide import TVGuide
from directory import DirItem

from gui.AlertBox import AlertBox
from gui.PopupBox import PopupBox

import tv.program_display, tv.program_search, tv.view_favorites

# Set to 1 for debug output
DEBUG = config.DEBUG

TRUE = 1
FALSE = 0


def get_tunerid(channel_id):
    tuner_id = None
    for vals in config.TV_CHANNELS:
        tv_channel_id, tv_display_name, tv_tuner_id = vals[:3]
        if tv_channel_id == channel_id:
            return tv_tuner_id

    AlertBox(text=_('Could not find TV channel %s') % channel_id).show()
    return None


def get_friendly_channel(channel_id):
    channel_name = tv_util.get_chan_displayname(channel_id)

    if not channel_name: 
        AlertBox(text=_('Could not find TV channel %s') % channel_id).show()

    return channel_name


def start_tv(mode=None, channel_id=None):
    tuner_id = get_tunerid(channel_id)
    print 'mode=%s    channel=%s  tuner=%s' % (mode, channel_id, tuner_id)
    plugin.getbyname(plugin.TV).Play(mode, tuner_id)



#
# The TV menu
#
class TVMenu(Item):
    
    def __init__(self):
        Item.__init__(self)
        self.type = 'tv'


    def main_menu(self, arg, menuw):
        items = []
        if config.TV_CHANNELS:
            items.append(menu.MenuItem(_('TV Guide'), action=self.start_tvguide))
        if 0:
            items.append(menu.MenuItem(_('View VCR Input'), action=self.start_vcr))
        items.append(DirItem(config.TV_RECORD_DIR, None, name = _('Recorded Shows'),
                             display_type='tv'))
        items.append(menu.MenuItem(_('Scheduled Recordings'), 
                                   action=self.view_schedule))
        items.append(menu.MenuItem(_('Search Guide'), action=self.show_search))
        items.append(menu.MenuItem('View Favorites', action=self.show_favorites))

        plugins_list = plugin.get('mainmenu_tv')
        for p in plugins_list:
            items += p.items(self)

        menuw.pushmenu(menu.Menu(_('TV Main Menu'), items, item_types = 'tv main menu'))


    def show_search(self, arg, menuw):
        tv.program_search.ProgramSearch().show()
        return


    def show_favorites(self, arg, menuw):
        tv.view_favorites.ViewFavorites().show()
        return


    def view_schedule(self, arg, menuw):
        tv.program_display.ScheduledRecordings().show()
        return


    def get_start_time(self):
        ttime = time.localtime()
        stime = [ ]
        for i in ttime:
            stime += [i]
        stime[5] = 0 # zero seconds
        if stime[4] >= 30:
            stime[4] = 30
        else:
            stime[4] = 0

        return time.mktime(stime)


    def start_tvguide(self, arg, menuw):

        # Check that the TV channel list is not None
        if not config.TV_CHANNELS:
            msg = _('The list of TV channels is invalid!\n')
            msg += _('Please check the config file.')
            AlertBox(text=msg).show()
            return

        if arg == 'record':
            start_tv(None, ('record', None))
            return

        TVGuide(self.get_start_time(), start_tv, menuw)


    def start_vcr(self, arg, menuw):
        _debug_('tvmenu: mode=vcr')
        plugin.getbyname(plugin.TV).Play('vcr', None)
