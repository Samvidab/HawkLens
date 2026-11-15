"""In-memory stand-in for api.nessieisreal.com: just the endpoints nessie_client uses, with the validation that matters."""
from __future__ import annotations

import json
import re
import uuid

BASE = "https://api.nessieisreal.com"
# the ids the Nessie teammate seeded (hardcoded in nessie/finance.py and test_deposit.py)
CUSTOMER = "4dba3d91-00ae-405b-bdf1-aac090f66996"
OPERATING = "3e4f8885-befb-4d0f-85ad-545b776f0888"
RESERVE = "37f8e523-1f9d-435d-8102-eef7f8dfc05b"


class Resp:
    def __init__(self, code: int, body):
        self.status_code, self._body = code, body
        self.text = json.dumps(body)

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.text)


class FakeNessie:
    def __init__(self, *, reserve_exists: bool = True, balance: float = 50_000_000.0):
        self.accounts = {OPERATING: {"_id": OPERATING, "customer_id": CUSTOMER, "nickname": "Hawk Lens Operating", "type": "Checking", "balance": balance}}
        if reserve_exists:
            self.accounts[RESERVE] = {"_id": RESERVE, "customer_id": CUSTOMER, "nickname": "Hawk Lens Retrofit Reserve", "type": "Savings", "balance": 0}
        self.bills: dict[str, list[dict]] = {a: [] for a in self.accounts}
        self.transfers: list[dict] = []
        self.writes: list[tuple[str, str, dict]] = []  # (method, path, body) for every POST
        self.calls: list[tuple[str, str]] = []
        self.keys: set[str | None] = set()
        self.fail_on: dict[str, int] = {}  # path regex -> HTTP code, once

    def seed_utility_bills(self):
        for nick, amt, date in [("23551_electricity_01", 12000.5, "2026-01-15"), ("23551_gas_01", 900.0, "2026-01-15"),
                                ("sample_001_electricity_01", 5.0, "2026-01-15"), ("a_b_c_electricity_02", 77.0, "2026-02-15"),
                                ("23551_electricity_xx", 1.0, "2026-03-15"), ("23551_electricity_03", -4.0, "2026-03-15")]:
            self.bills[OPERATING].append({"_id": f"u-{nick}", "nickname": nick, "payment_amount": amt, "payment_date": date, "payee": "Hawk Lens Electric Utility"})

    def install_plain(self):
        """Patch requests for a whole process (used by sitecustomize in subprocess tests)."""
        import requests
        requests.get = lambda url, **kw: self.request("GET", url, **kw)
        requests.post = lambda url, **kw: self.request("POST", url, **kw)
        return self

    def install(self, monkeypatch):
        import requests
        monkeypatch.setattr(requests, "get", lambda url, **kw: self.request("GET", url, **kw))
        monkeypatch.setattr(requests, "post", lambda url, **kw: self.request("POST", url, **kw))
        return self

    def request(self, method, url, params=None, json=None, timeout=None):
        assert url.startswith(BASE), url
        path = url[len(BASE):]
        self.keys.add((params or {}).get("key"))
        self.calls.append((method, path))
        for pat, code in list(self.fail_on.items()):
            if re.fullmatch(pat, path):
                del self.fail_on[pat]
                return Resp(code, {"code": code, "message": "injected failure"})
        if method == "POST":
            self.writes.append((method, path, dict(json or {})))
        if m := re.fullmatch(r"/customers/([^/]+)/accounts", path):
            if method == "GET":
                return Resp(200, [a for a in self.accounts.values() if a["customer_id"] == m[1]])
            aid = f"acct-{len(self.accounts)}"
            self.accounts[aid] = {**json, "_id": aid, "customer_id": m[1]}; self.bills[aid] = []
            return Resp(201, {"code": 201, "message": "Created", "objectCreated": self.accounts[aid]})
        if m := re.fullmatch(r"/accounts/([^/]+)", path):
            return Resp(200, self.accounts[m[1]]) if m[1] in self.accounts and method == "GET" else Resp(404, {"code": 404})
        if m := re.fullmatch(r"/accounts/([^/]+)/bills", path):
            if m[1] not in self.accounts:
                return Resp(404, {"code": 404})
            if method == "GET":
                return Resp(200, self.bills[m[1]])
            missing = {"status", "payee", "nickname", "payment_date", "payment_amount"} - set(json or {})
            if missing:
                return Resp(400, {"code": 400, "message": f"missing {sorted(missing)}"})
            b = {**json, "_id": f"bill-{uuid.uuid4().hex[:8]}", "account_id": m[1]}
            self.bills[m[1]].append(b)
            return Resp(201, {"code": 201, "objectCreated": b})
        # Strict like the real sandbox: unknown fields are rejected ("extra fields not permitted")
        if m := re.fullmatch(r"/accounts/([^/]+)/(withdrawals|deposits)", path):
            acct, kind = m[1], m[2]
            allowed = {"medium", "transaction_date", "status", "amount", "description"}
            required = allowed  # a stored withdrawal/deposit without all of these breaks its list endpoint on the real sandbox
            body = json or {}
            if acct not in self.accounts:
                return Resp(404, {"code": 404})
            if set(body) - allowed or required - set(body):
                return Resp(400, {"code": 400, "message": f"validation: extra/missing fields {sorted(set(body) ^ allowed)}"})
            if kind == "withdrawals":
                if self.accounts[acct]["balance"] < body["amount"]:
                    return Resp(400, {"code": 400, "message": "insufficient funds"})
                self.accounts[acct]["balance"] -= body["amount"]
            else:
                self.accounts[acct]["balance"] += body["amount"]
            t = {**body, "_id": f"{kind[0]}-{len(self.transfers)}", "account": acct, "kind": kind}
            self.transfers.append(t)
            return Resp(201, {"code": 201, "objectCreated": t})
        if re.fullmatch(r"/accounts/([^/]+)/transfers", path):
            body = json or {}
            if {"medium", "payee_id"} & set(body):
                return Resp(400, {"code": 400, "message": "2 validation errors for TransferCreate: extra fields not permitted"})
            return Resp(201, {"code": 201, "objectCreated": {**body, "_id": f"rec-{len(self.transfers)}"}})  # a record only, no balance change
        return Resp(404, {"code": 404, "message": f"{method} {path}"})
