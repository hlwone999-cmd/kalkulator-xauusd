"""Konektor DEMO — data demonstrasi yang diberi LABEL JELAS.

Digunakan untuk: pengembangan, pengujian dashboard, dan melihat tampilan
tanpa akun sungguhan. Data DIBANGKITKAN secara deterministik dari seed
(login) sehingga hasil pengujian stabil. Bukan data akun sungguhan.
"""
from __future__ import annotations

import random
import time

from .base import Connector, ConnectorError

INITIAL_DEPOSIT = 10_000.0
SYMBOLS = ["XAUUSD", "EURUSD", "BTCUSD"]


class DemoConnector(Connector):
    platform = "demo"
    mode = "demo"

    def __init__(self, seed: str = "demo"):
        self._seed = str(seed)
        self._connected = False
        self._info: dict = {}

    # ---- data generatif (deterministik) --------------------------------
    def _rng(self) -> random.Random:
        return random.Random(f"pytrader-demo::{self._seed}")

    def _generate(self) -> tuple[list[dict], list[dict], list[dict]]:
        rng = self._rng()
        now = int(time.time())
        start = now - 60 * 86400  # 60 hari terakhir
        closed: list[dict] = []
        ops: list[dict] = [{"time": start, "type": "deposit",
                            "amount": INITIAL_DEPOSIT}]
        t = start + 3600
        balance = INITIAL_DEPOSIT
        ticket = 100000
        for i in range(140):
            # sesekali deposit/withdrawal
            if i in (40, 90):
                amt = 2000 if i == 40 else -1500
                ops.append({"time": int(t), "type":
                            "deposit" if amt > 0 else "withdrawal",
                            "amount": float(amt)})
                balance += amt
            sym = rng.choice(SYMBOLS)
            is_win = rng.random() < 0.56
            risk = rng.uniform(0.008, 0.015) * balance  # ~1% risiko
            profit = round(risk * rng.uniform(1.2, 2.4) if is_win
                           else -risk * rng.uniform(0.8, 1.05), 2)
            hold = rng.randint(20, 300) * 60
            open_t = int(t)
            close_t = int(t + hold)
            closed.append({
                "ticket": ticket, "symbol": sym,
                "type": rng.choice(["buy", "sell"]),
                "volume": round(rng.uniform(0.05, 1.2), 2),
                "open_price": round(rng.uniform(1800, 2700), 2),
                "close_price": round(rng.uniform(1800, 2700), 2),
                "open_time": open_t, "close_time": close_t,
                "profit": profit,
                "swap": round(rng.uniform(-0.4, 0.4), 2),
                "commission": round(-abs(rng.uniform(0, 0.8)), 2),
            })
            balance += profit
            ticket += 7
            t += hold + rng.randint(30, 400) * 60
            if t > now - 3600:
                break
        # 3 posisi terbuka
        open_pos = []
        for k in range(3):
            open_pos.append({
                "ticket": ticket + k, "symbol": SYMBOLS[k % len(SYMBOLS)],
                "type": rng.choice(["buy", "sell"]),
                "volume": round(rng.uniform(0.05, 0.6), 2),
                "open_price": round(rng.uniform(1800, 2700), 2),
                "open_time": now - rng.randint(1, 20) * 3600,
                "close_price": None, "close_time": None,
                "profit": round(rng.uniform(-180, 240), 2),
                "swap": round(rng.uniform(-0.3, 0.3), 2),
                "commission": -0.5,
            })
        return ops, closed, open_pos

    # ---- antarmuka Connector -------------------------------------------
    def connect(self) -> dict:
        ops, closed, open_pos = self._generate()
        balance = INITIAL_DEPOSIT + sum(o["amount"] for o in ops) \
            + sum(c["profit"] + c["swap"] + c["commission"] for c in closed)
        floating = round(sum(p["profit"] + p["swap"] + p["commission"]
                             for p in open_pos), 2)
        self._info = {
            "login": self._seed,
            "name": "Akun Demonstrasi",
            "broker": "DEMO — bukan akun sungguhan",
            "server": "demo-server",
            "currency": "USD",
            "balance": round(balance, 2),
            "equity": round(balance + floating, 2),
            "leverage": 500,
            "platform": self.platform,
        }
        self._connected = True
        return dict(self._info)

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def dynamic_info(self) -> dict:
        if not self._connected:
            raise ConnectorError("Akun demo belum terhubung.")
        ops, closed, open_pos = self._generate()
        floating = round(sum(p["profit"] + p["swap"] + p["commission"]
                             for p in open_pos), 2)
        balance = self._info["balance"]
        return {"balance": balance, "equity": round(balance + floating, 2)}

    def closed_positions(self, since_ts: int, until_ts: int) -> list[dict]:
        _, closed, _ = self._generate()
        return [c for c in closed if since_ts <= c["close_time"] <= until_ts]

    def open_positions(self) -> list[dict]:
        _, _, open_pos = self._generate()
        return open_pos

    def balance_operations(self, since_ts: int, until_ts: int) -> list[dict]:
        ops, _, _ = self._generate()
        return [o for o in ops if since_ts <= o["time"] <= until_ts]
