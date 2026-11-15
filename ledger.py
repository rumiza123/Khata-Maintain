from datetime import date
from typing import Literal
from urllib.parse import quote
from pydantic import BaseModel, Field

EDITABLE = {"customer", "item", "qty", "unit", "amount", "kind"}
SIGN = {"udhaar": 1, "payment": -1, "cash": 0}

class Entry(BaseModel):
    customer: str = Field(min_length=1)
    item: str | None = None
    qty: float | None = None
    unit: str | None = None
    amount: float = Field(gt=0)
    kind: Literal["udhaar", "payment", "cash"]
    ref: int | None = None          # payment aimed at one specific udhaar row id

class Ledger:
    def __init__(self):
        self.rows: list[dict] = []
        self.undo_stack: list[tuple] = []
        self._next_id = 1

    def add(self, data: dict) -> dict:
        row = {"id": self._next_id, "date": date.today().isoformat(), **data}
        self._next_id += 1
        self.rows.append(row)
        self.undo_stack.append(("add", row["id"]))
        return row

    def correct_last(self, field: str, value) -> dict:
        if field not in EDITABLE:
            raise ValueError("Ye field edit nahi ho sakti")
        if not self.rows:
            raise ValueError("Koi entry nahi hai")
        row = self.rows[-1]
        validated = Entry(**{**row, field: value}).model_dump()
        old = row[field]
        row[field] = validated[field]
        self.undo_stack.append(("edit", row["id"], field, old))
        return row

    def undo(self) -> tuple:
        if not self.undo_stack:
            raise ValueError("Undo ke liye kuch nahi hai")
        op = self.undo_stack.pop()
        if op[0] == "add":
            self.rows = [r for r in self.rows if r["id"] != op[1]]
        else:
            _, rid, field, old = op
            next(r for r in self.rows if r["id"] == rid)[field] = old
        return op

    def balances(self) -> dict[str, float]:
        bal: dict[str, float] = {}
        for r in self.rows:
            bal[r["customer"]] = bal.get(r["customer"], 0) + SIGN[r["kind"]] * r["amount"]
        return bal

    def statuses(self) -> dict[int, dict]:
        """Per udhaar row: amount still unpaid and status. Payments with a ref settle that row first;
        all other payments settle the oldest unpaid rows first (FIFO)."""
        out, by_c = {}, {}
        for r in self.rows:
            by_c.setdefault(r["customer"], []).append(r)
        for rs in by_c.values():
            ud = [r for r in rs if r["kind"] == "udhaar"]
            left = {r["id"]: r["amount"] for r in ud}
            free = 0.0
            for p in (r for r in rs if r["kind"] == "payment"):
                ref = p.get("ref")
                if ref in left:
                    take = min(left[ref], p["amount"])
                    left[ref] -= take
                    free += p["amount"] - take
                else:
                    free += p["amount"]
            for r in ud:
                take = min(left[r["id"]], free)
                left[r["id"]] -= take
                free -= take
            for r in ud:
                l = round(left[r["id"]], 2)
                out[r["id"]] = {"left": l, "status": "paid" if l <= 0 else
                                "partial" if l < r["amount"] else "pending"}
        return out

    def reminders(self, days: int = 7) -> list[dict]:
        today, st, out = date.today(), self.statuses(), []
        for cust, bal in self.balances().items():
            if bal <= 0:
                continue
            open_rows = [r for r in self.rows if r["customer"] == cust and r["kind"] == "udhaar"
                         and st.get(r["id"], {}).get("left", 0) > 0]
            if not open_rows:
                continue
            age = (today - min(date.fromisoformat(r["date"]) for r in open_rows)).days
            if age >= days:
                msg = (f"Namaste {cust}ji, aapka {bal:.0f} rupaye udhaar baaki hai. "
                       "Kripya jald bhugtaan karein. Dhanyavaad.")
                out.append({"customer": cust, "balance": bal, "days_old": age,
                            "message": msg, "wa_link": "https://wa.me/?text=" + quote(msg)})
        return out

    def summary_text(self) -> str:
        dues = ", ".join(f"{k} ka {v:.0f} rupaye" for k, v in self.balances().items() if v > 0)
        return f"Aaj ki entries save ho gayi. Baaki udhaar: {dues or 'koi udhaar baaki nahi'}."