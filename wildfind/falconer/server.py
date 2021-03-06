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

from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from SocketServer import ThreadingMixIn
import os
import threading

from wildfind.falconer.utils import get_resource_htdocs


PORT = 12015


class Server(object):
    def __init__(self, heatmap):
        handler = Handler
        handler.heatmap = heatmap
        self._server = ThreadedServer(('localhost', PORT), Handler)

        thread = threading.Thread(target=self._server.serve_forever)
        thread.start()

    def close(self):
        self._server.shutdown()


class ThreadedServer(ThreadingMixIn, HTTPServer):
    allow_reuse_address = False


class Handler(BaseHTTPRequestHandler):
    heatmap = None

    def do_GET(self):
        if self.path.startswith('/heatmap.png'):
            self.send_response(200)
            self.send_header('Content-type', 'image/png')
            self.send_header('cache-control', 's-maxage=0 , no-cache')
            self.end_headers()
            self.heatmap.seek(0)
            self.wfile.write(self.heatmap.read())
        else:
            path = get_resource_htdocs(self.path.lstrip('/'))

            if os.path.exists(path):
                self.send_response(200)
                self.__send_content_type(path)
                self.end_headers()

                f = open(path, 'rb')
                self.wfile.write(f.read())
                f.close()
            else:
                self.send_response(404)
                self.end_headers()

    def log_message(self, _format, *_args):
        return

    def __send_content_type(self, path):
        content = 'text/plain'
        _root, ext = os.path.splitext(path)
        if ext == '.css':
            content = 'text/css'
        elif ext == '.html':
            content = 'text/html'
        elif ext == '.gif':
            content = 'image/gif'
        elif ext == '.js':
            content = 'text/javascript'

        self.send_header('Content-type', content)


if __name__ == '__main__':
    print 'Please run falconer.py'
    exit(1)
