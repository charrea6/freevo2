# -*- coding: iso-8859-1 -*-
# -----------------------------------------------------------------------------
# player.py - the Freevo video player
# -----------------------------------------------------------------------------
# $Id$
#
# -----------------------------------------------------------------------------
# Freevo - A Home Theater PC framework
# Copyright (C) 2007 Dirk Meyer, et al.
#
# First Edition: Dirk Meyer <dischi@freevo.org>
# Maintainer:    Dirk Meyer <dischi@freevo.org>
#
# Please see the file AUTHORS for a complete list of authors.
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

__all__ = [ 'play', 'stop' ]

# python imports
import logging

# kaa imports
import kaa.utils
import kaa.popcorn
import kaa.notifier

# Freevo imports
import config

from event import *
from application import Application, STATUS_RUNNING, STATUS_STOPPING, \
	 STATUS_STOPPED, STATUS_IDLE, CAPABILITY_TOGGLE, CAPABILITY_PAUSE, \
	 CAPABILITY_FULLSCREEN

# get logging object
log = logging.getLogger('video')

class Player(Application):
    """
    Video player object.
    """
    def __init__(self):
        capabilities = (CAPABILITY_FULLSCREEN, )
        Application.__init__(self, 'videoplayer', 'video', capabilities)
        self.player = kaa.popcorn.Player()
        self.player.set_window(self.engine.get_window())
        self.player.signals['failed'].connect_weak(self._play_failed)


    def play(self, item):
        """
        play an item
        """
        if not self.status in (STATUS_IDLE, STATUS_STOPPED):
            # Already running, stop the current player by sending a STOP
            # event. The event will also get to the playlist behind the
            # current item and the whole list will be stopped.
            Event(STOP, handler=self.eventhandler).post()
            # Now connect to our own 'stop' signal once to repeat this current
            # function call without the player playing
            self.signals['stop'].connect_once(self.play, item)
            return True

        if not kaa.notifier.running:
            # Freevo is in shutdown mode, do not start a new player, the old
            # only stopped because of the shutdown.
            return False

        # Try to get VIDEO and AUDIO resources. The ressouces will be freed
        # by the system when the application switches to STATUS_STOPPED or
        # STATUS_IDLE.
        blocked = self.get_resources('AUDIO', 'VIDEO')
        if 'VIDEO' in blocked:
            # Something has the video resource blocked. The only application
            # possible is the tv player right now. It would be possible to
            # ask the user what to do with a popup but we assume the user
            # does not care about the tv and just stop it.
            Event(STOP, handler=blocked['VIDEO'].eventhandler).post()
            # Now connect to the 'stop' signal once to repeat this current
            # function call without the player playing
            blocked['VIDEO'].signals['stop'].connect_once(self.play, item)
            return True
        if 'AUDIO' in blocked:
            # AUDIO is blocked, VIDEO is not. This is most likely the audio
            # player and we can pause it. Do this if possible.
            if not blocked['AUDIO'].has_capability(CAPABILITY_PAUSE):
                # Unable to pause, just stop it
                Event(STOP, handler=blocked['AUDIO'].eventhandler).post()
                # Now connect to the 'stop' signal once to repeat this current
                # function call without the player playing
                blocked['AUDIO'].signals['stop'].connect_once(self.play, item)
                return True
            # Now pause the current player. On its pause signal this player can
            # play again. And on the stop signal of this player (STATUS_IDLE)
            # the other player can be resumed again.
            in_progress = blocked['AUDIO'].pause()
            if isinstance(in_progress, kaa.notifier.InProgress):
                # takes some time, wait
                in_progress.connect(self.play, item).set_ignore_caller_args()
            if in_progress is not False:
                # we paused the application, resume on our stop
                self.signals['stop'].connect_once(blocked['AUDIO'].resume)
            return True

        # store item and playlist
        self.item = item
        self.playlist = self.item.get_playlist()
        if self.playlist:
            self.playlist.select(self.item)

        # set the current item to the gui engine
        self.engine.set_item(self.item)
        self.status = STATUS_RUNNING

        self.player.open(self.item.url)
        self.player.signals['end'].connect_once(PLAY_END.post, self.item)
        self.player.signals['start'].connect_once(PLAY_START.post, self.item)

        if item.info.get('interlaced'):
            self.player.set_property('deinterlace', True)

        # FIXME: set more properties
        self.player.play()


    def _play_failed(self):
        """
        Playing this item failed.
        """
        log.error('playback failed for %s', self.item)
        # disconnect the signal handler with that item
        self.player.signals['end'].disconnect(PLAY_END.post, self.item)
        self.player.signals['start'].disconnect(PLAY_START.post, self.item)
        # We should handle it here with a messge or something like that. To
        # make playlist work, we just send start and stop. It's ugly but it
        # should work.
        PLAY_START.post(self.item)
        PLAY_END.post(self.item)


    def stop(self):
        """
        Stop playing.
        """
        if self.get_status() != STATUS_RUNNING:
            return True
        self.player.stop()
        self.status = STATUS_STOPPING


    def eventhandler(self, event):
        """
        React on some events or send them to the real player or the
        item belongig to the player
        """
        if event == STOP:
            # Stop the player and pass the event to the item
            self.stop()
            self.item.eventhandler(event)
            return True

        if event == PLAY_START:
            self.item.eventhandler(event)
            return True

        if event == PLAY_END:
            # Now the player has stopped (either we called self.stop() or the
            # player stopped by itself. So we need to set the application to
            # to stopped.
            self.status = STATUS_STOPPED
            self.item.eventhandler(event)
            if self.status == STATUS_STOPPED:
                self.status = STATUS_IDLE
            return True

        if event in (PAUSE, PLAY):
            if self.player.get_state() == kaa.popcorn.STATE_PLAYING:
                self.player.pause()
                return True
            if self.player.get_state() == kaa.popcorn.STATE_PAUSED:
                self.player.resume()
                return True
            return False

        if event == SEEK:
            self.player.seek(int(event.arg), kaa.popcorn.SEEK_RELATIVE)
            return True

        if event == VIDEO_TOGGLE_INTERLACE:
            interlaced = not self.player.get_property('deinterlace')
            self.item.info['interlaced'] = interlaced
            self.player.set_property('deinterlace', interlaced)
            return True

        # give it to the item
        return self.item.eventhandler(event)


# create singleton object
player = kaa.utils.Singleton(Player)

# create functions to use from the outside
play = player.play
stop = player.stop
