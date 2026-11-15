import re

UDHAAR = {"udhaar", "udhar", "उधार", "उधारी", "credit"}
PAY = {"diye", "jama", "payment", "chukaye", "chukaya", "wapas", "mile", "mila", "received", "paid",
       "दिए", "दिये", "जमा", "चुकाए", "वापस", "मिले"}
CASHW = {"cash", "nakad", "नकद"}
UNDO = {"undo", "cancel", "hatao", "हटाओ"}
REM = {"reminder", "reminders", "remind", "yaad", "रिमाइंडर", "याद"}
SUM = {"summary", "hisab", "hisaab", "हिसाब", "सारांश"}
WRONG = {"galat", "गलत", "sudhar", "सुधार", "sahi", "theek", "badlo", "badal", "correct", "सही", "बदलो"}
NOT = {"nahi", "nahin", "nhi", "नहीं", "नही"}
NE = {"ne", "ने", "ko", "को", "se", "से"}
UNITS = {"kg", "kilo", "किलो", "litre", "liter", "लीटर", "packet", "पैकेट", "gram", "ग्राम", "dozen", "दर्जन"}
RUPEE = {"rupaye", "rupees", "rupay", "rupee", "rs", "₹", "रुपये", "रुपए", "रुपया"}
AMBIG = {"do", "ek", "दो", "एक"}
FILLER = {"liya", "lia", "le", "liye", "li", "लिया", "ली", "diya", "दिया", "aur", "और", "ka", "ki", "ke",
          "का", "की", "के", "hai", "है", "please", "aaj", "आज", "bhi", "total", "entry", "add", "likho",
          "likh", "karo", "kar", "do", "de", "dena", "amount", "qty", "quantity", "last", "pichla",
          "ek", "एक", "दो", "mein", "me", "tha", "thi", "hain", "chahiye", "dedo", "dijiye", "bill",
          "bhai", "bhaiya", "ji", "sahab", "sahib", "didi", "aunty", "uncle", "madam", "sir", "bhabhi"}
FILLER |= {"pending", "baaki", "baki", "bakaya"}
ITEMS = {"atta", "aata", "chini", "cheeni", "chawal", "dal", "daal", "tel", "namak", "doodh", "dudh", "chai",
         "patti", "sabun", "biscuit", "maggi", "ghee", "sugar", "rice", "oil", "salt", "milk", "tea", "bread",
         "anda", "ande", "aloo", "pyaz", "tamatar", "masala", "besan", "maida", "suji", "soap", "आटा", "चीनी",
         "चावल", "दाल", "तेल", "नमक", "दूध", "चाय", "साबुन", "बिस्कुट"}
ONES = {"ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5, "chhe": 6, "saat": 7,
        "aath": 8, "nau": 9, "das": 10, "dedh": 1.5, "dhai": 2.5, "aadha": 0.5, "adha": 0.5,
        "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "छह": 6, "सात": 7, "आठ": 8, "नौ": 9,
        "दस": 10, "डेढ़": 1.5, "ढाई": 2.5, "आधा": 0.5}
MULT = {"sau": 100, "सौ": 100, "hazaar": 1000, "hazar": 1000, "हज़ार": 1000, "हजार": 1000}
FUNC = (UDHAAR | PAY | CASHW | UNDO | REM | SUM | WRONG | NOT | NE | UNITS | RUPEE | FILLER | set(MULT))
NUM_RE = re.compile(r"\d[\d,]*(\.\d+)?")


def num(w):
    return float(w.replace(",", "")) if NUM_RE.fullmatch(w) else None


def tokens(text: str) -> list:
    """Words as str, numbers as float. 'paanch sau' -> 500.0, '2 hazaar' -> 2000.0, '2kg' -> 2.0 'kg'."""
    t = text.lower().replace("₹", " ₹ ")
    t = re.sub(r"\brs\.?\s*(?=\d)", "₹ ", t)
    t = re.sub(r"(\d)([^\d\s.,])", r"\1 \2", t)
    t = re.sub(r"([^\d\s.,])(\d)", r"\1 \2", t)
    raw = [w for w in (x.strip(".,!?।:;\"'()") for x in t.split()) if w]
    out, i = [], 0
    while i < len(raw):
        w, v = raw[i], num(raw[i])
        nxt = raw[i + 1] if i + 1 < len(raw) else ""
        if v is None and w in ONES:
            if w in AMBIG and nxt not in MULT and nxt not in UNITS and nxt not in RUPEE:
                out.append(w)
                i += 1
                continue
            val = float(ONES[w])
            if nxt in MULT:
                val *= MULT[nxt]
                i += 1
            out.append(val)
            i += 1
            continue
        if v is not None and nxt in MULT:
            out.append(v * MULT[nxt])
            i += 2
            continue
        if w in MULT:
            out.append(float(MULT[w]))
            i += 1
            continue
        out.append(v if v is not None else w)
        i += 1
    return out


def parse(text: str, known=(), items=()) -> dict:
    items_l = ITEMS | {x.lower() for x in items}
    t = tokens(text)
    words = {w for w in t if isinstance(w, str)}
    nums = [(i, v) for i, v in enumerate(t) if isinstance(v, float)]
    unknown = {"intent": "unknown"}

    if words & UNDO:
        return {"intent": "undo"}
    if words & REM:
        return {"intent": "reminders"}
    if words & SUM:
        return {"intent": "summary"}

    # Correction: "300 nahi 250", "amount 200 sahi karo"
    not_i = next((i for i, w in enumerate(t) if w in NOT), None)
    if (not_i is not None and len(nums) >= 2) or words & WRONG:
        if not nums:
            return unknown
        if not_i is not None and len(nums) >= 2:
            before = [n for n in nums if n[0] < not_i]
            old = before[-1] if before else nums[0]
            val = next(v for j, v in nums if j != old[0])
        else:
            val = nums[-1][1]
        return {"intent": "correct", "field": "amount", "value": val}

    # ---- Entry: roles, not positions ----
    used, qty, unit, qty_i, unit_i = set(), None, None, None, None
    for i, w in enumerate(t):
        if isinstance(w, str) and w in UNITS:
            for k in (i - 1, i + 1):
                if 0 <= k < len(t) and isinstance(t[k], float):
                    qty, unit, qty_i, unit_i = t[k], w, k, i
                    used.add(k)
                    break
            if qty is not None:
                break

    amount = None
    for i, w in enumerate(t):
        if isinstance(w, str) and w in RUPEE:
            for k in ((i + 1, i - 1) if w == "₹" else (i - 1, i + 1)):
                if 0 <= k < len(t) and isinstance(t[k], float) and k not in used:
                    amount = t[k]
                    used.add(k)
                    break
            if amount is not None:
                break
    rest = [v for j, v in nums if j not in used]
    if amount is None:
        if not rest:
            return unknown
        amount = max(rest)
        rest.remove(amount)
    if qty is None and rest:
        qty = min(rest)

    kind = ("udhaar" if words & {"pending", "baaki", "baki", "bakaya"} else
            "payment" if (words & PAY and unit is None) else "udhaar" if words & UDHAAR else "cash")

    low_known = {k.lower(): k for k in known}
    cust = cust_i = None
    for i, w in enumerate(t):                                   # 1) known customer, anywhere
        if isinstance(w, str) and w in low_known:
            cust, cust_i = low_known[w], i
            break
    if cust is None:                                            # 2) word before ne/ko/se
        for i, w in enumerate(t):
            if w in NE and i > 0 and isinstance(t[i - 1], str) and t[i - 1] not in FUNC \
                    and t[i - 1] not in items_l:
                cust, cust_i = t[i - 1].title(), i - 1
                break

    pool = [(i, w) for i, w in enumerate(t) if isinstance(w, str) and w not in FUNC and i != cust_i]
    pool_d = dict(pool)
    item_i = next((i for i, w in pool if w in items_l), None)   # known item word
    if item_i is None and unit_i is not None:                   # word touching the quantity+unit
        lo, hi = min(qty_i, unit_i), max(qty_i, unit_i)
        item_i = next((k for k in (hi + 1, lo - 1) if k in pool_d), None)
    if item_i is None and cust is not None and pool:
        item_i = pool[0][0]
    item = pool_d.get(item_i)

    if cust is None:                                            # 3) leftover word that isn't the item
        rem = [w for i, w in pool if i != item_i and w not in items_l]
        if rem:
            cust = rem[0].title()
        elif kind == "cash":
            cust = "Walk-in"
        else:
            return unknown
    if kind == "payment":
        item = qty = unit = None
    return {"intent": "entry", "entries": [
        {"customer": cust, "item": item, "qty": qty, "unit": unit, "amount": amount, "kind": kind}]}