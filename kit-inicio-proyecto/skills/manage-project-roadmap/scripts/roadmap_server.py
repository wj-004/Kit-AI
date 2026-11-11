"""Validated, loopback-only preview; serves snapshots, never arbitrary files."""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from plan_model import IMAGE_TYPES
from roadmap import render, snapshot, write_document
from roadmap_edit import EditConflict, approval_token, persist, proposal


class Monitor:
    def __init__(self, root: Path, plan_dir: Path, output: Path, *, allow_edit: bool = False):
        self.root, self.plan_dir, self.output = root, plan_dir, output
        self.lock = threading.RLock()
        self.attempted = None
        self.graph, self.sources, self.document, self.error = None, {}, b'', ''
        self.allow_edit, self.edit_secret = allow_edit, secrets.token_urlsafe(32)

    def fingerprint(self) -> str:
        digest = hashlib.sha256()
        suffixes = {'.md', *IMAGE_TYPES}
        for path in sorted(path for path in self.plan_dir.rglob('*') if path.suffix.lower() in suffixes and not path.is_dir()):
            if path.is_symlink() or not path.resolve().is_relative_to(self.plan_dir.resolve()):
                raise ValueError('El plan contiene una fuente enlazada fuera de sus archivos.')
            digest.update(path.relative_to(self.plan_dir).as_posix().encode('utf-8') + b'\0' + path.read_bytes() + b'\0')
        config = self.root / '.agents/project.json'
        if config.is_symlink():
            raise ValueError('La configuración no puede ser un enlace simbólico.')
        if config.exists():
            digest.update(config.read_bytes())
        return digest.hexdigest()

    def refresh(self) -> bool:
        with self.lock:
            fingerprint = None
            try:
                fingerprint = self.fingerprint()
                if fingerprint == self.attempted:
                    return False
                graph, sources = snapshot(self.root, self.plan_dir, self.output)
                if self.fingerprint() != fingerprint:
                    return False
                for task in graph['tasks']:
                    task['sourceUrl'] = '__roadmap__/source/' + quote(task['source'], safe='/')
                graph.update(revision=fingerprint,
                             live={'statusUrl': '__roadmap__/status', 'dataUrl': '__roadmap__/data',
                                   'intervalMs': 1000, 'allowEdit': self.allow_edit})
                document = render(graph)
                write_document(self.output, document)
                self.graph, self.sources, self.document = graph, sources, document.encode('utf-8')
                self.attempted, self.error = fingerprint, ''
                return True
            except (OSError, ValueError) as error:
                self.error = str(error)
                if isinstance(error, ValueError) and fingerprint is not None:
                    self.attempted = fingerprint
                return False

    def status(self) -> dict:
        with self.lock:
            return {'projectId': (self.graph or {}).get('projectId'),
                    'projectName': (self.graph or {}).get('projectName'),
                    'revision': (self.graph or {}).get('revision'),
                    'generatedAt': (self.graph or {}).get('generatedAt'),
                    'status': 'invalid' if self.error else 'ok', 'error': self.error}


class RoadmapHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = not hasattr(socket, 'SO_EXCLUSIVEADDRUSE')

    def server_bind(self) -> None:
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def create_server(monitor: Monitor, port: int = 8788) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def trusted_host(self) -> bool:
            allowed_hosts = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
            if self.headers.get('Host') not in allowed_hosts:
                self.send_error(403)
                return False
            return True

        def do_GET(self):
            if not self.trusted_host():
                return
            route = unquote(urlsplit(self.path).path)
            with monitor.lock:
                if route in {'/', '/' + monitor.output.name}:
                    self.send_payload(monitor.document, 'text/html')
                elif route == '/__roadmap__/status':
                    self.send_payload(json.dumps(monitor.status(), ensure_ascii=False).encode(), 'application/json')
                elif route == '/__roadmap__/data':
                    self.send_payload(json.dumps(monitor.graph, ensure_ascii=False).encode(), 'application/json')
                elif route == '/__roadmap__/session' and monitor.allow_edit:
                    if (self.headers.get('Sec-Fetch-Site') == 'cross-site' or
                            self.headers.get('Origin', 'http://' + self.headers['Host']) != 'http://' + self.headers['Host']):
                        self.send_error(403)
                        return
                    self.send_json({'projectId': monitor.graph['projectId'], 'token': monitor.edit_secret})
                elif route.startswith('/__roadmap__/source/') and route[len('/__roadmap__/source/'):] in monitor.sources:
                    self.send_payload(monitor.sources[route[len('/__roadmap__/source/'):]].encode(), 'text/plain')
                else:
                    self.send_error(404)

        def do_POST(self):
            if not self.trusted_host():
                return
            if (not monitor.allow_edit or self.headers.get('Origin') != 'http://' + self.headers['Host']
                    or not hmac.compare_digest(self.headers.get('X-Roadmap-Token', ''), monitor.edit_secret)):
                self.send_json({'error': 'Edición no autorizada. Usá el servidor local con --allow-edit.'}, 403)
                return
            route = urlsplit(self.path).path
            if route not in {'/__roadmap__/edit/preview', '/__roadmap__/edit/save'}:
                self.send_json({'error': 'Operación desconocida.'}, 404)
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if self.headers.get('Transfer-Encoding') or not 0 < length <= 262144:
                    self.send_json({'error': 'La propuesta debe ocupar como máximo 256 KiB.'}, 413)
                    return
                if self.headers.get_content_type() != 'application/json':
                    self.send_json({'error': 'Se requiere application/json.'}, 415)
                    return
                self.connection.settimeout(5)
                payload = json.loads(self.rfile.read(length).decode('utf-8'))
                with monitor.lock:
                    if not isinstance(payload, dict):
                        raise ValueError('La solicitud debe ser un objeto JSON.')
                    authorized = payload.pop('authorized', False)
                    approval = payload.pop('approval', '')
                    reviewed = proposal(monitor, payload)
                    expected = approval_token(monitor.edit_secret, payload, reviewed)
                    if route.endswith('/preview'):
                        self.send_json({'diff': reviewed['diff'], 'branch': reviewed['branch'], 'approval': expected,
                                        'source': reviewed['source'], 'revision': reviewed['revision']})
                        return
                    if authorized is not True or not isinstance(approval, str) or not hmac.compare_digest(approval, expected):
                        self.send_json({'error': 'Revisá la vista previa y autorizá expresamente este cambio antes de guardar.'}, 403)
                        return
                    persist(monitor, reviewed)
                    monitor.refresh()
                    self.send_json({'saved': True, 'source': reviewed['source'], 'branch': reviewed['branch'],
                                    'revision': monitor.graph['revision'], 'error': monitor.error,
                                    'message': 'Cambio local guardado. Revisá git diff y abrí una Pull Request hacia main.'})
            except EditConflict as error:
                self.send_json({'error': str(error)}, 409)
            except (ValueError, UnicodeError, OSError) as error:
                self.send_json({'error': str(error)}, 422)

        def send_json(self, payload: dict, status: int = 200):
            self.send_payload(json.dumps(payload, ensure_ascii=False).encode('utf-8'), 'application/json', status)

        def send_payload(self, payload: bytes, content_type: str, status: int = 200):
            self.send_response(status)
            self.send_header('Content-Type', content_type + '; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format, *args):
            pass

    return RoadmapHTTPServer(('127.0.0.1', port), Handler)


def serve(root: Path, plan_dir: Path, output: Path, port: int, interval: float, *, allow_edit: bool = False) -> int:
    monitor = Monitor(root, plan_dir, output, allow_edit=allow_edit)
    server = create_server(monitor, port)
    if not monitor.refresh():
        server.server_close()
        raise ValueError(monitor.error or 'El plan cambió durante la lectura; reintentar con las fuentes estables.')
    stopped = threading.Event()

    def watch():
        while not stopped.wait(interval):
            monitor.refresh()

    worker = threading.Thread(target=watch, name='roadmap-watch', daemon=True)
    worker.start()
    print(f"{monitor.graph['projectName']} — proyecto {monitor.graph['projectId']}\n"
          f'http://127.0.0.1:{server.server_port}/{output.name}\nCtrl+C para detener.', flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        stopped.set()
        server.server_close()
        worker.join(timeout=2)
    return 0
