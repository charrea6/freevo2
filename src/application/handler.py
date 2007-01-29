# -*- coding: iso-8859-1 -*-
# -----------------------------------------------------------------------------
# handler.py - Handle active applications and windows
# -----------------------------------------------------------------------------
# $Id$
#
# This file defines the application handler. The handler will manage the
# current active applications and windows, show/hide them and send events to
# the application or window with the focus.
#
# The handler should not be accessed from outside the application module.
#
# -----------------------------------------------------------------------------
# Freevo - A Home Theater PC framework
# Copyright (C) 2005-2007 Dirk Meyer, et al.
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

__all__ = [ 'handler' ]

# python imports
import sys
import time
import logging

# kaa imports
import kaa.notifier

# freevo imports
import config
from freevo.ui.input import set_mapping
from freevo.ui.event import *

# the logging object
log = logging.getLogger()

# debug stuff
_TIME_DEBUG = False

# the global object
handler = None

# -----------------------------------------------------------------------------

STATUS_IDLE     = 'idle'
STATUS_RUNNING  = 'running'
STATUS_STOPPING = 'stopping'
STATUS_STOPPED  = 'stopped'

CAPABILITY_TOGGLE = 1

class Handler(object):
    """
    This is the main application for Freevo, handling applications
    with an event handler and the event mapping.
    """
    def __init__(self):
        self.applications = []
        self.current = None
        self.windows = []
        # callback for events
        kaa.notifier.EventHandler(self.handle).register()

        # Signals
        self.signals = { 'changed': kaa.notifier.Signal() }


    def set_focus(self):
        """
        Set new focus (input mapping, application show/hide)
        """
        app = self.applications[-1]

        # set input mapping
        focus = app
        if self.windows:
            focus = self.windows[-1]
        log.info('set focus to %s' % focus)
        set_mapping(focus.eventmap)

        if app == self.current:
            # same app as before
            return

        log.info('switch application from %s to %s' % (self.current, app))
        self.signals['changed'].emit(app)
        app._show_app()
        if self.current:
            self.current._hide_app()
        self.current = app


    def show_application(self, app):
        """
        Show application and set the focus
        """
        log.info('show application %s' % app)
        # do will have a stack or is this the first application?
        if len(self.applications) == 0:
            # just add the application
            self.applications.append(app)
            self.set_focus()
            return True
        # check about the old app if it is marked as removed
        # or if it is the same application as before
        previous = self.applications[-1]
        if previous == app:
            # It is the same app, nothing to do
            return True
        if app in self.applications:
            # already in list, remove it before appending
            self.applications.remove(app)
        # check if an application is in status stopped and replace it.
        for pos, a in enumerate(self.applications):
            if a.status == STATUS_STOPPED:
                self.applications[pos] = app
                break
        else:
            # no stopped application, just append to the list
            self.applications.append(app)
        self.set_focus()


    def hide_application(self, app):
        """
        Remove application from stack.
        """
        log.info('hide application %s' % app)
        if not app in self.applications:
            # already gone (maybe by show_application of a new one)
            return
        if not app == self.applications[-1]:
            # not visible, just remove
            self.applications.remove(app)
            return
        # remove from list and set new focus
        self.applications.pop()
        self.set_focus()


    def add_window(self, window):
        """
        Add a window above all applications
        """
        self.windows.append(window)
        self.set_focus()


    def remove_window(self, window):
        """
        Remove window from window list and reset the focus
        """
        if not window in self.windows:
            return
        self.windows.remove(window)
        self.set_focus()


    def get_active(self):
        """
        Return the application
        """
        if not self.applications:
            return None
        return self.applications[-1]


    def handle(self, event):
        """
        Event handling function.
        """
        log.debug('handling event %s' % str(event))
        if _TIME_DEBUG:
            t1 = time.clock()

        try:
            if event == TOGGLE_APPLICATION and len(self.applications) > 1 and \
                   self.applications[-1].has_capability(CAPABILITY_TOGGLE):
                log.info('Toggle application')
                self.applications.insert(0, self.applications.pop())
                self.set_focus()

            elif event == FUNCTION_CALL:
                # event is a direct function call, call it and do not
                # pass it on the the normal handling
                event.arg()

            elif event.handler:
                # event has it's own handler function, call this
                # function and do not pass it on the the normal
                # handling.
                event.handler(event=event)

            elif len(self.windows) and self.windows[-1].eventhandler(event=event):
                # handled by the current popup
                pass

            else:
                # handle by the current appliaction
                self.applications[-1].eventhandler(event=event)

            if _TIME_DEBUG:
                print time.clock() - t1
            return True

        except (SystemExit, KeyboardInterrupt):
            sys.exit(0)

        except Exception, e:
            log.exception('application.handler')
            if config.FREEVO_EVENTHANDLER_SANDBOX:
                msg=_('Event \'%s\' crashed\n\nPlease take a ' \
                      'look at the logfile and report the bug to ' \
                      'the Freevo mailing list. The state of '\
                      'Freevo may be corrupt now and this error '\
                      'could cause more errors until you restart '\
                      'Freevo.') % event
                handler = kaa.notifier.Callback(sys.exit, 0)
                from window import ConfirmWindow
                pop = ConfirmWindow(msg, (_('Shutdown'), _('Continue')))
                pop.buttons[0].connect(sys.exit, 0)
                pop.show()
            else:
                sys.exit(1)

# create the global object
handler = Handler()
