"""Nessie (Capital One hackathon banking API): TRD §8.2 client.

NESSIE_MODE=stub  in-memory ledger with deterministic ids (default for tests/demo without a key).
NESSIE_MODE=live  thin wrapper around the Nessie teammate's code in <repo>/nessie/ (not edited):
    - auth + base URL come from her `client.py` (NESSIE_API_KEY, https://api.nessieisreal.com);
    - `get_bills` uses her `get_bills.get_bills()` (all bills of the operating account), filtered per building;
    - her `finance.py` / `funding.py` hardcode the customer/account ids, return nothing and block all funding after one
      allocation, so reserve account, transfer (withdrawal + deposit) and contractor bills are our own calls (same auth).
    Ids: NESSIE_CUSTOMER_ID (customer) and NESSIE_SOURCE_ACCOUNT_ID (the operating account funds are taken from).
Signatures are the TRD's and do not change between modes.
"""
from __future__ import annotations

import hashlib
import math
import importlib
import os
import re
import sys
from datetime import date
from pathlib import Path

from pydantic import BaseModel

from app.config import get_settings
from app.envutil import env_value

HER_DIR = Path(__file__).resolve().parents[3] / "nessie"  # <repo>/nessie/ (the Nessie teammate's scripts)
HTTP_TIMEOUT_S = 15


class NessieError(RuntimeError):
    """A Nessie call failed (HTTP error, missing config). The message is safe to show: no key, no URL query."""


class Bill(BaseModel):  # TRD leaves Bill undefined; minimal shape the engine/baseline needs
    bill_id: str
    building_id: str
    month: str  # YYYY-MM
    amount_usd: float
    kwh: float | None = None  # Nessie bills carry only a dollar amount
    utility: str | None = None  # "electricity" | "gas"


_ledger: dict[str, list[dict]] = {"accounts": [], "transfers": [], "bills": []}


def reset_stub() -> None:
    for v in _ledger.values():
        v.clear()


def _id(kind: str, *parts) -> str:
    return hashlib.sha256("|".join([kind, *map(str, parts)]).encode()).hexdigest()[:24]


def _live() -> bool:
    return get_settings().nessie_mode == "live"


def get_bills(building_id: str) -> list[Bill]:
    """Utility bills of one building (live: the sandbox bills on the operating account named <building>_<utility>_<MM>)."""
    if _live():
        return _live_get_bills(building_id)
    base = 8000 + int(_id("bills", building_id)[:4], 16) % 4000  # deterministic per building
    return [Bill(bill_id=_id("bill", building_id, m), building_id=building_id, month=f"2026-{m:02d}",
                 amount_usd=float(base + 150 * (m % 6)), kwh=float((base + 150 * (m % 6)) / 0.11), utility="electricity") for m in range(1, 13)]


def create_account(customer_id: str, nickname: str = "Retrofit Reserve") -> str:
    """Account id for `nickname` (live: get-or-create, so approving twice never opens a second reserve)."""
    if _live():
        return _live_get_or_create_account(customer_id, nickname)
    aid = _id("acct", customer_id, nickname, len(_ledger["accounts"]))
    _ledger["accounts"].append({"id": aid, "customer_id": customer_id, "nickname": nickname, "balance": 0.0})
    return aid


def transfer(from_account: str, to_account: str, amount: float, description: str) -> str:
    if amount <= 0:
        raise ValueError("amount must be positive")
    if _live():
        return _live_transfer(from_account, to_account, amount, description)
    tid = _id("xfer", from_account, to_account, amount, len(_ledger["transfers"]))
    _ledger["transfers"].append({"id": tid, "from": from_account, "to": to_account, "amount": amount,
                                 "description": description})
    return tid


def create_bill(account_id: str, merchant_id: str, amount: float, description: str) -> str:
    """One bill on `account_id` payable to `merchant_id` (live: a payee name; same description -> same bill id)."""
    if amount <= 0:
        raise ValueError("amount must be positive")
    if _live():
        return _live_create_bill(account_id, merchant_id, amount, description)
    bid = _id("bill", account_id, merchant_id, amount, len(_ledger["bills"]))
    _ledger["bills"].append({"id": bid, "account": account_id, "merchant": merchant_id, "amount": amount,
                             "description": description})
    return bid


# ---- live mode ----------------------------------------------------------------------------------
_her_mods: dict = {}


def _her() -> dict:
    """Import the teammate's scripts (top-level modules that import each other as `from client import ...`)."""
    if _her_mods:
        return _her_mods
    key = env_value("NESSIE_API_KEY")
    if not key:
        raise NessieError("NESSIE_API_KEY is not set (backend/.env); it is the key the Nessie teammate uses in nessie/.env")
    os.environ["NESSIE_API_KEY"] = key  # her client.py reads it at import time (load_dotenv would not find backend/.env)
    if not HER_DIR.is_dir():
        raise NessieError(f"{HER_DIR} not found: merge origin/nessie_data")
    sys.path.insert(0, str(HER_DIR))
    try:
        for name in ("client", "get_bills"):
            _her_mods[name] = importlib.import_module(name)
    finally:
        sys.path.remove(str(HER_DIR))
    if source := env_value("NESSIE_SOURCE_ACCOUNT_ID"):
        _her_mods["get_bills"].ACCOUNT_ID = source  # her get_bills() hardcodes the operating account; one setting rules
    return _her_mods


def reset_live() -> None:
    """Forget the imported modules (tests that change the key)."""
    for n in ("client", "get_bills"):
        sys.modules.pop(n, None)
    _her_mods.clear()


def _call(method: str, path: str, **kw) -> dict | list:
    import requests
    c = _her()["client"]
    try:
        r = getattr(requests, method)(c.BASE_URL + path, params={"key": c.API_KEY}, timeout=HTTP_TIMEOUT_S, **kw)
    except requests.RequestException as e:
        raise NessieError(f"Nessie {method.upper()} {path} failed: {type(e).__name__}") from e
    if r.status_code >= 400:
        raise NessieError(f"Nessie {method.upper()} {path} -> HTTP {r.status_code}: {r.text[:200]}")
    return r.json()


def _created_id(body: dict, what: str) -> str:
    try:
        return body["objectCreated"]["_id"]
    except (KeyError, TypeError) as e:
        raise NessieError(f"Nessie did not return an id for the new {what}: {str(body)[:150]}") from e


_BILL_NICK = re.compile(r"^(?P<building>.+)_(?P<utility>electricity|gas)_(?P<month>\d{2})$")


def _live_get_bills(building_id: str) -> list[Bill]:
    # Vedika 58ecff2: optional dedicated building-account mapping. Keep the
    # support lane's shared-account filter and safe transfer behavior otherwise.
    account = env_value("NESSIE_BUILDING_ACCOUNT_" + building_id.replace("-", "_").upper())
    if account:
        out = []
        for item in _call("get", f"/accounts/{account}/bills"):
            amount, paid = item.get("payment_amount"), item.get("payment_date")
            if (not item.get("_id") or not isinstance(paid, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", paid)
                    or isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(amount) or amount < 0):
                continue
            match = _BILL_NICK.match(str(item.get("nickname", "")))
            out.append(Bill(bill_id=str(item["_id"]), building_id=str(building_id), month=paid[:7],
                            amount_usd=float(amount), kwh=None, utility=match["utility"] if match else None))
        return sorted(out, key=lambda b: b.month)
    out = []
    for b in _her()["get_bills"].get_bills():  # her function: every bill on the operating account
        m = _BILL_NICK.match(str(b.get("nickname", "")))
        amount = b.get("payment_amount")
        if not m or m["building"] != str(building_id) or not isinstance(amount, (int, float)) or amount < 0:
            continue  # someone else's building, a contractor bill, or malformed
        out.append(Bill(bill_id=b["_id"], building_id=str(building_id), amount_usd=float(amount), utility=m["utility"],
                        month=f"{str(b.get('payment_date', ''))[:4]}-{m['month']}"))
    return sorted(out, key=lambda x: (x.month, x.utility or ""))


def _live_get_or_create_account(customer_id: str, nickname: str) -> str:
    for a in _call("get", f"/customers/{customer_id}/accounts"):
        if a.get("nickname") == nickname:
            return a["_id"]
    body = {"type": "Savings", "nickname": nickname, "rewards": 0, "balance": 0}
    return _created_id(_call("post", f"/customers/{customer_id}/accounts", json=body), "account")


def _live_transfer(from_account: str, to_account: str, amount: float, description: str) -> str:
    """Record a transfer as a withdrawal on the source plus a deposit on the destination (the calls the Nessie teammate's
    test_withdrawal.py / test_deposit.py use). This sandbox's `/transfers` rejects `medium`/`payee_id`, and it never
    recomputes an account's `balance` from its records: the movement shows up as completed transactions, not as a new
    balance (her funding ledger says the same: bank_transfer_completed false). Returns "<withdrawal id>:<deposit id>"."""
    amount = round(amount, 2)
    body = {"medium": "balance", "transaction_date": date.today().isoformat(), "status": "completed", "amount": amount,
            "description": description}  # all of these: a stored Withdrawal without date/status/description breaks its list endpoint
    w = _created_id(_call("post", f"/accounts/{from_account}/withdrawals", json=body), "withdrawal")
    try:
        d = _created_id(_call("post", f"/accounts/{to_account}/deposits", json=body), "deposit")
    except NessieError as e:
        try:  # put the money back so a failed transfer does not lose it
            _call("post", f"/accounts/{from_account}/deposits", json={**body, "description": f"refund: {description}"[:120]})
        except NessieError:
            raise NessieError(f"deposit failed AND the refund failed (withdrawal {w} of ${amount:,.2f} is not returned): {e}") from e
        raise NessieError(f"deposit into the reserve failed; the ${amount:,.2f} withdrawal was refunded: {e}") from e
    return f"{w}:{d}"


def _live_create_bill(account_id: str, merchant_id: str, amount: float, description: str) -> str:
    for b in _call("get", f"/accounts/{account_id}/bills"):  # crash between POST and our bookkeeping must not double-bill
        if b.get("nickname") == description:
            return b["_id"]
    body = {"status": "pending", "payee": merchant_id, "nickname": description, "payment_date": date.today().isoformat(),
            "recurring_date": 1, "payment_amount": round(amount, 2)}  # same payload shape her upload_bills.py uses
    return _created_id(_call("post", f"/accounts/{account_id}/bills", json=body), "bill")
