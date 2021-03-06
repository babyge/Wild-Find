#!/usr/bin/env python
#
#
# Wild Find
#
#
# Copyright 2014 - 2017 Al Brown
#
# Wildlife tracking and mapping
#
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as published by
# the Free Software Foundation
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import math
import os
import sqlite3

from wildfind.common.database import create_database, name_factory


class Database(object):
    def __init__(self):
        self._fileName = None
        self._conn = None

    def __connect(self, fileName):
        self._fileName = os.path.basename(fileName)
        self._conn = sqlite3.connect(fileName)
        self._conn.row_factory = name_factory

        return create_database(self._conn)

    def __filter(self, cursor, filteredSurveys, filteredScans=None, filteredSignals=None):
        condition = ' '
        condSurveys = ''
        condScans = ''
        condSignals = ''

        if len(filteredSurveys):
            cmd = 'select TimeStamp from Scans where Survey not in ('
            cmd += str(filteredSurveys).strip('[]')
            cmd += ')'
            cursor.execute(cmd)
            rows = cursor.fetchall()
            timeStamps = [row['TimeStamp'] for row in rows]

            condSurveys = ' TimeStamp in ('
            condSurveys += str(timeStamps).strip('[]')
            condSurveys += ') '

        if filteredScans is not None and len(filteredScans):
            condScans = ' TimeStamp not in ('
            condScans += str(filteredScans).strip('[]')
            condScans += ') '

        if filteredSignals is not None and len(filteredSignals):
            condSignals = ' Freq not in ('
            condSignals += str(filteredSignals).strip('[]')
            condSignals += ') '

        if len(condSurveys) or len(condScans) or len(condSignals):
            condition = ' where '
            if len(condSurveys):
                condition += condSurveys
            if len(condScans):
                if len(condSurveys):
                    condition += 'and'
                condition += condScans
            if len(condSignals):
                if len(condSurveys) or len(condScans):
                    condition += 'and'
                condition += condSignals

        return condition

    def open(self, fileName):
        return self.__connect(fileName)

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def is_connected(self):
        if self._conn is None:
            return False

        return True

    def add_scans(self, scans):
        with self._conn:
            for scan in scans:
                timeStamp = int(scan['TimeStamp'])
                freq = float(scan['Freq'])
                survey = scan['Survey']

                cmd = 'insert or ignore into Scans values(?, ?, ?)'
                self._conn.execute(cmd, (timeStamp, freq, survey))

    def add_signals(self, signals):
        with self._conn:
            for signal in signals:
                timeStamp = int(signal['TimeStamp'])
                freq = float(signal['Freq'])
                mod = int(signal['Mod'])
                rate = float(signal['Rate'])
                level = float(signal['Level'])
                lon = float(signal['Lon'])
                lat = float(signal['Lat'])

                cmd = ('insert or replace into Signals values'
                       '    ((select Id from Signals where'
                       '        TimeStamp=? and'
                       '        Freq=? and'
                       '        Mod=? and'
                       '        Rate=? and'
                       '        Level=? and'
                       '        Lon=? and'
                       '        lat=?),'
                       '      ?, ?, ?, ?, ?, ?, ?)')
                self._conn.execute(cmd,
                                   (timeStamp,
                                    freq,
                                    mod,
                                    rate,
                                    level,
                                    lon,
                                    lat,
                                    timeStamp,
                                    freq,
                                    mod,
                                    rate,
                                    level,
                                    lon,
                                    lat))

    def add_log(self, log):
        with self._conn:
            for entry in log:
                timeStamp = int(entry['TimeStamp'])
                message = entry['Message']

                cmd = ('insert or replace into Log values'
                       '    ((select Id from Log where'
                       '        TimeStamp=? and'
                       '        Message=?),'
                       '      ?, ?)')
                self._conn.execute(cmd,
                                   (timeStamp, message,
                                    timeStamp, message))

    def get_filename(self):
        return self._fileName

    def get_cursor(self):
        return self._conn.cursor()

    def get_surveys(self):
        cursor = self.get_cursor()
        cmd = 'select * from Scans group by Survey'
        cursor.execute(cmd)
        rows = cursor.fetchall()
        surveys = [row['Survey'].encode("utf-8") for row in rows]

        return surveys

    def get_scans(self, filteredSurveys):
        if self._conn is None:
            return []

        cursor = self.get_cursor()
        cmd = 'select * from Scans'
        cmd += self.__filter(cursor,
                             filteredSurveys)

        cursor.execute(cmd)
        rows = cursor.fetchall()
        scans = [[row['TimeStamp'], row['Freq']] for row in rows]

        return scans

    def get_signals(self, filteredSurveys, filteredSignals, filteredScans):
        if self._conn is None:
            return []

        cursor = self.get_cursor()

        cmd = 'select Freq, avg(Rate), count(Freq), avg(Level) from Signals'
        cmd += self.__filter(cursor,
                             filteredSurveys,
                             filteredScans,
                             filteredSignals)
        cmd += 'group by Freq'

        cursor.execute(cmd)
        rows = cursor.fetchall()
        signals = [[row['Freq'], row['avg(Rate)'], row['count(Freq)'], 10 * math.log10(row['avg(Level)'])]
                   for row in rows]

        return signals

    def get_telemetry(self, filteredSurveys, filteredScans, filteredSignals):
        if self._conn is None:
            return []

        cursor = self.get_cursor()
        cmd = 'select Id, Freq, Rate, Level, Lon, Lat from Signals'
        cmd += self.__filter(cursor,
                             filteredSurveys,
                             filteredScans,
                             filteredSignals)
        cmd += 'order by Id'

        cursor.execute(cmd)
        rows = cursor.fetchall()

        telemetry = [row for row in rows
                     if row['Level'] is not None and row['Level'] > 0]
        for row in telemetry:
            row['Level'] = 10 * math.log10(row['Level'])

        return telemetry

    def get_logs(self):
        cursor = self.get_cursor()

        cmd = 'select * from Log'
        cursor.execute(cmd)
        rows = cursor.fetchall()
        logs = [[row['TimeStamp'], row['Message']] for row in rows]

        return logs

    def merge(self, database):
        with self._conn:
            cursorDest = self.get_cursor()
            cursorSource = database.get_cursor()

            cmd = 'select name from sqlite_master where type = "table"'
            cursorDest.execute(cmd)
            rows = cursorDest.fetchall()
            tables = [row['name'] for row in rows
                      if row['name'] not in ['sqlite_sequence']]

            for table in tables:
                cmd = 'select * from {}'.format(table)
                cursorSource.execute(cmd)
                rows = cursorSource.fetchall()

                if len(rows):
                    columns = ', '.join(rows[0].keys())
                    places = ':' + ', :'.join(rows[0].keys())
                    cmd = 'insert or ignore into {} ({} ) values ({})'.format(table,
                                                                              columns,
                                                                              places)
                    for row in rows:
                        if 'id' in row:
                            row['id'] = 'null'
                        cursorDest.execute(cmd, row)

    def filter(self, filteredSurveys, filteredScans, filteredSignals):
        with self._conn:
            cursor = self.get_cursor()

            cmd = 'delete from Scans where Survey in ('
            cmd += str(filteredSurveys).strip('[]')
            cmd += ')'
            cursor.execute(cmd)

            cmd = 'delete from Scans where TimeStamp in ('
            cmd += str(filteredScans).strip('[]')
            cmd += ')'
            cursor.execute(cmd)

            cmd = 'delete from Signals where Freq in ('
            cmd += str(filteredSignals).strip('[]')
            cmd += ')'
            cursor.execute(cmd)

            self._conn.execute("VACUUM")


if __name__ == '__main__':
    print 'Please run falconer.py'
    exit(1)
