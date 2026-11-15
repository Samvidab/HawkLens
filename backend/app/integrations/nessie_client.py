
"""
Capital One Nessie API integration for HawkLens.

Supports:
- Stub mode for testing
- Live Nessie API requests
- Account creation
- Account transfers
- Contractor bill creation
- Utility bill retrieval

Environment variables:
NESSIE_MODE=live
NESSIE_API_KEY=your_api_key
NESSIE_CUSTOMER_ID=your_customer_id
NESSIE_SOURCE_ACCOUNT_ID=your_operating_account_id
"""

from __future__ import annotations

import hashlib
import os
from datetime import date

import requests
from pydantic import BaseModel

from app.config import get_settings
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


BASE_URL = "https://api.nessieisreal.com"

_ledger: dict[str, list[dict]] = {
    "accounts": [],
    "transfers": [],
    "bills": []
}


class Bill(BaseModel):
    bill_id: str
    building_id: str
    month: str
    amount_usd: float
    kwh: float | None = None


def reset_stub() -> None:
    for value in _ledger.values():
        value.clear()


def _id(kind: str, *parts) -> str:
    text = "|".join([kind, *map(str, parts)])
    return hashlib.sha256(text.encode()).hexdigest()[:24]


def _is_live() -> bool:
    return get_settings().nessie_mode == "live"


def _api_key() -> str:
    key = os.getenv("NESSIE_API_KEY")

    if not key:
        raise RuntimeError(
            "NESSIE_API_KEY is missing. Add it to backend/.env"
        )

    return key


def _request(method: str, path: str, payload=None):
    url = BASE_URL + path

    response = requests.request(
        method,
        url,
        params={"key": _api_key()},
        json=payload,
        timeout=15
    )

    response.raise_for_status()

    data = response.json()

    if isinstance(data, dict):
        if data.get("code") not in (None, 200, 201):
            raise RuntimeError(
                f"Nessie API error: {data.get('message', data)}"
            )

    return data


def _created_id(data) -> str:
    if isinstance(data, dict):
        obj = data.get("objectCreated", data)

        if isinstance(obj, dict):
            result = obj.get("_id") or obj.get("id")

            if result:
                return str(result)

    raise RuntimeError(
        "Nessie response did not include a created ID"
    )


# -----------------------------------------
# GET BILLS
# -----------------------------------------

def get_bills(building_id: str) -> list[Bill]:

    if _is_live():
        # Nessie bills are associated with accounts,
        # not building IDs.
        #
        # Configure a building-to-account mapping
        # before calling this in live mode.

        account_id = os.getenv(
            "NESSIE_BUILDING_ACCOUNT_" +
            building_id.replace("-", "_").upper()
        )

        if not account_id:
            raise RuntimeError(
                f"No Nessie account configured for building {building_id}"
            )

        data = _request(
            "GET",
            f"/accounts/{account_id}/bills"
        )

        bills = []

        for item in data:
            payment_date = item.get("payment_date", "")

            if not payment_date:
                continue

            amount = float(
                item.get("payment_amount", 0)
            )

            bills.append(
                Bill(
                    bill_id=str(item.get("_id", "")),
                    building_id=building_id,
                    month=payment_date[:7],
                    amount_usd=amount,
                    kwh=None
                )
            )

        return bills

    # Stub mode

    base = (
        8000 +
        int(_id("bills", building_id)[:4], 16) % 4000
    )

    bills = []

    for month in range(1, 13):
        amount = float(
            base + 150 * (month % 6)
        )

        bills.append(
            Bill(
                bill_id=_id(
                    "bill",
                    building_id,
                    month
                ),
                building_id=building_id,
                month=f"2026-{month:02d}",
                amount_usd=amount,
                kwh=amount / 0.11
            )
        )

    return bills


# -----------------------------------------
# GET ACCOUNT
# -----------------------------------------

def get_account(account_id: str) -> dict:
    """Live: Nessie GET /accounts/{id} -> {account_id, nickname, type, balance, simulated: False}.
    Stub: no account exists, so nothing is invented: balance None, simulated True."""
    if _is_live():
        data = _request("GET", f"/accounts/{account_id}")
        bal = data.get("balance")
        return {"account_id": str(data.get("_id", account_id)), "nickname": data.get("nickname"),
                "type": data.get("type"), "balance": float(bal) if isinstance(bal, (int, float)) else None,
                "simulated": False}
    return {"account_id": account_id, "nickname": None, "type": None, "balance": None, "simulated": True}


# -----------------------------------------
# CREATE ACCOUNT
# -----------------------------------------

def create_account(
    customer_id: str,
    nickname: str = "Retrofit Reserve"
) -> str:

    if _is_live():

        payload = {
            "type": "Savings",
            "nickname": nickname,
            "rewards": 0,
            "balance": 0
        }

        data = _request(
            "POST",
            f"/customers/{customer_id}/accounts",
            payload
        )

        return _created_id(data)

    # Stub mode

    aid = _id(
        "acct",
        customer_id,
        nickname,
        len(_ledger["accounts"])
    )

    _ledger["accounts"].append({
        "id": aid,
        "customer_id": customer_id,
        "nickname": nickname,
        "balance": 0.0
    })

    return aid


# -----------------------------------------
# TRANSFER MONEY
# -----------------------------------------

def transfer(
    from_account: str,
    to_account: str,
    amount: float,
    description: str
) -> str:

    if amount <= 0:
        raise ValueError(
            "amount must be positive"
        )

    if _is_live():

        payload = {
            "medium": "balance",
            "payee_id": to_account,
            "amount": round(amount, 2),
            "transaction_date": date.today().isoformat(),
            "description": description
        }

        data = _request(
            "POST",
            f"/accounts/{from_account}/transfers",
            payload
        )

        return _created_id(data)

    # Stub mode

    tid = _id(
        "xfer",
        from_account,
        to_account,
        amount,
        len(_ledger["transfers"])
    )

    _ledger["transfers"].append({
        "id": tid,
        "from": from_account,
        "to": to_account,
        "amount": amount,
        "description": description
    })

    return tid


# -----------------------------------------
# CREATE BILL
# -----------------------------------------

def create_bill(
    account_id: str,
    merchant_id: str,
    amount: float,
    description: str
) -> str:

    if amount <= 0:
        raise ValueError(
            "amount must be positive"
        )

    if _is_live():

        payload = {
            "status": "pending",
            "payee": merchant_id,
            "nickname": description,
            "payment_date": date.today().isoformat(),
            "payment_amount": round(amount, 2)
        }

        data = _request(
            "POST",
            f"/accounts/{account_id}/bills",
            payload
        )

        return _created_id(data)

    # Stub mode

    bid = _id(
        "bill",
        account_id,
        merchant_id,
        amount,
        len(_ledger["bills"])
    )

    _ledger["bills"].append({
        "id": bid,
        "account": account_id,
        "merchant": merchant_id,
        "amount": amount,
        "description": description
    })

    return bid
