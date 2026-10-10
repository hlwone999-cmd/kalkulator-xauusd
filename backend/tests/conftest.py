"""Fixture pengujian: fake modul MetaTrader5, fake socket MT4, app + store sementara."""
import sys
import types
import time
import pytest

from services.store import AccountStore


# ---------------------------------------------------------------- fakes
class _FakeMT5:
    """Peniru paket MetaTrader5 untuk pengujian di Linux."""
    DEAL_ENTRY_OUT = 1
    DEAL_ENTRY_IN = 0
    DEAL_TYPE_BUY = 0
    DEAL_TYPE_SELL = 1
    DEAL_TYPE_BALANCE = 2
    POSITION_TYPE_BUY = 0

    last_error_code = 0

    def __init__(self):
        self._connected = False

    def initialize(self, **kw):
        if kw.get("password") == "benar":
            self._connected = True
            return True
        self.last_error_code = 10004
        return False

    def shutdown(self):
        self._connected = False

    def last_error(self):
        return (self.last_error_code, "auth failed")

    def account_info(self):
        if not self._connected:
            return None
        t = types.SimpleNamespace(
            login=123456, name="Trader Uji", company="Broker Uji",
            server="Demo-Uji", currency="USD", balance=10000.0,
            equity=10150.0, leverage=500)
        return t

    @staticmethod
    def _deal(entry, dtype, profit, t, symbol="XAUUSD", price=2400.0,
              volume=0.1, swap=0.5, commission=-0.7):
        return types.SimpleNamespace(
            entry=entry, type=dtype, profit=profit, time=t, symbol=symbol,
            price=price, volume=volume, swap=swap, commission=commission,
            position_id=ticket_of(t), ticket=t)

    def history_deals_get(self, since, until):
        now = int(until) - 30
        return [
            self._deal(self.DEAL_ENTRY_OUT, self.DEAL_TYPE_BUY, 250.0, now),
            self._deal(self.DEAL_ENTRY_OUT, self.DEAL_TYPE_SELL, -120.0, now + 10),
            self._deal(self.DEAL_ENTRY_OUT, self.DEAL_TYPE_BUY, 0.0, now + 20,
                       swap=0.0, commission=0.0),  # impas bersih
            self._deal(self.DEAL_ENTRY_IN, self.DEAL_TYPE_BUY, 0.0, now + 5),  # entry: bukan trade tertutup
            self._deal(self.DEAL_ENTRY_OUT, self.DEAL_TYPE_BALANCE, 5000.0, now - 100),  # deposit
        ]

    def positions_get(self):
        if not self._connected:
            return None
        return [types.SimpleNamespace(
            ticket=99, symbol="XAUUSD", type=self.POSITION_TYPE_BUY,
            volume=0.2, time=int(time.time()) - 3600, price_open=2380.0,
            price_current=2410.0, profit=60.0, swap=-0.2)]


def ticket_of(t):
    return int(t) % 100000


class _FakeSocketMT4:
    """Peniru socket bridge EA PyTrader — membalas format '^' dan '$'."""
    def __init__(self):
        self.sent = []

    def create_connection(self, address, timeout=0):
        host, port = address
        if host == "127.0.0.1" and port == 2345:
            return self
        raise OSError("refused")

    def sendall(self, payload):
        self.sent.append(payload)

    def recv(self, n):
        sent = (self.sent[-1].decode() if isinstance(self.sent[-1], bytes)
                else str(self.sent[-1])) if self.sent else ""
        if sent.startswith("F001"):
            return ("F001^1^Trader Uji$123456$USD$demo$500$True$100$50$50$"
                    "Broker Uji^!").encode()
        if sent.startswith("F002"):
            return ("F002^1^10000.0$10150.0$60.0$0$0$10000^!").encode()
        if sent.startswith("F061"):
            return ("F061^1^99$XAUUSD$88$0$0$0.2$2380.0$1700000000$0$0$"
                    "komentar$60.0$-0.2$-0.5^!").encode()
        if sent.startswith("F062"):
            t1, t2 = 1700000100, 1700000200
            return (f"F062^1^101$XAUUSD$88$0$0$0.1$2350.0${t1}$0$0$2360.0${t2}$"
                    f"c$250.0$0.5$-0.7^102$XAUUSD$89$1$0$0.1$2350.0${t1}$0$0$"
                    f"2340.0${t2}$c$-120.0$0.5$-0.7^!").encode()
        return b"?"

    def close(self):
        pass


@pytest.fixture()
def fake_mt5(monkeypatch):
    mod = types.ModuleType("MetaTrader5")
    fake = _FakeMT5()
    mod.initialize = fake.initialize
    mod.shutdown = fake.shutdown
    mod.last_error = fake.last_error
    mod.account_info = fake.account_info
    mod.history_deals_get = fake.history_deals_get
    mod.positions_get = fake.positions_get
    mod.DEAL_ENTRY_OUT = _FakeMT5.DEAL_ENTRY_OUT
    mod.DEAL_ENTRY_IN = _FakeMT5.DEAL_ENTRY_IN
    mod.DEAL_TYPE_BUY = _FakeMT5.DEAL_TYPE_BUY
    mod.DEAL_TYPE_SELL = _FakeMT5.DEAL_TYPE_SELL
    mod.DEAL_TYPE_BALANCE = _FakeMT5.DEAL_TYPE_BALANCE
    mod.POSITION_TYPE_BUY = _FakeMT5.POSITION_TYPE_BUY
    monkeypatch.setitem(sys.modules, "MetaTrader5", mod)
    return fake


@pytest.fixture()
def fake_mt4_socket(monkeypatch):
    import connectors.mt4_pytrader as m4
    fake = _FakeSocketMT4()
    monkeypatch.setattr(m4.socket, "create_connection",
                        fake.create_connection, raising=True)
    return fake


@pytest.fixture()
def store_tmp(tmp_path):
    return AccountStore(path=tmp_path / "accounts.json",
                        secret_key="MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")


@pytest.fixture()
def client(store_tmp, monkeypatch):
    import config
    import app as app_mod
    monkeypatch.setattr(app_mod, "store", store_tmp)
    app_mod._connectors.clear()
    app_mod.app.config["TESTING"] = True
    with app_mod.app.test_client() as c:
        yield c


def add_demo_account(client, seed="demo-uji"):
    r = client.post("/api/trading/accounts", json={"platform": "demo",
                                                   "login": seed})
    assert r.status_code == 201
    return r.get_json()["account"]


def connect_demo(client, seed="demo-uji"):
    acc = add_demo_account(client, seed)
    r = client.post("/api/trading/connect", json={"account_id": acc["id"]})
    assert r.status_code == 200, r.get_json()
    return acc
