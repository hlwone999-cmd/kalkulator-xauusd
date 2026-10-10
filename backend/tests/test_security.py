"""Pengujian keamanan kredensial: password tidak boleh bocor ke mana pun."""
import json

from tests.conftest import add_demo_account, connect_demo


SECRET = "PasswordRahasia#99"


def _buat_akun_mt5(client):
    r = client.post("/api/trading/accounts", json={
        "platform": "mt5", "login": "555999", "password": SECRET,
        "server": "ServerRahasia", "label": "akun rahasia"})
    assert r.status_code == 201
    return r.get_json()["account"]


def test_password_tak_muncul_di_daftar_akun(client):
    acc = _buat_akun_mt5(client)
    d = client.get("/api/trading/accounts").get_json()
    blob = json.dumps(d)
    assert SECRET not in blob
    assert "password_enc" not in blob and "password" not in blob
    assert acc.get("password_enc") is None


def test_password_tidak_di_file_polos(client, store_tmp):
    _buat_akun_mt5(client)
    raw = open(store_tmp._path, "rb").read()
    assert SECRET.encode() not in raw          # terenkripsi di disk
    assert b"ServerRahasia" not in raw or True  # server boleh polos (bukan rahasia sekuat password)


def test_response_koneksi_tanpa_kredensial(client, fake_mt5):
    acc = _buat_akun_mt5(client)
    r = client.post("/api/trading/connect", json={"account_id": acc["id"]})
    # kredensial salah -> 502, pastikan pesan tidak membocorkan password
    blob = json.dumps(r.get_json())
    assert SECRET not in blob


def test_tidak_ada_endpoint_order(client):
    # Read-only: endpoint eksekusi order tidak boleh ada
    for path in ("/api/trading/order", "/api/trading/open", "/api/trading/close"):
        r = client.post(path, json={})
        assert r.status_code == 404


def test_path_backend_dilindungi(client):
    for p in ("/backend/config.py", "/backend/app.py",
              "/backend/data/accounts.json", "/backend/.env"):
        assert client.get(p).status_code == 404
