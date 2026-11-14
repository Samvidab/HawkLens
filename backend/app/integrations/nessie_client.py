"""Nessie (Capital One hackathon banking API) client stub, TRD §8.2.

The Nessie teammate replaces this file; signatures must not change. NESSIE_MODE=stub keeps an
in-memory ledger with deterministic IDs. NESSIE_MODE=live is not implemented here.
"""
from __future__ import annotations

import hashlib

from pydantic import BaseModel

from app.config import get_settings


class Bill(BaseModel):  # TRD leaves Bill undefined; minimal shape the engine/baseline needs
    bill_id: str
    building_id: str
    month: str  # YYYY-MM
    amount_usd: float
    kwh: float | None = None


_ledger: dict[str, list[dict]] = {"accounts": [], "transfers": [], "bills": []}


def reset_stub() -> None:
    for v in _ledger.values():
        v.clear()


def _id(kind: str, *parts) -> str:
    return hashlib.sha256("|".join([kind, *map(str, parts)]).encode()).hexdigest()[:24]


def _check_stub() -> None:
    if get_settings().nessie_mode == "live":
        raise NotImplementedError("live Nessie client is provided by the Nessie teammate")


def get_bills(building_id: str) -> list[Bill]:
    _check_stub()
    base = 8000 + int(_id("bills", building_id)[:4], 16) % 4000  # deterministic per building
    return [Bill(bill_id=_id("bill", building_id, m), building_id=building_id, month=f"2026-{m:02d}",
                 amount_usd=float(base + 150 * (m % 6)), kwh=float((base + 150 * (m % 6)) / 0.11)) for m in range(1, 13)]


def create_account(customer_id: str, nickname: str = "Retrofit Reserve") -> str:
    _check_stub()
    aid = _id("acct", customer_id, nickname, len(_ledger["accounts"]))
    _ledger["accounts"].append({"id": aid, "customer_id": customer_id, "nickname": nickname, "balance": 0.0})
    return aid


def transfer(from_account: str, to_account: str, amount: float, description: str) -> str:
    _check_stub()
    if amount <= 0:
        raise ValueError("amount must be positive")
    tid = _id("xfer", from_account, to_account, amount, len(_ledger["transfers"]))
    _ledger["transfers"].append({"id": tid, "from": from_account, "to": to_account, "amount": amount,
                                 "description": description})
    return tid


def create_bill(account_id: str, merchant_id: str, amount: float, description: str) -> str:
    _check_stub()
    if amount <= 0:
        raise ValueError("amount must be positive")
    bid = _id("bill", account_id, merchant_id, amount, len(_ledger["bills"]))
    _ledger["bills"].append({"id": bid, "account": account_id, "merchant": merchant_id, "amount": amount,
                             "description": description})
    return bid
