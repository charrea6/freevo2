# -*- coding: iso-8859-1 -*-
# -----------------------------------------------------------------------------
# mcomm.py - wrapper for mbus communication for Freevo
# -----------------------------------------------------------------------------
# $Id$
#
# This file registers the application to the mbus and provides some wrapper
# functions and classes for easier access.
#
# If not present, this module will generate a mbus configuration file in
# ~/.mbus with some basic mbus settings. All applications on the mbus need
# to have the same settings to communicate. All known mbus implementations
# read this file, if you have mbus applications with different users, please
# make sure the entries match. If your applications are on different hosts,
# change SCOPE=LINKLOCAL in the config file. Also make sure you have a valid
# route for the given address. If the default route is used, make sure the
# mbus messages are not eaten by an iptable rule.
#
# Note: this is a test only right now. To test some basic stuff, call
#       './freevo recordserver' and
#       './freevo execute src/tv/recordings.py' in two different shells.
#
# -----------------------------------------------------------------------------
# Freevo - A Home Theater PC framework
# Copyright (C) 2002-2004 Krister Lagerstrom, Dirk Meyer, et al.
#
# First Edition: Dirk Meyer <dmeyer@tzi.de>
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


__all__ = [ 'MException', 'RPCReturn', 'RPCError', 'RPCServer', 'get_address',
            'register_entity_notification', 'find' ]


# python imports
import os
import sys
import random
import string
import time
import traceback

# notifier / mbus import
import notifier
import mbus

# freevo imports
import config



# dict of all our mbus instances
_instance_list = {}

def instance(name='default'):
    """
    Return the mbus instance with the given name. Create the instance
    if it does not yet exist. Use the name 'default' to get the default
    instance for this application.
    """
    if _instance_list.has_key(name):
        return _instance_list[name]
    i = Instance(name)
    _instance_list[name] = i
    if i == 'default':
        _instance_list[i.module] = i
    return i


class MException(Exception):
    """
    Mbus related exception
    """
    pass


class RPCReturn(mbus.RPCReturn):
    """
    A positive rpc response. Sending this signals the caller that the call
    was sucessfull.
    """
    def __init__(self, result = [], description = 'success'):
        mbus.RPCReturn.__init__(self, result, 'OK', description)


class RPCError(mbus.RPCReturn):
    """
    A positive rpc response. Sending this signals the caller that the call
    was unsucessfull for the given reason.
    """
    def __init__(self, description):
        mbus.RPCReturn.__init__(self, [], 'FAILED', description)



class RemoteEntity:
    """
    Wrapper class for an Entity. It is possible to act with this object like
    it is a real class, only that the calls are handled by the remote
    application.

    There are three different ways to call a function:
    1. add a callback to the end of the parameter list of a function call
       e.g.: RemoteEntity.function_to_call(arg1, arg2, callback)
    2. add the callback as **args to the function:
       e.g.: RemoteEntity.function_to_call(arg2, arg2, callback=callback)
    3. provide no callback function and the call will wait for the return
       e.g.: result = RemoteEntity.function_to_call(arg2, arg2)
    """
    def __init__(self, addr, mbus_instance):
        self.addr = addr
        self.cmd = None
        self.present = True
        self.mbus_instance = mbus_instance


    def matches(self, addr):
        """
        Return True if the given addr matches the address of the object.
        The given address can also be a subset of the objects address
        informations.
        """
        return mbus.isAddressedTo(addr, self.addr)


    def __getattr__(self, attr):
        """
        Wrapper function to make it possible to call functions from
        the remote entity.
        """
        if attr in ('has_key', ) or attr.startswith('__'):
            return getattr(self.addr, attr)
        self.cmd  = attr.replace('_', '-')
        return self.__call


    def __callback(self, return_list, data = None):
        """
        Internal callback when the function should return the resuls.
        """
        self.result = return_list


    def __call(self, *args, **kargs):
        """
        Internal function to do the real RPC call.
        """
        if args and callable(args[-1]):
            callback    = args[-1]
            cmdargs     = args[:-1]
            self.result = True
        elif kargs.has_key('callback'):
            callback    = kargs['callback']
            cmdargs     = args
            self.result = True
        else:
            callback    = self.__callback
            cmdargs     = args
            wait        = True
            self.result = None
        self.mbus_instance.sendRPC(self.addr, 'home-theatre.' + self.cmd,
                                   cmdargs, callback)

        if self.result == True:
            return True

        # wait for return
        while not self.result:
            notifier.step(True, False)

        # check for errors / exceptions and raise them
        if isinstance(self.result, mbus.types.MError):
            raise MException(self.result.descr)

        status, args = self.result[0][1:]
        r = self.result[0][1:]
        if status[0] == 'FAILED':
            print status
            if status[1] in ('TypeError', ):
                raise eval(status[1])(status[2])
            else:
                raise MException('%s: %s' % (status[1], status[2]))

        # normal return handling
        if status[1] == 'OK':
            return True, args
        return False, args


    def __eq__(self, obj):
        """
        Compare two Entities based on the addr.
        """
        if hasattr(obj, 'addr'):
            obj = obj.addr
        return self.addr == obj



class RPCServer:
    """
    A base class for a RPC Server. All functions starting with __rpc and
    ending with __ are registered for the specific command.
    """
    def __init__(self, mbus_instance='default'):
        """
        Register all callbacks
        """
        add_callback = instance(mbus_instance).addRPCCallback
        for f in dir(self):
            if f.startswith('__rpc_'):
                cmdname = 'home-theatre.' + f[6:-2].replace('_', '-')
                add_callback(cmdname, getattr(self, f))


    def parse_parameter(self, val, pattern):
        """
        Parse the given parameter and send a TypeError if the parameters
        don't match the pattern.
        """
        if len(pattern) == len(val):
            if len(val) == 1:
                return val[0]
            return val
        if len(pattern) == 1:
            arg = '1 argument'
        else:
            arg = '%s arguments' % len(pattern)
        function = traceback.extract_stack(limit = 2)[0][2][6:-2]
        msg = '%s() takes %s (%s given)' % (function, arg, len(val))
        raise mbus.RPCException('TypeError', msg)



def get_address(name):
    """
    Return a mbus address based on the freevo naming scheme.
    """
    if name == 'default':
        name = os.path.splitext(os.path.basename(sys.argv[0]))[0]
    if name in ('main', 'freevo'):
        name = 'core'
    return mbus.MAddress({'type': 'home-theatre', 'module': name })


def register_entity_notification(func):
    """
    Register to callback to get notification when an entity joins or leaves
    the mbus. The parameter of the callback is an 'RemoteEntity'. The attribute
    'present' of this entity can be used to check if the entity joined the
    bus (present = True) or is gone now (present = False).
    """
    return instance().register_entity_notification(func)


def find(name, timeout = 10000):
    """
    Wait for an entity matching 'name'. Return the entity or None if no
    entity is found after timeout. In most cases this function is needed
    for helpers connection to freevo or the recordserver.
    """
    return instance().find(name, timeout)



class Instance(mbus.Guides):
    """
    Freevo mbus instance for mbus communication
    """
    def __init__(self, name='default'):
        """
        Create the mbus address and connect to the mbus
        """
        # build mbus name including app=freevo
        addr = get_address(name)
        addr['app'] = 'freevo'

        # init the mbus interface
        mbus.Guides.__init__( self, addr )

        # set callbacks
        self.newEntityFunction = self.new_entity
        self.lostEntityFunction = self.lost_entity
        self.errorFunction = None
        self.onErrorInvokeRPCCallback = True
        
        # application short name
        self.module = addr['module']

        # a list of our callbacks when an entity joins or leaves the bus
        self.__notification_callbacks = []

        # a list of all known entities
        self.__entities = []


    def register_entity_notification(self, func):
        """
        Register to callback to get notification when an entity joins or leaves
        the mbus. The parameter of the callback is an 'RemoteEntity'. The
        attribute 'present' of this entity can be used to check if the entity
        joined the bus (present = True) or is gone now (present = False).
        """
        self.__notification_callbacks.append(func)


    def find(self, name, timeout = 10000):
        """
        Wait for an entity matching 'name'. Return the entity or None if no
        entity is found after timeout. In most cases this function is needed
        for helpers connection to freevo or the recordserver.
        """
        addr = get_address(name)
        t1 = time.time()
        while 1:
            for e in self.__entities:
                if mbus.isAddressedTo(addr, e.addr):
                    return e
            if t1 + float(timeout) / 1000 < time.time():
                return None
            notifier.step(True, False)


    def new_entity(self, maddr):
        """
        pyMbus callback for new entity
        """
        e = RemoteEntity(maddr, self)
        self.__entities.append(e)
        for c in self.__notification_callbacks:
            c(e)


    def lost_entity(self, maddr):
        """
        pyMbus callback for lost entity
        """
        for e in self.__entities:
            if e == maddr:
                self.__entities.remove(e)
                e.present = False
                for c in self.__notification_callbacks:
                    c(e)
                break


# Check for mbus configuration file. It is either ~/.mbus or defined
# in the environment variable MBUS.
mbus_config = os.path.expanduser('~/.mbus')
if os.environ.has_key('MBUS'):
    mbus_config = os.environ['MBUS']

if not os.path.isfile(mbus_config):
    # If the file does not exist, generate one with a random hash key
    # and a user defined port. For security reasons it is not allowed
    # to have read access to this file for 'others'
    tmp = open(os.path.join(config.SHARE_DIR, 'mbus.conf'))
    cfg = open(mbus_config, 'w')
    for line in tmp.readlines():
        if line.startswith('PORT='):
            # generate new user defined port
            line = 'PORT=%s\n' % (47000 + os.getuid())
        if line.startswith('HASHKEY='):
            # generate new random has key
            chars = string.ascii_letters + string.digits
            line = 'HASHKEY=(HMAC-MD5-96, '
            for i in range(16):
                line += chars[random.randint(0, len(chars)-1)]
            line += ')\n'
        # write line to config file
        cfg.write(line)
    tmp.close()
    cfg.close()
    os.chmod(mbus_config, 0600)


if config.HELPER and not notifier.loop:
    # init the notifier (not done yet)
    notifier.init( notifier.GENERIC )