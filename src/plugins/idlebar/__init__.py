# -*- coding: iso-8859-1 -*-
# -----------------------------------------------------------------------------
# idlebar.py - IdleBar plugin
# -----------------------------------------------------------------------------
# $Id$
#
# -----------------------------------------------------------------------------
# Freevo - A Home Theater PC framework
# Copyright (C) 2002-2005 Krister Lagerstrom, Dirk Meyer, et al.
#
# First Edition: Dirk Meyer <dischi@freevo.org>
# Maintainer:    Dirk Meyer <dischi@freevo.org>
#
# Please see the file doc/CREDITS for a complete list of authors.
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


# python imports
import time
import locale
import logging

import kaa

# freevo imports
from freevo.plugin import Plugin
from freevo.ui import application
from freevo.ui import config
from freevo.ui.event import *
from plugin import IdleBarPlugin
import freevo.ui.gui

# get logging object
log = logging.getLogger()

# # get gui config object
# guicfg = config.gui

class PluginInterface(Plugin):
    """
    """
    def plugin_activate(self, level):
        """
        init the idlebar
        """
        # register for signals
        application.signals['changed'].connect(self._app_change)
        self.visible = False
        self.container = None


    def _app_change(self, app):
        if not self.container:
            self.container = freevo.ui.gui.window.render('idlebar')
            for p in IdleBarPlugin.plugins():
                if p.widget:
                    p.widget.parent = self.container
        fullscreen = app.has_capability(application.CAPABILITY_FULLSCREEN)
        if fullscreen == self.visible:
            log.info('set visible %s' % (not fullscreen))
            if not self.visible:
                animation = self.container.animate(0.2)
                animation.behave('opacity', 0, 255)
            else:
                animation = self.container.animate(0.2)
                animation.behave('opacity', 255, 0)
            self.visible = not fullscreen
        return True
