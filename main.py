import hashlib, hmac, json, re, secrets, sqlite3
from datetime import date
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Response, Depends
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, ValidationError, Field
from ledger import Ledger, Entry
from gnani import transcribe, synthesize, GnaniError
from nlu import parse, ONES, MULT
from report import monthly_report

app = FastAPI()
DATA = Path("data")
DATA.mkdir(exist_ok=True)
sessions: dict[str, str] = {}     # token -> username (in memory: restart = log in again)
ledgers: dict[str, Ledger] = {}

# ---------- auth (SQLite) ----------
DB = DATA / "khata.db"

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

with db() as c:
    c.execute("""CREATE TABLE IF NOT EXISTS users(
        username TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL,
        pw TEXT NOT NULL, shop TEXT NOT NULL,
        created TEXT DEFAULT CURRENT_TIMESTAMP)""")

def hash_pw(pw: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    return salt.hex() + ":" + hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 200_000).hex()

def check_pw(pw: str, stored: str) -> bool:
    return hmac.compare_digest(hash_pw(pw, bytes.fromhex(stored.split(":")[0])), stored)

def shop(request: Request) -> str:
    u = sessions.get(request.cookies.get("session", ""))
    if not u:
        raise HTTPException(401, "Login required")
    return u

def start_session(resp: Response, user: str):
    tok = secrets.token_urlsafe(32)
    sessions[tok] = user
    resp.set_cookie("session", tok, httponly=True, samesite="lax", max_age=7 * 86400)

class Cred(BaseModel):
    username: str = ""      # on login this may hold username OR email
    password: str
    email: str = ""
    shop_name: str = ""

@app.post("/signup")
def signup(c: Cred, response: Response):
    u, em = c.username.strip().lower(), c.email.strip().lower()
    if not re.fullmatch(r"[a-z0-9_]{3,20}", u):
        raise HTTPException(400, "Username: 3-20 letters, digits or _")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", em):
        raise HTTPException(400, "Enter a valid email")
    if len(c.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    shop_name = c.shop_name.strip()[:40] or u
    try:
        with db() as conn:
            conn.execute("INSERT INTO users(username,email,pw,shop) VALUES(?,?,?,?)",
                         (u, em, hash_pw(c.password), shop_name))
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Username or email already registered")
    start_session(response, u)
    return {"shop": shop_name}

@app.post("/login")
def login(c: Cred, response: Response):
    ident = c.username.strip().lower()
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE username=? OR email=?", (ident, ident)).fetchone()
    if not row or not check_pw(c.password, row["pw"]):
        raise HTTPException(401, "Wrong username/email or password")
    start_session(response, row["username"])
    return {"shop": row["shop"]}

@app.post("/logout")
def logout(request: Request, response: Response):
    sessions.pop(request.cookies.get("session", ""), None)
    response.delete_cookie("session")
    return {"ok": True}

@app.get("/me")
def me(user: str = Depends(shop)):
    with db() as conn:
        row = conn.execute("SELECT shop,email FROM users WHERE username=?", (user,)).fetchone()
    return {"username": user, "shop": row["shop"], "email": row["email"]}

# ---------- per-shop ledger ----------
def get_ledger(user: str) -> Ledger:
    if user not in ledgers:
        l, f = Ledger(), DATA / f"ledger_{user}.json"
        if f.exists():
            d = json.loads(f.read_text("utf-8"))
            l.rows, l._next_id = d["rows"], d["next_id"]
        ledgers[user] = l
    return ledgers[user]

def persist(user: str):
    l = ledgers[user]
    (DATA / f"ledger_{user}.json").write_text(
        json.dumps({"rows": l.rows, "next_id": l._next_id}, ensure_ascii=False), "utf-8")

# ---------- catalog + report ----------
def cat_file(user: str) -> Path:
    return DATA / f"catalog_{user}.json"

def get_catalog(user: str) -> dict:
    f = cat_file(user)
    return json.loads(f.read_text("utf-8")) if f.exists() else {}

class Item(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    cost: float = Field(gt=0)
    unit: str = ""

@app.get("/catalog")
def catalog_list(user: str = Depends(shop)):
    return {"items": get_catalog(user)}

@app.post("/catalog")
def catalog_set(i: Item, user: str = Depends(shop)):
    c = get_catalog(user)
    c[i.name.strip().lower()] = {"cost": i.cost, "unit": i.unit.strip().lower()}
    cat_file(user).write_text(json.dumps(c, ensure_ascii=False), "utf-8")
    return {"items": c}

@app.delete("/catalog/{name}")
def catalog_del(name: str, user: str = Depends(shop)):
    c = get_catalog(user)
    c.pop(name.lower(), None)
    cat_file(user).write_text(json.dumps(c, ensure_ascii=False), "utf-8")
    return {"items": c}

@app.get("/report")
def report(month: str = "", user: str = Depends(shop)):
    month = month or date.today().isoformat()[:7]
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        raise HTTPException(400, "month must be YYYY-MM")
    return monthly_report(get_ledger(user).rows, get_catalog(user), month)

# ---------- pages ----------
@app.get("/")
def index(request: Request):
    if not sessions.get(request.cookies.get("session", "")):
        return RedirectResponse("/login")
    return FileResponse("index.html")

@app.get("/login")
def login_page():
    return FileResponse("login.html")

# ---------- API ----------
class Action(BaseModel):
    intent: str
    entries: list[dict] = []
    field: str | None = None
    value: float | str | None = None

SETTLE = {"paid", "clear", "cleared", "settle", "settled", "chuka", "chukta", "chukaya", "chukaye",
          "received", "jama"}
NUMW = (set(ONES) - {"do", "ek", "दो", "एक"}) | set(MULT)

def settle_intent(text: str, l: Ledger):
    """'Ramesh paid' (no amount) -> payment of his full balance."""
    if re.search(r"\d", text):
        return None
    ws = [w.strip(".,!?।") for w in text.lower().split()]
    if not set(ws) & SETTLE or set(ws) & NUMW:
        return None
    bal = l.balances()
    low = {k.lower(): k for k in bal}
    name = next((low[w] for w in ws if w in low), None)
    if not name:
        return None
    if bal[name] <= 0:
        raise HTTPException(400, f"{name} ka koi udhaar baaki nahi")
    return {"intent": "entry", "entries": [{"customer": name, "amount": bal[name], "kind": "payment"}]}

@app.post("/parse")
async def parse_cmd(audio: UploadFile | None = File(None), text: str | None = Form(None),
                    lang: str = Form("indic-auto"), user: str = Depends(shop)):
    if not re.fullmatch(r"[A-Za-z-]{2,15}", lang):
        lang = "indic-auto"
    if audio is not None:
        data = await audio.read()
        (DATA / "last_audio.wav").write_bytes(data)      # play this file to check what Prisma received
        try:
            text = transcribe(data, audio.filename or "audio.wav", lang)
        except GnaniError as e:
            raise HTTPException(502, str(e))
        print("STT:", lang, len(data), "bytes ->", repr(text))
    if not text or not text.strip():
        raise HTTPException(400, "Audio ya text bhejiye")
    l = get_ledger(user)
    known_items = list(get_catalog(user)) + [r["item"] for r in l.rows if r.get("item")]
    result = (settle_intent(text, l)
              or parse(text, list(l.balances()), known_items)
              or {"intent": "unknown"})
    return {"transcript": text, **result}

@app.post("/apply")
def apply(a: Action, user: str = Depends(shop)):
    l = get_ledger(user)
    try:
        if a.intent == "entry":
            out = {"saved": [l.add(Entry(**e).model_dump()) for e in a.entries]}
        elif a.intent == "correct":
            out = {"row": l.correct_last(a.field, a.value)}
        elif a.intent == "undo":
            l.undo()
            out = {"ok": True}
        else:
            raise HTTPException(400, "Unknown intent")
    except (ValueError, ValidationError) as e:
        raise HTTPException(400, str(e))
    persist(user)
    return out

@app.get("/ledger")
def ledger_view(user: str = Depends(shop)):
    l = get_ledger(user)
    st = l.statuses()
    return {"rows": [{**r, **st.get(r["id"], {})} for r in l.rows], "balances": l.balances()}

@app.get("/reminders")
def reminders(days: int = 7, user: str = Depends(shop)):
    return {"reminders": get_ledger(user).reminders(days)}

@app.get("/summary")
def summary(user: str = Depends(shop)):
    try:
        return Response(synthesize(get_ledger(user).summary_text()), media_type="audio/wav")
    except GnaniError as e:
        raise HTTPException(502, str(e))