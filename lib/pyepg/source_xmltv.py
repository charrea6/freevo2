# -*- coding: iso-8859-1 -*-
# -----------------------------------------------------------------------------
# source_xmltv.py - Freevo Electronic Program Guide module for XMLTV
# -----------------------------------------------------------------------------
# $Id$
#
# -----------------------------------------------------------------------------
# Freevo - A Home Theater PC framework
# Copyright (C) 2002-2004 Krister Lagerstrom, Dirk Meyer, et al.
#
# First Edition: Dirk Meyer <dmeyer@tzi.de>
# Maintainer:    Dirk Meyer <dmeyer@tzi.de>
#                Rob Shortt <rob@infointeractive.com>
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

import re
import time
import os
import calendar
import logging

import _strptime as strptime

import xmltv

# get logging object
log = logging.getLogger('pyepg')


EPG_TIME_EXC = _('Time conversion error')


def format_text(text):
    while len(text) and text[0] in (u' ', u'\t', u'\n'):
        text = text[1:]
    text = re.sub(u'\n[\t *]', u' ', text)
    while len(text) and text[-1] in (u' ', u'\t', u'\n'):
        text = text[:-1]
    return text


def timestr2secs_utc(timestr):
    """
    Convert a timestring to UTC (=GMT) seconds.

    The format is either one of these two:
    '20020702100000 CDT'
    '200209080000 +0100'
    """
    # This is either something like 'EDT', or '+1'
    try:
        tval, tz = timestr.split()
    except ValueError:
        tval = timestr
        tz   = str(-time.timezone/3600)

    if tz == 'CET':
        tz='+1'

    # Is it the '+1' format?
    if tz[0] == '+' or tz[0] == '-':
        tmTuple = ( int(tval[0:4]), int(tval[4:6]), int(tval[6:8]),
                    int(tval[8:10]), int(tval[10:12]), 0, -1, -1, -1 )
        secs = calendar.timegm( tmTuple )

        adj_neg = int(tz) >= 0
        try:
            min = int(tz[3:5])
        except ValueError:
            # sometimes the mins are missing :-(
            min = 0
        adj_secs = int(tz[1:3])*3600+ min*60

        if adj_neg:
            secs -= adj_secs
        else:
            secs += adj_secs
    else:
        # No, use the regular conversion

        ## WARNING! BUG HERE!
        # The line below is incorrect; the strptime.strptime function doesn't
        # handle time zones. There is no obvious function that does. Therefore
        # this bug is left in for someone else to solve.

        try:
            secs = time.mktime(strptime.strptime(timestr, xmltv.date_format))
        except ValueError:
            timestr = timestr.replace('EST', '')
            secs = time.mktime(strptime.strptime(timestr, xmltv.date_format))
    return secs


def update(guide, XMLTV_FILE):
    """
    Load guide data from a raw XMLTV file into the database, parsing using
    the XMLTV using the xmltv.py support lib.

    Returns:  -1 = failed to load any data
               0 = loaded channels and programs
               1 = loaded channel data only
    """
    # Is there a file to read from?
    if os.path.isfile(XMLTV_FILE):
        gotfile = 1
        guide.timestamp = os.path.getmtime(XMLTV_FILE)
    else:
        log.error('XMLTV file (%s) missing!' % XMLTV_FILE)
        gotfile = 0

    new_channels = []

    exclude_channels = guide.exclude_channels
    if not (isinstance(exclude_channels, list) or \
            isinstance(exclude_channels, tuple)):
        exclude_channels = []


    log.info('excluding channels: %s' % exclude_channels)

    xmltv_channels = None
    if gotfile:
        f = open(XMLTV_FILE)
        xmltv_channels = xmltv.read_channels(f)
        f.close()

    # Was the guide read successfully?
    if not xmltv_channels:
        return -1   # No

    for chan in xmltv_channels:
        id   = chan['id'].encode('latin-1', 'ignore')
        if id in exclude_channels:  continue

        new_channels.append(id)
        displayname = ''
        tunerid = ''

        if ' ' in id:
            # Assume the format is "TUNERID CHANNELNAME"
            tunerid     = id.split()[0]   # XXX Educated guess
            displayname = id.split()[1]   # XXX Educated guess
        else:
            displayname = chan['display-name'][0][0]
            if ' ' in displayname:
                tunerid     = displayname.split()[0]
                displayname = displayname.split()[1]
            else:
                tunerid = _('REPLACE WITH TUNERID FOR %s') % displayname

        guide.sql_add_channel(id, displayname, tunerid)

    xmltv_programs = None
    if gotfile:
        log.info('reading xmltv data')
        f = open(XMLTV_FILE)
        xmltv_programs = xmltv.read_programmes(f)
        f.close()

    # Was the guide read successfully?
    if not xmltv_programs:
        return 1    # Return the guide, it has the channels at least...


    known_ids = guide.sql_get_channel_ids()

    log.info('creating guide for %s' % new_channels)

    for p in xmltv_programs:
        if not p['channel'] in known_ids or p['channel'] in exclude_channels:
            continue
        try:
            channel_id = p['channel']
            title = Unicode(p['title'][0][0])
            episode = ''
            sub_title = ''
            desc = ''
            start = 0
            stop = 0
            date = None
            ratings = {}
            categories = []
            advisories = []

            if p.has_key('date'):
                date = Unicode(p['date'][0][0])
            if p.has_key('category'):
                categories = [ cat[0] for cat in p['category'] ]
            if p.has_key('rating'):
                for r in p['rating']:
                    if r.get('system') == 'advisory':
                        advisories.append(String(r.get('value')))
                        continue
                    ratings[String(r.get('system'))] = String(r.get('value'))
            if p.has_key('desc'):
                desc = Unicode(format_text(p['desc'][0][0]))
            if p.has_key('episode-num'):
                episode = p['episode-num'][0][0]
            if p.has_key('sub-title'):
                sub_title = p['sub-title'][0][0]
            try:
                start = timestr2secs_utc(p['start'])
                try:
                    stop = timestr2secs_utc(p['stop'])
                except:
                    # Fudging end time
                    stop = timestr2secs_utc(p['start'][0:8] + '235900' + \
                                            p['start'][14:18])
            except EPG_TIME_EXC:
                continue
            # fix bad German titles to make favorites working
            if title.endswith('. Teil'):
                title = title[:-6]
                if title.rfind(' ') > 0:
                    try:
                        part = int(title[title.rfind(' ')+1:])
                        title = title[:title.rfind(' ')].rstrip()
                        if sub_title:
                            sub_title = u'Teil %s: %s' % (part, sub_title)
                        else:
                            sub_title = u'Teil %s' % part
                    except Exception, e:
                        log.exception('error converting title')

            guide.sql_add_program(channel_id, title, start, stop,
                                  subtitle=sub_title, description=desc,
                                  episode=episode)

        except:
            log.exception('error in xmltv file')
    return 0