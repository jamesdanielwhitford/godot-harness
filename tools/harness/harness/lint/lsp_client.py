"""Minimal JSON-RPC over TCP client for Godot's GDScript language server (port of research/scripts/r1_1_cli/lsp_probe.py,
with the S5 didOpen/timeout loop; spec 2.2)."""
from __future__ import annotations

import json
import socket
import time
from pathlib import Path
from urllib.parse import quote


class Conn:
    def __init__(self, port: int, timeout: float = 5.0):
        self.s = socket.create_connection(("127.0.0.1", port), timeout=timeout)
        self.buf = b""

    def close(self):
        try:
            self.s.close()
        except OSError:
            pass

    def send(self, obj: dict):
        b = json.dumps(obj).encode()
        self.s.sendall(b"Content-Length: %d\r\n\r\n" % len(b) + b)

    def recv(self, deadline: float):
        """Next message or None when the deadline passes."""
        while True:
            i = self.buf.find(b"\r\n\r\n")
            if i >= 0:
                n = None
                for ln in self.buf[:i].split(b"\r\n"):
                    if ln.lower().startswith(b"content-length"):
                        n = int(ln.split(b":")[1])
                if n is not None and len(self.buf) >= i + 4 + n:
                    m = self.buf[i + 4: i + 4 + n]
                    self.buf = self.buf[i + 4 + n:]
                    try:
                        return json.loads(m)
                    except ValueError:
                        continue
            left = deadline - time.monotonic()
            if left <= 0:
                return None
            self.s.settimeout(left)
            try:
                chunk = self.s.recv(65536)
            except (socket.timeout, TimeoutError):
                return None
            if not chunk:
                return None
            self.buf += chunk


def file_uri(path: Path) -> str:
    return "file://" + quote(str(path))


def initialize(c: Conn, project: Path, timeout: float = 5.0) -> bool:
    c.send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"processId": None, "rootUri": file_uri(project), "capabilities": {}}})
    deadline = time.monotonic() + timeout
    while True:
        m = c.recv(deadline)
        if m is None:
            return False
        if m.get("id") == 1:
            c.send({"jsonrpc": "2.0", "method": "initialized", "params": {}})
            return True


def ready(port: int, project: Path, timeout: float = 1.0) -> bool:
    try:
        c = Conn(port, timeout)
    except OSError:
        return False
    try:
        return initialize(c, project, timeout)
    except OSError:
        return False
    finally:
        c.close()


def diagnose(port: int, project: Path, file: Path, res: str, wait: float = 5.0) -> list:
    """-> [{"kind": "diag", line, severity, message}] or [{"kind": "timeout"}]."""
    try:
        text = file.read_bytes().decode("utf-8", "replace")
    except OSError:
        return []
    uri = file_uri(file)
    try:
        c = Conn(port, wait)
    except OSError:
        return [{"kind": "timeout"}]
    try:
        if not initialize(c, project, wait):
            return [{"kind": "timeout"}]
        c.send({"jsonrpc": "2.0", "method": "textDocument/didOpen",
                "params": {"textDocument": {"uri": uri, "languageId": "gdscript", "version": 1, "text": text}}})
        deadline = time.monotonic() + wait
        while True:
            m = c.recv(deadline)
            if m is None:
                return [{"kind": "timeout"}]
            if m.get("method") == "textDocument/publishDiagnostics":
                p = m.get("params", {})
                if p.get("uri") not in (uri, uri.replace("%2F", "/")) and Path(p.get("uri", "").replace("file://", "")).name != file.name:
                    continue
                out = []
                for d in p.get("diagnostics", []):
                    out.append({"kind": "diag", "line": int(d.get("range", {}).get("start", {}).get("line", 0)) + 1,
                                "severity": d.get("severity", 1), "message": str(d.get("message", "")).replace("\n", " ")})
                try:
                    c.send({"jsonrpc": "2.0", "method": "textDocument/didClose",
                            "params": {"textDocument": {"uri": uri}}})
                except OSError:
                    pass
                return out
    except OSError:
        return [{"kind": "timeout"}]
    finally:
        c.close()
