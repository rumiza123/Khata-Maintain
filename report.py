from collections import defaultdict


def monthly_report(rows: list, catalog: dict, month: str) -> dict:
    """month = 'YYYY-MM'. Sales = cash + udhaar rows. Profit counts only rows
    whose item has a catalog cost and a quantity."""
    cat = {k.lower(): v for k, v in catalog.items()}
    mrows = [r for r in rows if r["date"].startswith(month)]
    sales = [r for r in mrows if r["kind"] in ("cash", "udhaar")]

    items = defaultdict(lambda: {"qty": 0.0, "revenue": 0.0, "cost": 0.0, "costed": 0.0})
    daily = defaultdict(float)
    cogs = costed_rev = 0.0
    uncosted = 0
    for r in sales:
        name = (r.get("item") or "(no item)").lower()
        it = items[name]
        it["revenue"] += r["amount"]
        it["qty"] += r.get("qty") or 0
        daily[r["date"]] += r["amount"]
        cost_price = cat.get(name, {}).get("cost")
        if cost_price and r.get("qty"):
            cost = cost_price * r["qty"]
            it["cost"] += cost
            it["costed"] += r["amount"]
            cogs += cost
            costed_rev += r["amount"]
        else:
            uncosted += 1

    bal = defaultdict(float)
    sign = {"udhaar": 1, "payment": -1, "cash": 0}
    for r in rows:
        bal[r["customer"]] += sign[r["kind"]] * r["amount"]

    profit = costed_rev - cogs
    top = sorted(
        ({"item": k, "qty": round(v["qty"], 2), "revenue": round(v["revenue"], 2),
          "profit": round(v["costed"] - v["cost"], 2) if v["cost"] else None}
         for k, v in items.items()),
        key=lambda x: -x["revenue"])
    return {
        "month": month,
        "entries": len(mrows),
        "total_sales": round(sum(r["amount"] for r in sales), 2),
        "cash_sales": round(sum(r["amount"] for r in sales if r["kind"] == "cash"), 2),
        "credit_sales": round(sum(r["amount"] for r in sales if r["kind"] == "udhaar"), 2),
        "collections": round(sum(r["amount"] for r in mrows if r["kind"] == "payment"), 2),
        "outstanding": round(sum(v for v in bal.values() if v > 0), 2),
        "cogs": round(cogs, 2),
        "gross_profit": round(profit, 2),
        "margin_pct": round(profit / costed_rev * 100, 1) if costed_rev else None,
        "costed_sales": round(costed_rev, 2),
        "uncosted_entries": uncosted,
        "top_items": top[:10],
        "daily": [{"date": d, "sales": round(v, 2)} for d, v in sorted(daily.items())],
    }