"""Pengujian API: alur utama, multi-akun, periode, error, dan keamanan kredensial."""
import time

from tests.conftest import add_demo_account, connect_demo


# ----------------------------------------------------------- health & auth
def test_health(client):
    r = client.get("/api/trading/health")
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True and "connectors" in d


def test_auth_token(monkeypatch, store_tmp, client):
    import app as app_mod
    monkeypatch.setattr(app_mod.config, "API_TOKEN", "rahasia123")
    r = client.get("/api/trading/accounts")
    assert r.status_code == 401
    r = client.get("/api/trading/accounts",
                   headers={"Authorization": "Bearer salah"})
    assert r.status_code == 401
    r = client.get("/api/trading/accounts",
                   headers={"Authorization": "Bearer rahasia123"})
    assert r.status_code == 200


# ----------------------------------------------------------- akun & koneksi
def test_validasi_akun(client):
    r = client.post("/api/trading/accounts", json={"platform": "binance"})
    assert r.status_code == 400
    r = client.post("/api/trading/accounts", json={"platform": "mt5",
                                                   "login": "abc"})
    assert r.status_code == 400
    r = client.post("/api/trading/accounts", json={
        "platform": "mt5", "login": "123", "password": "x"})
    assert r.status_code == 400  # server kosong


def test_koneksi_demo_dan_status(client):
    acc = connect_demo(client, "demo-status")
    r = client.get("/api/trading/status")
    d = r.get_json()
    assert d["connected"] is True and d["mode"] == "demo"
    assert d["account"]["balance"] > 0
    assert d["account"]["broker"].startswith("DEMO")


def test_connect_akun_tidak_ada(client):
    r = client.post("/api/trading/connect", json={"account_id": "tidakada"})
    assert r.status_code == 404


def test_mt5_kredensial_salah(client, fake_mt5, store_tmp):
    r = client.post("/api/trading/accounts", json={
        "platform": "mt5", "login": "123456", "password": "salah",
        "server": "Demo-Uji"})
    assert r.status_code == 201
    acc_id = r.get_json()["account"]["id"]
    r = client.post("/api/trading/connect", json={"account_id": acc_id})
    assert r.status_code == 502
    msg = r.get_json()["error"]["message"]
    assert "MT5" in msg and "login" in msg.lower()


def test_mt5_kredensial_benar(client, fake_mt5, store_tmp):
    r = client.post("/api/trading/accounts", json={
        "platform": "mt5", "login": "123456", "password": "benar",
        "server": "Demo-Uji"})
    acc_id = r.get_json()["account"]["id"]
    r = client.post("/api/trading/connect", json={"account_id": acc_id})
    assert r.status_code == 200
    info = r.get_json()["account"]
    assert info["broker"] == "Broker Uji" and info["currency"] == "USD"
    # summary dari fake deals
    r = client.get("/api/trading/summary?period=all")
    d = r.get_json()
    assert d["total_deals"] == 3 and d["wins"] == 1 and d["losses"] == 1
    assert d["breakeven"] == 1
    assert d["total_deposit"] == 5000.0  # deal balance dari fake


def test_mt4_bridge_uji(client, fake_mt4_socket, store_tmp):
    r = client.post("/api/trading/accounts", json={
        "platform": "mt4", "login": "123456", "password": "x",
        "server": "Demo-Uji", "bridge_host": "127.0.0.1",
        "bridge_port": "2345"})
    acc_id = r.get_json()["account"]["id"]
    r = client.post("/api/trading/connect", json={"account_id": acc_id})
    assert r.status_code == 200
    info = r.get_json()["account"]
    assert info["login"] == "123456" and info["broker"] == "Broker Uji"
    r = client.get("/api/trading/history?period=all")
    d = r.get_json()
    assert d["total"] == 2
    profits = [x["profit"] for x in d["deals"]]
    assert 250.0 in profits and -120.0 in profits


def test_mt4_bridge_tidak_aktif(client, store_tmp):
    r = client.post("/api/trading/accounts", json={
        "platform": "mt4", "login": "1", "password": "x", "server": "s",
        "bridge_host": "10.255.255.1", "bridge_port": "2345"})
    acc_id = r.get_json()["account"]["id"]
    r = client.post("/api/trading/connect", json={"account_id": acc_id})
    assert r.status_code == 502
    assert "bridge" in r.get_json()["error"]["message"].lower()


# ----------------------------------------------------------- multi-akun
def test_multi_akun_tidak_tercampur(client, store_tmp):
    a1 = connect_demo(client, "seed-satu")
    s1 = client.get("/api/trading/summary?period=all").get_json()
    client.post("/api/trading/accounts", json={"platform": "demo",
                                               "login": "seed-dua"})
    accs = client.get("/api/trading/accounts").get_json()
    acc2 = [a for a in accs["accounts"] if a["login"] == "seed-dua"][0]
    client.post("/api/trading/connect", json={"account_id": acc2["id"]})
    s2 = client.get("/api/trading/summary?period=all").get_json()
    # seed berbeda -> data berbeda, tidak boleh sama
    assert s1["balance"] != s2["balance"] or s1["total_deals"] != s2["total_deals"]


def test_hapus_akun_mengubah_active(client, store_tmp):
    a1 = connect_demo(client, "hapus-1")
    add_demo_account(client, "hapus-2")
    r = client.delete(f"/api/trading/accounts/{a1['id']}")
    assert r.status_code == 200
    accs = client.get("/api/trading/accounts").get_json()
    assert accs["active"] != a1["id"]


# ----------------------------------------------------------- periode & batas
def test_periode_invalid(client, store_tmp):
    connect_demo(client, "periode")
    r = client.get("/api/trading/summary?period=mingguan")
    assert r.status_code == 400
    r = client.get("/api/trading/summary?period=custom")
    assert r.status_code == 400
    r = client.get("/api/trading/summary?period=custom&from=1700000000&to=1690000000")
    assert r.status_code == 400


def test_history_offset(client, store_tmp):
    connect_demo(client, "offset")
    r = client.get("/api/trading/history?period=all&limit=5&offset=0")
    d = r.get_json()
    assert d["total"] >= 100 and len(d["deals"]) == 5
    r2 = client.get("/api/trading/history?period=all&limit=5&offset=5")
    assert r2.get_json()["deals"] != d["deals"]


def test_belum_terhubung(client, store_tmp):
    add_demo_account(client, "belum")
    r = client.get("/api/trading/summary?period=all")
    assert r.status_code == 502
    assert "Hubungkan" in r.get_json()["error"]["message"]


def test_aksesar_backend_terlarang(client):
    assert client.get("/backend/app.py").status_code == 404
    assert client.get("/backend/data/accounts.json").status_code == 404
    assert client.get("/script.js").status_code == 200
    assert client.get("/trading.html").status_code == 200
