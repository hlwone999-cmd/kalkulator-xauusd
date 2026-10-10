"""Mesin statistik trading (gaya Myfxbook) dari posisi tertutup ternormalisasi.

Definisi metrik (dipakai konsisten frontend & backend):
- trade        : posisi tertutup (deal OUT). Deposit/withdrawal BUKAN trade.
- menang       : profit bersih > 0;  kalah: < 0;  impas: == 0
- win rate     : menang / (menang + kalah)  — trade impas tidak masuk penyebut
- profit factor: jumlah profit bersih positif / abs(jumlah profit bersih negatif)
- avg win/loss : rata-rata profit bersih per menang/kalah
- max drawdown : dihitung pada kurva balance dari deposit awal periode +
                 akumulasi hasil tiap posisi tertutup (bukan tick-per-tick),
                 relatif terhadap puncak tertinggi sebelumnya.
Keterbatasan (jujur, dijelaskan ke pengguna):
- MT4 bridge (PyTrader) tidak mengekspor deposit -> total deposit = null.
- Drawdown berbasis kurva trade-tertutup; drawdown intratrade (floating)
  tidak terdeteksi.
- Waktu memakai waktu server broker; komisi/swap ikut dihitung ke profit bersih.
"""
from __future__ import annotations

from typing import Optional


def _net(p: dict) -> float:
    return float(p.get("profit", 0)) + float(p.get("swap", 0)) \
        + float(p.get("commission", 0))


def filter_by_period(deals: list[dict], since_ts: int, until_ts: int) -> list[dict]:
    return [d for d in deals
            if d.get("close_time") is not None
            and since_ts <= d["close_time"] <= until_ts]


def compute_summary(deals: list[dict], deposits: Optional[list[dict]] = None,
                    floating: float = 0.0, balance: Optional[float] = None,
                    equity: Optional[float] = None) -> dict:
    deposits = deposits or []
    nets = [_net(d) for d in deals]
    wins = [n for n in nets if n > 0]
    losses = [n for n in nets if n < 0]
    be = len(nets) - len(wins) - len(losses)
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    denom = len(wins) + len(losses)

    total_deposit = sum(o["amount"] for o in deposits if o["amount"] > 0) \
        if deposits else None
    total_withdrawal = abs(sum(o["amount"] for o in deposits
                               if o["amount"] < 0)) if deposits else None

    curve, max_dd_pct, max_dd_abs = _equity_and_drawdown(deals, deposits)

    return {
        "balance": balance,
        "equity": equity,
        "floating": round(floating, 2),
        "total_deals": len(deals),
        "wins": len(wins),
        "losses": len(losses),
        "breakeven": be,
        "win_rate": round(len(wins) / denom * 100, 2) if denom else None,
        "gross_profit": round(gross_win, 2),
        "gross_loss": round(gross_loss, 2),
        "net_profit": round(gross_win - gross_loss, 2),
        "avg_win": round(gross_win / len(wins), 2) if wins else None,
        "avg_loss": round(gross_loss / len(losses), 2) if losses else None,
        "profit_factor": (round(gross_win / gross_loss, 2)
                          if gross_loss > 0
                          else (None if gross_win == 0 else "inf")),
        "total_deposit": round(total_deposit, 2) if total_deposit is not None else None,
        "total_withdrawal": round(total_withdrawal, 2) if total_withdrawal is not None else None,
        "max_drawdown_pct": round(max_dd_pct, 2) if max_dd_pct is not None else None,
        "max_drawdown_abs": round(max_dd_abs, 2) if max_dd_abs is not None else None,
        "best_trade": round(max(nets), 2) if nets else None,
        "worst_trade": round(min(nets), 2) if nets else None,
        "deposits_available": deposits is not None and len(deposits) > 0,
    }


def _equity_and_drawdown(deals: list[dict], deposits: list[dict]):
    """Kurva balance = deposit awal + akumulasi hasil trade tertutup urut waktu."""
    events = sorted(
        [({"t": o["time"], "amt": o["amount"]}) for o in deposits]
        + [({"t": d["close_time"], "amt": _net(d)}) for d in deals],
        key=lambda e: e["t"])
    if not events:
        return [], None, None
    equity = 0.0
    peak = None
    max_dd_pct = 0.0
    max_dd_abs = 0.0
    points: list[dict] = []
    for e in events:
        equity += e["amt"]
        peak = equity if peak is None else max(peak, equity)
        dd_abs = peak - equity
        dd_pct = (dd_abs / peak * 100) if peak > 0 else 0.0
        if dd_pct >= max_dd_pct:
            max_dd_pct, max_dd_abs = dd_pct, dd_abs
        points.append({"t": e["t"], "balance": round(equity, 2)})
    return points, (max_dd_pct or None), (max_dd_abs or None)


def equity_curve(deals: list[dict], deposits: list[dict]) -> list[dict]:
    points, _, _ = _equity_and_drawdown(deals, deposits)
    return points


PERIODS = ("today", "7d", "30d", "all", "custom")


def resolve_period(period: str, from_ts: int = 0, to_ts: int = 0,
                   now_ts: Optional[int] = None) -> tuple[int, int]:
    """Kembalikan (since_ts, until_ts) UTC untuk nama periode standar."""
    import datetime as dt
    now = int(now_ts if now_ts is not None else time_now())
    if period not in PERIODS:
        raise ValueError(f"Periode tidak dikenal: {period}")
    if period == "today":
        start = dt.datetime.fromtimestamp(now, dt.timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0)
        return int(start.timestamp()), now
    if period == "7d":
        return now - 7 * 86400, now
    if period == "30d":
        return now - 30 * 86400, now
    if period == "all":
        return 0, now
    # custom
    if from_ts <= 0 or to_ts <= 0 or from_ts > to_ts:
        raise ValueError("Rentang tanggal khusus tidak valid.")
    return int(from_ts), min(int(to_ts), now)


def time_now() -> int:
    import time
    return int(time.time())
