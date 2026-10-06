"""Serves the export file on the local network for a few minutes, so it can be downloaded from a browser."""

import secrets
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORTS = range(8765, 8775)


def local_ip():
    # Connecting a UDP socket sends nothing; it only makes the OS pick the outgoing interface.
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class Share:
    """One file, one unguessable URL, a time limit. Everything else on the server is a 404."""

    def __init__(self):
        self._server = None
        self._timer = None
        self.url = None

    def start(self, path, file_name, seconds=600, host="0.0.0.0"):
        self.stop()
        token = secrets.token_urlsafe(9)
        wanted = "/%s/%s" % (token, file_name)

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != wanted:
                    self.send_error(404)
                    return
                try:
                    with open(path, "rb") as f:
                        body = f.read()
                except OSError:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Disposition", 'attachment; filename="%s"' % file_name)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                pass

        last_error = None
        for port in PORTS:
            try:
                self._server = ThreadingHTTPServer((host, port), Handler)
                break
            except OSError as e:
                last_error = e
        if self._server is None:
            raise last_error
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        self._timer = threading.Timer(seconds, self.stop)
        self._timer.daemon = True
        self._timer.start()
        self.url = "http://%s:%d%s" % (local_ip(), self._server.server_address[1], wanted)
        return self.url

    def stop(self):
        if self._timer:
            self._timer.cancel()
            self._timer = None
        if self._server:
            server, self._server = self._server, None
            server.shutdown()
            server.server_close()
        self.url = None
