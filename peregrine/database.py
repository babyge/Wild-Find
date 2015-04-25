#
# Project Peregrine
#
#
# Copyright 2014 - 2015 Al Brown
#
# Wildlife tracking and mapping
#
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import Queue
import os
import sqlite3
import threading
import time

from constants import LOG_SIZE
import events


VERSION = 1

ADD_SIGNAL, GET_SIGNALS_LAST, GET_SIGNALS, \
    GET_SCANS, DEL_SCAN, DEL_SCANS, \
    ADD_LOG, GET_LOG, \
    CLOSE = range(9)


class Database(threading.Thread):
    def __init__(self, path, notify):
        threading.Thread.__init__(self)
        self.name = 'Database'

        self._path = path
        self._notify = notify

        self._conn = None
        self._queue = Queue.Queue()

        if os.path.exists(path):
            print 'Appending data to {}'.format(path)
        else:
            print 'Creating {}'.format(path)

        self.start()

    def __name_factory(self, cursor, row):
        names = {}
        for i, column in enumerate(cursor.description):
            names[column[0]] = row[i]

        return names

    def __create(self):
        self._conn = sqlite3.connect(self._path)
        self._conn.row_factory = self.__name_factory

        with self._conn:
            cmd = 'pragma foreign_keys = 1;'
            self._conn.execute(cmd)
            cmd = 'pragma auto_vacuum = incremental;'
            self._conn.execute(cmd)

            # Info table
            cmd = ('create table if not exists '
                   'Info ('
                   '    Key text primary key,'
                   '    Value blob)')
            self._conn.execute(cmd)
            try:
                cmd = 'insert into info VALUES ("DbVersion", ?)'
                self._conn.execute(cmd, (VERSION,))
            except sqlite3.IntegrityError as error:
                pass
            except sqlite3.OperationalError as error:
                err = 'Database error: {}'.format(error.message)
                events.Post(self._notify).error(error=err)
                return

            # Scans table
            cmd = ('create table if not exists '
                   'Scans ('
                   '    TimeStamp integer primary key)')
            self._conn.execute(cmd)

            # Signals table
            cmd = ('create table if not exists '
                   'Signals ('
                   '    Id integer primary key autoincrement,'
                   '    TimeStamp integer,'
                   '    Freq real,'
                   '    Mod integer,'
                   '    Rate real,'
                   '    Level real,'
                   '    Lon real,'
                   '    Lat real,'
                   '    foreign key (TimeStamp) REFERENCES Scans (TimeStamp)'
                   '        on delete cascade)')
            self._conn.execute(cmd)

            # Log table
            cmd = ('create table if not exists '
                   'Log ('
                   '    Id integer primary key autoincrement,'
                   '    TimeStamp text,'
                   '    Message )')
            self._conn.execute(cmd)

            # Log pruning trigger
            cmd = ('create trigger if not exists LogPrune insert on Log when '
                   '(select count(*) from log) > {} '
                   'begin'
                   '    delete from Log where Log.Id not in '
                   '      (select Log.Id from Log order by'
                   '          Id desc limit {});'
                   'end;').format(LOG_SIZE, LOG_SIZE - 1)
            self._conn.execute(cmd)

    def __add_signal(self, **kwargs):
        with self._conn:
            timeStamp = int(kwargs['timeStamp'])
            signal = kwargs['signal']

            cmd = 'insert into Scans values(?)'
            try:
                self._conn.execute(cmd, (timeStamp,))
            except sqlite3.IntegrityError:
                pass

            cmd = 'insert into Signals values (null, ?, ?, ?, ?, ?, ?, ?)'
            self._conn.execute(cmd, (timeStamp,
                                     signal.freq,
                                     signal.mod,
                                     signal.rate,
                                     signal.level,
                                     signal.lon,
                                     signal.lat))

    def __add_log(self, **kwargs):
        with self._conn:
            timeStamp = int(kwargs['timeStamp'])
            message = kwargs['message']

            cmd = 'insert into Log values (null, ?, ?)'
            self._conn.execute(cmd, (timeStamp, message))

    def __get_scans(self, callback):
        cursor = self._conn.cursor()
        cmd = 'select * from Scans'
        cursor.execute(cmd)
        scans = cursor.fetchall()
        callback(scans)

    def __get_signals_last(self, callback):
        cursor = self._conn.cursor()
        cmd = 'select * from Signals order by Id desc limit 1'
        cursor.execute(cmd)
        signals = cursor.fetchall()
        for signal in signals:
            del signal['Id']
        callback(signals)

    def __get_signals(self, callback, timeStamp):
        cursor = self._conn.cursor()
        cmd = 'select * from Signals where TimeStamp = ?'
        cursor.execute(cmd, (timeStamp,))
        signals = cursor.fetchall()
        for signal in signals:
            del signal['Id']
        callback(signals)

    def __get_log(self, callback):
        cursor = self._conn.cursor()
        cmd = 'select * from Log'
        cursor.execute(cmd)
        signals = cursor.fetchall()
        for signal in signals:
            del signal['Id']
        callback(signals)

    def __del_scan(self, callback, timeStamp):
        cursor = self._conn.cursor()
        cmd = 'delete from Scans where TimeStamp = ?'
        with self._conn:
            cursor.execute(cmd, (timeStamp,))
        callback(cursor.rowcount)

    def __del_scans(self, callback):
        cursor = self._conn.cursor()
        cmd = 'delete from Scans'
        with self._conn:
            cursor.execute(cmd)
            self._conn.execute('pragma incremental_vacuum;')
        callback(cursor.rowcount)

    def run(self):
        self.__create()

        while True:
            if not self._queue.empty():
                event = self._queue.get()
                eventType = event.get_type()

                if eventType == ADD_SIGNAL:
                    self.__add_signal(**event.get_args())
                elif eventType == GET_SCANS:
                    callback = event.get_arg('callback')
                    self.__get_scans(callback)
                elif eventType == GET_SIGNALS_LAST:
                    callback = event.get_arg('callback')
                    self.__get_signals_last(callback)
                elif eventType == GET_SIGNALS:
                    callback = event.get_arg('callback')
                    timeStamp = event.get_arg('timeStamp')
                    self.__get_signals(callback, timeStamp)
                elif eventType == DEL_SCAN:
                    callback = event.get_arg('callback')
                    timeStamp = event.get_arg('timeStamp')
                    self.__del_scan(callback, timeStamp)
                elif eventType == DEL_SCANS:
                    callback = event.get_arg('callback')
                    self.__del_scans(callback)
                if eventType == ADD_LOG:
                    self.__add_log(**event.get_args())
                if eventType == GET_LOG:
                    callback = event.get_arg('callback')
                    self.__get_log(callback)
                elif eventType == CLOSE:
                    self._conn.close()
            else:
                time.sleep(0.05)

        self._conn.close()

    def append_signal(self, timeStamp, signal):
        event = events.Event(ADD_SIGNAL, signal=signal, timeStamp=timeStamp)
        self._queue.put(event)

    def append_log(self, message):
        event = events.Event(ADD_LOG, message=message, timeStamp=time.time())
        self._queue.put(event)

    def get_scans(self, callback):
        event = events.Event(GET_SCANS, callback=callback)
        self._queue.put(event)

    def get_signals_last(self, callback):
        event = events.Event(GET_SIGNALS_LAST, callback=callback)
        self._queue.put(event)

    def get_signals(self, callback, timeStamp):
        event = events.Event(GET_SIGNALS, callback=callback,
                             timeStamp=timeStamp)
        self._queue.put(event)

    def get_log(self, callback):
        event = events.Event(GET_LOG, callback=callback)
        self._queue.put(event)

    def del_scan(self, callback, timeStamp):
        event = events.Event(DEL_SCAN, callback=callback,
                             timeStamp=timeStamp)
        self._queue.put(event)

    def del_scans(self, callback):
        event = events.Event(DEL_SCANS, callback=callback)
        self._queue.put(event)

    def stop(self):
        event = events.Event(CLOSE)
        self._queue.put(event)