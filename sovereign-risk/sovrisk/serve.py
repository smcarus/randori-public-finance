"""Serve the dashboard on your own machine so it can pull a country's data live from the providers' APIs.

    python -m sovrisk.serve                 # http://localhost:8080
    python -m sovrisk.serve --port 8090

Pick a country in the dashboard's Live country data tab and the server calls sovrisk.live.country_profile(), which
asks the IMF, World Bank, BIS and Yahoo Finance for that country, then rates it on the early-warning panel. The
server listens on 127.0.0.1 only, so nothing outside your machine can use it. Routes:

    /                       the dashboard, built once at start (restart the server after changing data/)
    /api/countries          [{iso3, iso2, name}] from data/country_codes.csv, else the World Bank country list
    /api/country/<ISO3>     the live pull; query ?y0=2000&y1=2026&fx=ARS&refresh=1 (cached for the session
                            and saved to outputs/live/<ISO3>.json)
"""
import argparse
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import live
from .config import ROOT


class App:
    def __init__(self, root=ROOT, page=None):
        self.root = Path(root)
        self._page, self._codes, self._cache, self._lock = page, None, {}, threading.Lock()

    def page(self):
        if self._page is None:
            from .config import load_config
            from .dashboard import dashboard_data, render
            self._page = render(dashboard_data(load_config(self.root), self.root))
        return self._page

    def codes(self):
        if self._codes is None:
            self._codes = live.country_codes(self.root)
        return self._codes

    def countries(self):
        return [{'iso3': k, **v} for k, v in sorted(self.codes().items(), key=lambda kv: kv[1]['name'])]

    def country(self, iso3, y0=2000, y1=None, fx=None, refresh=False):
        key = (iso3, y0, y1, fx)
        with self._lock:
            if not refresh and key in self._cache:
                return self._cache[key]
        try:
            iso2 = self.codes().get(iso3, {}).get('iso2')
        except Exception:   # the country list could not be read or fetched: the BIS feed will say so
            iso2 = None
        p = live.country_profile(iso3, y0, y1, fx, iso2)
        try:
            p['name'] = self.codes().get(iso3, {}).get('name', iso3)
        except Exception:
            p['name'] = iso3
        live.save(p, self.root)
        with self._lock:
            self._cache[key] = p
        return p


def handler(app):
    class H(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype='application/json'):
            data = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header('Content-Type', ctype + '; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)

        def _json(self, code, obj):
            self._send(code, json.dumps(obj, default=str))

        def do_GET(self):
            u = urlparse(self.path)
            q = {k: v[-1] for k, v in parse_qs(u.query).items()}
            try:
                if u.path in ('/', '/dashboard.html', '/index.html'):
                    return self._send(200, app.page(), 'text/html')
                if u.path == '/api/countries':
                    return self._json(200, app.countries())
                m = re.fullmatch(r'/api/country/([A-Za-z]{3})', u.path)
                if m:
                    y0 = int(q.get('y0') or 2000)
                    y1 = int(q['y1']) if q.get('y1') else None
                    fx = q.get('fx') or None
                    if fx and not re.fullmatch(r'[A-Za-z]{3}', fx):
                        return self._json(400, {'error': 'fx must be a three-letter currency code, e.g. ARS'})
                    return self._json(200, app.country(m.group(1).upper(), y0, y1, fx and fx.upper(), q.get('refresh') == '1'))
                return self._json(404, {'error': f'no route {u.path}'})
            except Exception as e:
                return self._json(500, {'error': f'{type(e).__name__}: {e}'})

        def log_message(self, fmt, *args):
            print('serve:', fmt % args)
    return H


def main(argv=None):
    ap = argparse.ArgumentParser(description='Serve the dashboard locally with live country data pulls.')
    ap.add_argument('--port', type=int, default=8080)
    ap.add_argument('--root', default=None, help='repository root holding rulebook/ and data/')
    a = ap.parse_args(argv)
    app = App(Path(a.root) if a.root else ROOT)
    print('Building the dashboard...')
    app.page()
    srv = ThreadingHTTPServer(('127.0.0.1', a.port), handler(app))
    print(f'Dashboard at http://localhost:{a.port}  (Ctrl+C to stop)')
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
