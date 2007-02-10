# -*- coding: iso-8859-1 -*-
# -----------------------------------------------------------------------------
# config.py - Handle the configuration files
# -----------------------------------------------------------------------------
# $Id$
#
# -----------------------------------------------------------------------------
# Freevo - A Home Theater PC framework
# Copyright (C) 2002 Krister Lagerstrom, 2003-2007 Dirk Meyer, et al.
#
# First Edition: Krister Lagerstrom <krister-freevo@kmlager.com>
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

# python imports
import sys
import os
import logging

import kaa.popcorn

import freevo.conf

# freevo imports
from freevo.ui import plugin

# get logging object
log = logging.getLogger('config')

# generate config
pycfgfile = freevo.conf.datafile('freevo_config.py')
cfgdir = os.path.join(freevo.conf.SHAREDIR, 'config')
cfgsource = [ os.path.join(cfgdir, f) for f in os.listdir(cfgdir) ]
freevo.conf.xmlconfig(pycfgfile, cfgsource)
execfile(pycfgfile)

# add external stuff
config.add_variable('player', kaa.popcorn.config)

# load config
cfgfile = os.path.expanduser('~/.freevo/freevo2.conf')
if not os.path.isfile(cfgfile):
    print '%s does not exist' % cfgfile
    print 'The file is now created and Freevo will stop so you can'
    print 'adjust the config settings.'
    print 'You should recheck freevo2.conf after every svn update. Use'
    print '\'freevo setup\' to rebuild the file without starting freevo.'
    print 'Your settings will be saved when the config file is rewritten.'
    config.load(cfgfile, create=True)
    sys.exit(0)

config.load(cfgfile, create=True)
if len(sys.argv) > 1 and sys.argv[1] in ('setup', '--setup', 'config', '--config'):
    print 'wrote %s' % cfgfile
    sys.exit(0)

if config.debug:
    logging.getLogger().setLevel(logging.INFO)
    
# plugins ist a list of known plugins
for p in plugins:
    c = config
    for attr in p.split('.'):
        c = getattr(c, attr)
    if c.activate:
        p = p.replace('plugin.', '').replace('..', '.')
        if isinstance(c.activate, bool):
            plugin.activate(p)
        else:
            plugin.activate(p, level=c.activate)

ICON_DIR  = os.path.join(freevo.conf.SHAREDIR, 'icons')
IMAGE_DIR = os.path.join(freevo.conf.SHAREDIR, 'images')
