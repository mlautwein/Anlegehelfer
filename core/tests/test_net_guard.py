import socket
import threading

import pytest

from lims_assistant import net_guard


@pytest.fixture(autouse=True)
def _restore_guard():
    yield
    net_guard.uninstall()


def test_externe_verbindung_wird_blockiert():
    net_guard.install()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(net_guard.NetworkBlockedError):
            s.connect(("93.184.216.34", 80))  # externe Adresse
        with pytest.raises(net_guard.NetworkBlockedError):
            socket.create_connection(("example.com", 443), timeout=1)
    finally:
        s.close()


def test_loopback_bleibt_erlaubt():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    accepted = []

    def _accept():
        conn, _ = server.accept()
        accepted.append(conn)

    t = threading.Thread(target=_accept, daemon=True)
    t.start()
    net_guard.install()
    client = socket.create_connection(("127.0.0.1", port), timeout=5)
    t.join(timeout=5)
    assert accepted
    client.close()
    accepted[0].close()
    server.close()


def test_uninstall_stellt_verhalten_wieder_her():
    net_guard.install()
    assert net_guard.is_installed()
    net_guard.uninstall()
    assert not net_guard.is_installed()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.05)
    try:
        # darf jetzt wieder normal fehlschlagen (Timeout), nicht per Guard-Exception
        with pytest.raises(OSError):
            s.connect(("10.255.255.1", 9))
    finally:
        s.close()
