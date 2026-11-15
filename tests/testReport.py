from report import monthly_report

def test_report_profit():
    rows = [
        {"date": "2026-11-03", "customer": "A", "item": "atta", "qty": 2, "unit": "kg", "amount": 300, "kind": "cash"},
        {"date": "2026-11-05", "customer": "A", "item": "atta", "qty": 1, "unit": "kg", "amount": 160, "kind": "udhaar"},
        {"date": "2026-11-06", "customer": "A", "item": None, "qty": None, "unit": None, "amount": 100, "kind": "payment"},
        {"date": "2026-10-30", "customer": "B", "item": "dal", "qty": 1, "unit": "kg", "amount": 99, "kind": "cash"},
    ]
    r = monthly_report(rows, {"atta": {"cost": 120}}, "2026-11")
    assert (r["total_sales"], r["cash_sales"], r["credit_sales"], r["collections"]) == (460, 300, 160, 100)
    assert r["cogs"] == 360 and r["gross_profit"] == 100
    assert r["outstanding"] == 60 and r["uncosted_entries"] == 0