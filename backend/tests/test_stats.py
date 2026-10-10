"""Pengujian mesin statistik — dataset diketahui, hasil harus persis."""
from services import stats as S


DEALS = [
    # dua menang, satu kalah, satu impas — profit+swap+komisi
    {"close_time": 1000, "profit": 250.0, "swap": 0.0, "commission": 0.0},
    {"close_time": 1100, "profit": -120.0, "swap": 0.5, "commission": -0.7},
    {"close_time": 1200, "profit": 80.0, "swap": 0.0, "commission": -0.5},
    {"close_time": 1300, "profit": 0.0, "swap": 0.0, "commission": 0.0},
]
DEPOSITS = [{"time": 900, "type": "deposit", "amount": 10000.0}]


def test_win_rate_dan_hitungan_dasar():
    s = S.compute_summary(DEALS, DEPOSITS)
    # net per trade: +250, -120+0.5-0.7=-120.2, +80-0.5=79.5, 0
    assert s["total_deals"] == 4
    assert s["wins"] == 2 and s["losses"] == 1 and s["breakeven"] == 1
    assert s["win_rate"] == 66.67          # 2/3 (impas tak masuk penyebut)
    assert s["net_profit"] == 209.3         # 250 - 120.2 + 79.5 + 0


def test_profit_factor_avg():
    s = S.compute_summary(DEALS, DEPOSITS)
    assert s["gross_profit"] == 329.5       # 250 + 79.5 (komisi ikut net)
    assert s["gross_loss"] == 120.2
    assert s["profit_factor"] == round(329.5 / 120.2, 2)
    assert s["avg_win"] == 164.75
    assert s["avg_loss"] == 120.2
    assert s["best_trade"] == 250.0
    assert s["worst_trade"] == -120.2


def test_deposit_withdrawal():
    dep = [{"time": 900, "type": "deposit", "amount": 10000.0},
           {"time": 950, "type": "deposit", "amount": 2000.0},
           {"time": 990, "type": "withdrawal", "amount": -1500.0}]
    s = S.compute_summary(DEALS, dep)
    assert s["total_deposit"] == 12000.0
    assert s["total_withdrawal"] == 1500.0
    assert s["deposits_available"] is True


def test_tanpa_data_deposit():
    s = S.compute_summary(DEALS, [])
    assert s["total_deposit"] is None and s["total_withdrawal"] is None
    assert s["deposits_available"] is False


def test_max_drawdown():
    # kurva: 10000 → +250 (10250) → -120.2 (10129.8) → +79.5 (10209.3) → +0
    # puncak 10250, lembah 10129.8 → dd abs 120.2 → pct 1.17%
    s = S.compute_summary(DEALS, DEPOSITS)
    assert s["max_drawdown_abs"] == 120.2
    assert s["max_drawdown_pct"] == round(120.2 / 10250 * 100, 2)


def test_kurva_ekuitas_urut():
    pts = S.equity_curve(DEALS, DEPOSITS)
    assert pts[0]["balance"] == 10000.0     # titik pertama: deposit awal
    assert pts[-1]["balance"] == 10209.3    # 10000 + 209.3
    assert all(pts[i]["t"] <= pts[i + 1]["t"] for i in range(len(pts) - 1))


def test_filter_periode():
    f = S.filter_by_period(DEALS, 1050, 1250)
    assert len(f) == 2  # hanya close_time 1100 dan 1200


def test_resolve_period():
    now = 1_700_000_000
    a, b = S.resolve_period("7d", now_ts=now)
    assert (b - a) == 7 * 86400
    a, b = S.resolve_period("today", now_ts=now)
    assert b == now and a <= now
    try:
        S.resolve_period("custom", 0, 0, now)
        assert False, "harusnya ValueError"
    except ValueError:
        pass
    try:
        S.resolve_period("mingguan", now_ts=now)
        assert False, "harusnya ValueError"
    except ValueError:
        pass


def test_kas_kosong():
    s = S.compute_summary([], [])
    assert s["win_rate"] is None and s["profit_factor"] is None
    assert s["max_drawdown_pct"] is None and s["total_deals"] == 0


def test_gross_loss_nol():
    deals = [{"close_time": 1, "profit": 50, "swap": 0, "commission": 0}]
    s = S.compute_summary(deals, [])
    assert s["profit_factor"] == "inf"   # untung tanpa rugi
    assert s["win_rate"] == 100.0
