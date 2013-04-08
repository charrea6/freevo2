import struct

import kaa
import logging

# https://www.lonelycoder.com/redmine/projects/tvheadend/wiki/Htsp

class binary(str):
    pass

class Client(object):

    host = None

    def __init__(self):
        self._data = ''
        self._seq = 0
        self._requests = {}
        self.channels = []
        self._channels_map = {}
        self._events = {}
        self.dvr_entries = DVREntries()
        self.connected = kaa.InProgress()

    @kaa.coroutine()
    def connect(self, host, sync_epg=True):
        self.host = host
        self.socket = kaa.Socket()
        self.socket.signals['read'].connect(self.__read)
        yield self.socket.connect((host, 9982))
        yield self.send('hello', htspversion=5, clientname='Freevo', clientversion='2.0git')
        self.send('enableAsyncMetadata', epg=sync_epg and 1 or 0, async=False)
        self.connected = kaa.InProgress()
        yield self.connected

    def send(self, command, **args):
        async = args.pop('async', True)
        self._seq += 1
        args['method'] = command
        args['seq'] = self._seq
        value = ''.join([self._encode(*i) for i in args.items()])
        if async:
            self._requests[self._seq] = kaa.InProgress()
        self.socket.write(struct.pack('>I', len(value)) + value)
        if async:
            return self._requests[self._seq]

    def _encode(self, key, value):
        # https://www.lonelycoder.com/redmine/projects/tvheadend/wiki/Htsmsgbinary
        if isinstance(value, unicode):
            value = str(value)
        if isinstance(value, binary):
            vtype = 4
        elif isinstance(value, str):
            vtype = 3
        elif isinstance(value, dict):
            value = ''.join([self._encode(*i) for i in value.items()])
            vtype = 1
        elif isinstance(value, int):
            value = struct.pack('q', value).rstrip('\00')
            vtype = 2
        else:
            raise AttributeError('unsupported type %s' % type(value))
        return struct.pack('bb', vtype, len(key)) + struct.pack('>I', len(value)) + key + value

    def _decode(self, data, result):
        # https://www.lonelycoder.com/redmine/projects/tvheadend/wiki/Htsmsgbinary
        vtype, nlen = struct.unpack('bb', data[:2])
        dlen = struct.unpack('>I', data[2:6])[0]
        key = data[6:6+nlen]
        value = data[6+nlen:6+nlen+dlen]
        if vtype == 1:
            r = {}
            while value:
                value = self._decode(value, r)
            value = r
        elif vtype == 2:
            value = struct.unpack('q', value.ljust(8, '\00'))[0]
        elif vtype == 3:
            pass
        elif vtype == 4:
            value = binary(value)
        elif vtype == 5:
            r = []
            while value:
                value = self._decode(value, r)
            value = r
        else:
            log.error('unsupported type %s', vtype)
            value = None
        if isinstance(result, list):
            result.append(value)
        else:
            result[key] = value
        return data[6+nlen+dlen:]

    def __read(self, data):
        self._data += data
        while True:
            if len(self._data) < 4:
                return
            length = struct.unpack('>I', self._data[:4])[0]
            if length > len(self._data[4:]):
                return
            data = self._data[4:4+length]
            result = {}
            while data:
                data = self._decode(data, result)
            if 'seq' in result and result['seq'] in self._requests:
                inprogress = self._requests.pop(result['seq'])
                inprogress.finish(result)
            elif 'method' in result:
                if hasattr(self, 'event_' + result['method']):
                    getattr(self, 'event_' + result.pop('method'))(result)
                else:
                    log.error('unsupported method %s', result.get('method'))
            self._data = self._data[4+length:]

    def event_eventAdd(self, result):
        e = Event(self, result)
        self._events[result['eventId']] = e
        c = e.channel
        if c:
            c.events.append(e)

    def event_eventDelete(self, result):
        e = self._events.get(result['eventId'])
        if e:
            c = e.channel
            if c:
                c.events.remove(e)
            del self._events[result['eventId']]

    def event_eventUpdate(self, result):
        e = self._events.get(result['eventId'])
        if e:
            e.__dict__.update(result)

    def event_channelAdd(self, result):
        c  = Channel(self, result)
        self.channels.append(c)
        self._channels_map[c.channelId] = c

    def event_channelDelete(self, result):
        c = self._channels_map.get(result['channelId'])
        if c:
            self.channels.remove(c)
            del self._channels_map[result['channelId']]

    def event_channelUpdate(self, result):
        c = self._channels_map.get(result['channelId'])
        if c:
            c.__dict__.update(result)

    def event_dvrEntryAdd(self, result):
        d = DVREntry(self, result)
        self.dvr_entries._entries[result['id']] = d

    def event_dvrEntryDelete(self, result):
        del self.dvr_entries._entries[result['id']]

    def event_dvrEntryUpdate(self, result):
        d = self.dvr_entries._entries[result['id']]
        if d:
            d.__dict__.update(result)

    def event_initialSyncCompleted(self, result):
        self.connected.finish(None)

    @kaa.coroutine()
    def get_disk_space(self):
        result = yield self.send('getDiskSpace')
        yield result['freediskspace'], result['totaldiskspace']

    @kaa.coroutine()
    def get_sys_time(self):
        result = yield self.send('getSysTime')
        yield result['time'], result['timezone']

    @kaa.coroutine()
    def check_conflict(self, **kwargs):
        result = yield self.send('checkConflict', **kwargs)
        if result['conflict']:
            suggestions = []
            for dqr in result['suggestions']:
                array = []
                for d in dqr:
                    array.append(self.dvr_entries._entries[d])
                suggestions.append(array)
            yield suggestions


class TVHEObject(object):
    """Base class for all TVHeadend  Objects.
    Handles updates that are sent from the server and stores a reference to the client connection.
    """
    def __init__(self, client, data):
        self._client = client
        self.__dict__.update(data)


class Channel(TVHEObject):
    """TVHeadend Channel,has all the same properties as described in the htsp protocol.
    """
    def __init__(self, client, data):
        super(Channel, self).__init__(client, data)
        self.events = []

    @kaa.coroutine()
    def stream(self):
        result = yield self._client.send('getTicket', channelId=self.channelId)
        yield 'http://%s:9981%s?ticket=%s' % (self.host, result['path'], result['ticket'])

    @kaa.coroutine()
    def record(self, start, stop, **kwargs):
        result = yield self._client.send('addDvrEntry', channelId=self.channelId, start=start, stop=stop, **kwargs)
        if result['success']:
            yield result['id']
        raise TVHEError(result['error'])

    def check_conflict(self, start, stop):
        return self._client.check_conflict(channelId=self.channelId, start=start, stop=stop)

    @property
    def event(self):
        return self._client._events.get(self.eventId)

    @property
    def next_event(self):
        return self._client._events.get(self.nextEventId)



class Event(TVHEObject):
    """TVHeadend Event,has all the same properties as described in the htsp protocol.
    """
    @property
    def channel(self):
        return self._client._channels_map.get(self.channelId)

    @property
    def next_event(self):
        return self._client._events.get(self.nextEventId)

    @property
    def dvr_entry(self):
        if hasattr(self, 'dvrId'):
            return self._client.dvr_entries._entries[self.dvrId]

    @kaa.coroutine()
    def record(self, **kwargs):
        result = yield self._client.send('addDvrEntry', eventId=self.eventId, **kwargs)
        if result['success']:
            yield self._client.dvr_entries._entries.get(result['id'],result['id'])
        raise TVHEError(result['error'])

    def check_conflict(self):
        return self._client.check_conflict(eventId=self.eventId)



class DVREntry(TVHEObject):
    """TVHeadend DVR Entry,has all the same properties as described in the htsp protocol.
    """
    @kaa.coroutine()
    def update(self, **kwargs):
        result = yield self._client.send('updateDvrEntry', id=self.id, **kwargs)
        if result['success']:
            yield True
        raise TVHEError(result['error'])

    @kaa.coroutine()
    def cancel(self):
        result = yield self._client.send('cancelDvrEntry', id=self.id)
        if result['success']:
            yield True
        raise TVHEError(result['error'])

    @kaa.coroutine()
    def delete(self):
        result = yield self._client.send('deleteDvrEntry', id=self.id)
        if result['success']:
            yield True
        raise TVHEError(result['error'])


class DVREntries(object):
    """Class to hold DVREntries and allow filter of those entries based on their state.
    """
    def __init__(self):
        self._entries = {}

    def __filter(self, state):
        r = []
        for e in self._entries.values():
            if e.state == state:
                r.append(e)
        return r

    @property
    def all(self):
        return self._entries.values()

    @property
    def completed(self):
        return self.__filter('completed')

    @property
    def scheduled(self):
        return self.__filter('scheduled')

    @property
    def recording(self):
        return self.__filter('recording')

    @property
    def missed(self):
        return self.__filter('missed')

class TVHEError(Exception):
    pass

if __name__ == "__main__":
    import time
    import sys

    if len(sys.argv) < 2:
        print 'usage: %s <tvheadend hostname>'
        sys.exit(1)

    log = logging.getLogger()
    log.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)-15s %(levelname)s %(module)s(%(lineno)s): %(message)s')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    log.addHandler(handler)

    @kaa.coroutine()
    def main():
        tv = Client()
        yield tv.connect(sys.argv[1])
        free_space, total_space = yield tv.get_disk_space()
        print '%d/%d (%d%% free)' % (free_space, total_space, (free_space * 100) / total_space)
        print '%d channels' % len(tv.channels)
        channel = None
        for c in tv.channels:
            print '%s: %d events' % (c.channelName,len(c.events))
            if len(c.events) > 3:
                channel = c

        if channel is not None:
            print 'Selected channel', channel.channelName
            now = time.time()

            for e in channel.events:
                if e.start > now + (10*60):
                    event = e
                    break
            print 'Recording ', event.title
            conflicts = yield event.check_conflict()
            print 'Conflicts?', conflicts
            dvr = yield event.record()
            print 'DVREntry id', dvr.id

            for d in tv.dvr_entries.scheduled:
                if d.id == dvr.id:
                    print 'Found our recording!'
                    success = yield  d.delete()
                    if success:
                        print 'Delete recording'

        kaa.main.stop()
    main()
    kaa.main.run()
