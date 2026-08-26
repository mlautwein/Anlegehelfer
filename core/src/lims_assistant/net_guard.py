"""Offline-Waechter: blockiert unerwartete Netzwerkzugriffe zur Laufzeit.

Der Produktivbetrieb ist vollstaendig lokal. Einzige zulaessige Verbindung ist
Loopback (llama.cpp-Server auf 127.0.0.1). Der Waechter wird im CLI-Einstieg
installiert (offline_strict=true) und macht jeden anderen Verbindungsaufbau zu
einem harten Fehler - testbar und nachweisbar.
"""

from __future__ import annotations

import socket

_LOOPBACK = {"127.0.0.1", "::1", "localhost"}
_installed = False
_orig_connect = socket.socket.connect
_orig_connect_ex = socket.socket.connect_ex
_orig_create_connection = socket.create_connection


class NetworkBlockedError(RuntimeError):
    pass


def _check(address) -> None:
    host = None
    if isinstance(address, tuple) and address:
        host = str(address[0])
    elif isinstance(address, (str, bytes)):
        # AF_UNIX ist lokal und zulaessig.
        return
    if host is None:
        return
    if host in _LOOPBACK or host.startswith("127."):
        return
    raise NetworkBlockedError(
        f"Netzwerkzugriff blockiert (offline-Modus): {host!r}"
    )


def install() -> None:
    global _installed
    if _installed:
        return

    def guarded_connect(self, address):  # type: ignore[no-untyped-def]
        _check(address)
        return _orig_connect(self, address)

    def guarded_connect_ex(self, address):  # type: ignore[no-untyped-def]
        _check(address)
        return _orig_connect_ex(self, address)

    def guarded_create_connection(address, *args, **kwargs):  # type: ignore[no-untyped-def]
        _check(address)
        return _orig_create_connection(address, *args, **kwargs)

    socket.socket.connect = guarded_connect  # type: ignore[assignment]
    socket.socket.connect_ex = guarded_connect_ex  # type: ignore[assignment]
    socket.create_connection = guarded_create_connection  # type: ignore[assignment]
    _installed = True


def uninstall() -> None:
    global _installed
    socket.socket.connect = _orig_connect  # type: ignore[assignment]
    socket.socket.connect_ex = _orig_connect_ex  # type: ignore[assignment]
    socket.create_connection = _orig_create_connection  # type: ignore[assignment]
    _installed = False


def is_installed() -> bool:
    return _installed
