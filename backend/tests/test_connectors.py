"""Pengujian konektor: demo deterministik, MT5 adapter (fake), MT4 protokol."""
import time

from connectors.demo import DemoConnector
from connectors.mt4_pytrader import MT4PyTraderConnector
from connectors.base import ConnectorError


# ------------------------------------------------------------- demo
def test_demo_deterministik():
    a = DemoConnector(seed="x").connect()
    b = DemoConnector(seed="x").connect()
    assert a["balance"] == b["balance"]
    c = DemoConnector(seed="y").connect()
    assert a["balance"] != c["balance"]


def test_demo_terlabel():
    info = DemoConnector("x").connect()
    assert "DEMO" in info["broker"]
    assert DemoConnector.mode == "demo"


def test_demo_statistik_tidak_negatif_deposit():
    conn = DemoConnector("x")
    conn.connect()
    s_before = conn._info["balance"]
    assert s_before > 0


# ------------------------------------------------------------- MT5
def test_mt5_tanpa_paket_memberi_pesan_jelas(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "MetaTrader5", None)  # import gagal? None tak cukup
    # hapus agar ImportError benar-benar terjadi
    monkeypatch.delitem(sys.modules, "MetaTrader5", raising=False)
    import builtins
    real_import = builtins.__import__

    def blocked(name, *a, **k):
        if name == "MetaTrader5":
            raise ImportError("No module named 'MetaTrader5'")
        return real_import(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", blocked)

    from connectors.mt5_api import MT5Connector, ConnectorUnavailable
    conn = MT5Connector(login=1, password="p", server="s")
    try:
        conn.connect()
        assert False, "harusnya ConnectorUnavailable"
    except ConnectorUnavailable as e:
        assert "Windows" in str(e)


def test_mt5_alur_normal(fake_mt5):
    from connectors.mt5_api import MT5Connector
    conn = MT5Connector(login=123456, password="benar", server="Demo-Uji")
    info = conn.connect()
    assert info["broker"] == "Broker Uji" and info["platform"] == "mt5"
    deals = conn.closed_positions(0, int(time.time()) + 60)
    assert len(deals) == 3  # entry IN & balance dikecualikan dari trades
    ops = conn.balance_operations(0, int(time.time()) + 60)
    assert any(o["type"] == "deposit" for o in ops)
    snap = conn.snapshot()
    assert snap["floating"] == 59.8  # 60 - 0.2 + 0
    conn.disconnect()
    assert not conn.is_connected()


# ------------------------------------------------------------- MT4 protokol
def test_mt4_protokol_parse(fake_mt4_socket):
    conn = MT4PyTraderConnector(server_host="127.0.0.1", port=2345)
    info = conn.connect()
    assert info["login"] == "123456"
    assert info["broker"] == "Broker Uji"
    deals = conn.closed_positions(0, int(time.time()) + 60)
    assert deals[0]["type"] == "buy" and deals[1]["type"] == "sell"
    assert deals[0]["profit"] == 250.0 and deals[1]["profit"] == -120.0
    pos = conn.open_positions()
    assert pos[0]["ticket"] == 99 and pos[0]["volume"] == 0.2
    assert conn.balance_operations(0, 1) == []  # protokol tak menyediakan


def test_mt4_host_kosong_ditolak():
    try:
        MT4PyTraderConnector(server_host="")
        assert False
    except ConnectorError as e:
        assert "bridge" in str(e).lower()


def test_mt4_host_mati(fake_mt4_socket):
    conn = MT4PyTraderConnector(server_host="10.0.0.99", port=1)
    try:
        conn.connect()
        assert False
    except ConnectorError as e:
        assert "bridge" in str(e).lower()
