# -*- coding: iso-8859-1 -*-
# -----------------------------------------------------------------------
# v4l2.py - V4L2 python interface.
# -----------------------------------------------------------------------
# $Id$
#
# Notes: http://bytesex.org/v4l/spec/
# Todo:        
#
# -----------------------------------------------------------------------
# $Log$
# Revision 1.22  2004/11/14 19:41:57  dischi
# fix future warning the better way, always use util.ioctl please
#
# Revision 1.21  2004/11/13 16:07:54  dischi
# fix ioctl future warning for now
#
# Revision 1.20  2004/10/28 19:45:38  dischi
# remove future warning
#
# Revision 1.19  2004/08/23 01:24:50  rshortt
# -Revive v4l2 channel changing.
# -Set the card's input based on the current settings.
#
# Revision 1.18  2004/08/13 16:17:33  rshortt
# More work on tv settings, configuration of v4l2 devices based on TV_SETTINGS.
#
# Revision 1.17  2004/08/12 16:52:49  rshortt
# Work on autodetecting tv cards.
#
# Revision 1.16  2004/08/11 20:47:17  rshortt
# Start adding some try/except.
#
# Revision 1.15  2004/07/10 12:33:42  dischi
# header cleanup
#
# Revision 1.14  2004/01/13 15:08:22  outlyer
# Removed an extraneous 'print'
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


import string
import freq
import os
import struct
import sys
from util.ioctl import ioctl, _IOC
import config

DEBUG = config.DEBUG


_IOC_NRBITS = 8
_IOC_TYPEBITS = 8
_IOC_SIZEBITS = 14
_IOC_DIRBITS = 2

_IOC_NRMASK = ((1 << _IOC_NRBITS)-1)
_IOC_TYPEMASK = ((1 << _IOC_TYPEBITS)-1)
_IOC_SIZEMASK = ((1 << _IOC_SIZEBITS)-1)
_IOC_DIRMASK = ((1 << _IOC_DIRBITS)-1)

_IOC_NRSHIFT = 0 
_IOC_TYPESHIFT = (_IOC_NRSHIFT+_IOC_NRBITS)
_IOC_SIZESHIFT = (_IOC_TYPESHIFT+_IOC_TYPEBITS)
_IOC_DIRSHIFT = (_IOC_SIZESHIFT+_IOC_SIZEBITS)

# Direction bits.
_IOC_NONE = 0
_IOC_WRITE = 1
_IOC_READ = 2

def _IO(type,nr): return _IOC(_IOC_NONE,(type),(nr),0)
def _IOR(type,nr,size): return _IOC(_IOC_READ,(type),(nr),struct.calcsize(size))
def _IOW(type,nr,size): return _IOC(_IOC_WRITE,(type),(nr),struct.calcsize(size))
def _IOWR(type,nr,size): return _IOC(_IOC_READ|_IOC_WRITE,(type),(nr),struct.calcsize(size))

# used to decode ioctl numbers..
def _IOC_DIR(nr): return (((nr) >> _IOC_DIRSHIFT) & _IOC_DIRMASK)
def _IOC_TYPE(nr): return (((nr) >> _IOC_TYPESHIFT) & _IOC_TYPEMASK)
def _IOC_NR(nr): return (((nr) >> _IOC_NRSHIFT) & _IOC_NRMASK)
def _IOC_SIZE(nr): return (((nr) >> _IOC_SIZESHIFT) & _IOC_SIZEMASK)

FREQUENCY_ST = "III32x"
GETFREQ_NO   = _IOWR('V', 56, FREQUENCY_ST)
SETFREQ_NO   = _IOW('V', 57, FREQUENCY_ST)

SETFREQ_NO_V4L = _IOW('v', 15, "L")

QUERYCAP_ST  = "16s32s32sLL16x"
QUERYCAP_NO  = _IOR('V',  0, QUERYCAP_ST)

ENUMSTD_ST   = "LQ24s2LL16x"
ENUMSTD_NO   = _IOWR('V', 25, ENUMSTD_ST)

STANDARD_ST  = "Q"
GETSTD_NO    = _IOR('V', 23, STANDARD_ST)
SETSTD_NO    = _IOW('V', 24, STANDARD_ST)

ENUMINPUT_ST = "L32sLLLQL16x"
ENUMINPUT_NO = _IOWR('V', 26, ENUMINPUT_ST)

INPUT_ST  = "L";
GETINPUT_NO  = _IOR('V', 38, INPUT_ST)
SETINPUT_NO  = _IOWR('V', 39, INPUT_ST)

FMT_ST = "L7L4x168x"
GET_FMT_NO = _IOWR ('V',  4, FMT_ST)
SET_FMT_NO = _IOWR ('V',  5, FMT_ST)

TUNER_ST = "L32sLLLLLLll16x"
GET_TUNER_NO = _IOWR ('V', 29, TUNER_ST)
SET_TUNER_NO = _IOW  ('V', 30, TUNER_ST)

AUDIO_ST = "L32sLL8x"
GET_AUDIO_NO = _IOWR ('V', 33, AUDIO_ST)
SET_AUDIO_NO = _IOW  ('V', 34, AUDIO_ST)


V4L2_TUNER_CAP_LOW    = 0x0001
V4L2_TUNER_CAP_NORM   = 0x0002
V4L2_TUNER_CAP_STEREO = 0x0010
V4L2_TUNER_CAP_LANG2  = 0x0020
V4L2_TUNER_CAP_SAP    = 0x0020
V4L2_TUNER_CAP_LANG1  = 0x0040


NORMS = { 'NTSC'  : 0x3000,
          'PAL'   : 0xff,
          'SECAM' : 0x7f0000  }


class Videodev:
    def __init__(self, which=None, device=None):
        self.devfd = None
        self.settings = None

        if not which:
            if not device:
                device = '/dev/video'

            self.basic_info(device)

        else:
            self.settings = config.TV_SETTINGS.get(which)
            self.init_settings()


    def basic_info(self, device):
        self.devfd = os.open(device, os.O_TRUNC)
        if self.devfd < 0:
            sys.exit("Error: %d\n" %self.devfd)
        else:
            if DEBUG: print "Video Opened at %s" % device

        results           = self.querycap()
        self.driver       = results[0]
        self.card         = results[1]
        self.bus_info     = results[2]
        self.version      = results[3]
        self.capabilities = results[4]
    

    def close(self):
        os.close(self.devfd)


    def setchanlist(self, chanlist):
        self.chanlist = freq.CHANLIST[chanlist]


    def getfreq(self):
        val = struct.pack( FREQUENCY_ST, 0,0,0 )
        try:
            r = ioctl(self.devfd, GETFREQ_NO, val)
            (junk,junk, freq, ) = struct.unpack(FREQUENCY_ST, r)
            return freq
        except IOError:
            print "Failed to get frequency, not supported by device?" 
            return -1


    def setchannel(self, channel):
        channel = str(channel)

        freq = config.FREQUENCY_TABLE.get(channel)
        if freq:
            if DEBUG: 
                print 'USING CUSTOM FREQUENCY: chan="%s", freq="%s"' % \
                      (channel, freq)
        else:
            freq = self.chanlist.get(channel)
            if DEBUG: 
                print 'USING STANDARD FREQUENCY: chan="%s", freq="%s"' % \
                      (channel, freq)

        if not freq:
            print 'ERROR: unable to get frequency for %s' % channel
            return

        freq *= 16

        # The folowing check for TUNER_LOW capabilities was not working for
        # me... needs further investigation. 
        # if not (self.capabilities & V4L2_TUNER_CAP_LOW):
        #     # Tune in MHz.
        #     freq /= 1000
        freq /= 1000

        try:
            self.setfreq(freq)
        except:
            self.setfreq_old(freq)
      

    def setfreq_old(self, freq):
        val = struct.pack( "L", freq)
        r = ioctl(self.devfd, long(SETFREQ_NO_V4L), val)        


    def setfreq(self, freq):
        val = struct.pack( FREQUENCY_ST, long(0), long(0), freq)
        r = ioctl(self.devfd, long(SETFREQ_NO), val)


    def getinput(self):
        r = ioctl(self.devfd, GETINPUT_NO, struct.pack(INPUT_ST,0))
        return struct.unpack(INPUT_ST,r)[0]
  

    def setinput(self,value):
        r = ioctl(self.devfd, SETINPUT_NO, struct.pack(INPUT_ST,value))


    def querycap(self):
        val = struct.pack( QUERYCAP_ST, "", "", "", 0, 0 )
        r = ioctl(self.devfd, QUERYCAP_NO, val)
        return struct.unpack( QUERYCAP_ST, r )


    def enumstd(self, no):
        val = struct.pack( ENUMSTD_ST, no, 0, "", 0, 0, 0)
        r = ioctl(self.devfd,ENUMSTD_NO,val)
        return struct.unpack( ENUMSTD_ST, r )


    def getstd(self):
        val = struct.pack( STANDARD_ST, 0 )
        r = ioctl(self.devfd,GETSTD_NO, val)
        return struct.unpack( STANDARD_ST, r )[0]


    def setstd(self, value):
        val = struct.pack( STANDARD_ST, value )
        r = ioctl(self.devfd,SETSTD_NO, val)


    def enuminput(self,index):
        val = struct.pack( ENUMINPUT_ST, index, "", 0,0,0,0,0)
        r = ioctl(self.devfd,ENUMINPUT_NO,val)
        return struct.unpack( ENUMINPUT_ST, r )


    def getfmt(self):  
        val = struct.pack( FMT_ST, 0,0,0,0,0,0,0,0)
        try:
            r = ioctl(self.devfd,GET_FMT_NO,val)
            return struct.unpack( FMT_ST, r )
        except IOError:
            print "Failed to get format, not supported by device?" 
            return (-1, -1, -1, -1, -1, -1, -1, -1)


    def setfmt(self, width, height):
        val = struct.pack( FMT_ST, 1L, width, height, 0L, 4L, 0L, 131072L, 0L)
        r = ioctl(self.devfd,SET_FMT_NO,val)


    def gettuner(self,index):
        val = struct.pack( TUNER_ST, index, "", 0,0,0,0,0,0,0,0)
        r = ioctl(self.devfd,GET_TUNER_NO,val)
        return struct.unpack( TUNER_ST, r )


    def settuner(self,index,audmode):
        val = struct.pack( TUNER_ST, index, "", 0,0,0,0,0,audmode,0,0)
        r = ioctl(self.devfd,SET_TUNER_NO,val)


    def getaudio(self,index):
        val = struct.pack( AUDIO_ST, index, "", 0,0)
        r = ioctl(self.devfd,GET_AUDIO_NO,val)
        return struct.unpack( AUDIO_ST, r )


    def setaudio(self,index,mode):
        val = struct.pack( AUDIO_ST, index, "", mode, 0)
        r = ioctl(self.devfd,SET_AUDIO_NO,val)


    def init_settings(self):
        if not self.settings:
            # XXX: clever error here
            return

        self.basic_info(self.settings.vdev)

        self.setstd(NORMS.get(self.settings.norm))
        self.setchanlist(self.settings.chanlist)

        self.setinput(self.settings.input)

        # XXX TODO: make a good way of setting the capture resolution
        # self.setfmt(int(width), int(height))


    def print_settings(self):
        print 'Driver: %s' % self.driver
        print 'Card: %s' % self.card
        print 'Version: %s' % self.version
        print 'Capabilities: %s' % self.capabilities

        print "Enumerating supported Standards."
        try:
            for i in range(0,255):
                (index,id,name,junk,junk,junk) = self.enumstd(i)
                print "  %i: 0x%x %s" % (index, id, name)
        except:
            pass
        print "Current Standard is: 0x%x" % self.getstd()

        print "Enumerating supported Inputs."
        try:
            for i in range(0,255):
                (index,name,type,audioset,tuner,std,status) = self.enuminput(i)
                print "  %i: %s" % (index, name)
        except:
            pass
        print "Input: %i" % self.getinput()

        (buf_type, width, height, pixelformat, field, bytesperline,
         sizeimage, colorspace) = self.getfmt()
        print "Width: %i, Height: %i" % (width,height)

        print "Read Frequency: %i" % self.getfreq()


