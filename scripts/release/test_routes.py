"""Serve exported files with ordinary HTTP; no SPA fallback can hide broken routes."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from urllib.request import urlopen
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parents[2]
class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*args):
        pass

if __name__=='__main__':
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(ROOT/'showcase/out')))
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    try:
        for route in ['', 'inflation','labor','yield-curve','workspace','analytics','fed','sources','about','business-cycle']:
            for suffix in ['/', '/index.html'] if route else ['/']:
                with urlopen(f'http://127.0.0.1:{server.server_port}/{route}{suffix}'.replace('//index','/index')) as r:
                    assert r.status==200 and b'Static Showcase' in r.read()
        for asset in ['data/snapshot.json','data/licenses.json','data/snapshot.schema.json','data/third-party-notices.txt','_headers']:
            with urlopen(f'http://127.0.0.1:{server.server_port}/{asset}') as r:
                assert r.status==200
        try:
            urlopen(f'http://127.0.0.1:{server.server_port}/unknown-route/')
            raise AssertionError('Unknown route should not succeed')
        except HTTPError as error:
            assert error.code==404
        print('PASS: 10 routes, direct deep-link refresh, 5 static resources and unknown-route 404 over HTTP.')
    finally:
        server.shutdown();server.server_close();worker.join()
