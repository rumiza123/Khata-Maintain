# Khata-Maintain
 
A voice-first udhaar (credit) ledger for neighbourhood shops. The shopkeeper speaks or types an entry in Hindi or Hinglish, confirms it, and the app tracks pending and paid dues, monthly sales and gross profit. It can also read the day's summary aloud.
 

 
## The problem
 
Most kirana shops keep their khata in a paper notebook. Entries get lost, old dues are forgotten, and the owner has no clear view of monthly sales or profit. Typing into an app is slow for many shopkeepers, but speaking comes naturally.
 
## Gnani AI models used
 
| Model | Used for |
|---|---|
| **Prisma v3.0** (speech to text) | Transcribes the spoken command (`/stt/v3`, `language_code` auto or Hindi or English) |
| **Timbre v2.5** (text to speech) | Reads the daily udhaar summary aloud (`/api/v1/tts/inference`, voice Nalini) |
 
 
## Features
 
- **Voice or typed entries** in Hindi, Hinglish or English, in any word order
  (`Teen sau rupaye udhaar, atta do kilo, Ramesh ne` works the same as `Ramesh ne 2 kg atta 300 rupaye udhaar`)
- **Confirm before save.** Every entry or correction appears on a card first, because the ledger holds money
- Three entry types: `udhaar` (credit), `payment`, `cash` sale. Cash sales with no name are saved as "Walk-in"
- **Pending / partial / paid status** per udhaar entry. Payments settle the oldest dues first, or one specific entry via "Mark paid"
- `Ramesh paid` settles a customer's full balance in one sentence
- Voice or typed **correction** (`300 nahi 250`) and **undo**
- **Customer dues** panel, with a WhatsApp-ready reminder text for each customer (nothing is sent automatically)
- **Item catalog with cost prices**, and a **monthly report**: total, cash and credit sales, collections, outstanding udhaar, cost of goods, gross profit, top items, with print and CSV export
- **Spoken summary** through Timbre
- **Shopkeeper accounts** (username or email, hashed password), a separate ledger per shop, light and dark mode
## Architecture
 
```
Browser (index.html)
   │  mic -> 16 kHz WAV, or typed text
   ▼
FastAPI (main.py)
   ├─ gnani.py    Prisma (STT), Timbre (TTS)
   ├─ nlu.py      rule-based parser: roles, not word order
   ├─ ledger.py   entries, balances, paid status, undo, reminders
   └─ report.py   monthly report
   │
   ▼
data/  SQLite (users) + JSON (per-shop ledger and catalog)
```
 
Design choices:
- **Modular monolith.** One process and a clear split, which suits a single developer.
- **Pure domain logic.** `ledger.py`, `nlu.py` and `report.py` do no I/O, so they are tested without API keys.
- **The AI proposes, the user confirms, the ledger rules validate.** Every write goes through Pydantic validation and is undoable.
- **Gnani calls live in one adapter file**, so an API change touches one place.
## Setup (Windows PowerShell)
 
Requires Python 3.11+.
 
```powershell
git clone <your-repo-url>
cd <repo-folder>
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install fastapi uvicorn pydantic httpx python-dotenv python-multipart pytest
```
 
Create a `.env` file in the project root:
 
```
GNANI_API_KEY=your_key_here
```
 
Get a key from the Gnani API platform. `.env` and `data/` are in `.gitignore` and must never be committed.
 
macOS / Linux: use `python3 -m venv .venv` and `source .venv/bin/activate`.
 
## Run
 
```powershell
python -m uvicorn main:app --reload
```
 
Open **http://127.0.0.1:8000**, create an account, and start. Use `localhost` or `127.0.0.1`, because browsers block the microphone on other addresses.
 
## Try it
 
| Say or type | Result |
|---|---|
| `Ramesh ne 2 kg atta liya 300 rupaye udhaar` | Udhaar entry, shown as pending |
| `300 rupaye udhaar atta 2 kg Ramesh ne` | Same entry, different word order |
| `Geeta ko 1 kg chini 50 rupaye` | Cash sale |
| `Ramesh ne 100 diye` | Payment of ₹100, oldest due becomes partial |
| `Ramesh paid` | Settles Ramesh's full balance |
| `300 nahi 250` | Corrects the last entry's amount |
| `undo` | Reverts the last change |
 
## Project structure
 
```
├── main.py        routes, login, per-shop storage
├── gnani.py       Prisma and Timbre API calls
├── nlu.py         rule-based command parser
├── ledger.py      ledger logic: balances, statuses, undo, reminders
├── report.py      monthly report
├── index.html     dashboard
├── login.html     login and sign-up
├── tests/         pytest tests
└── data/          created at runtime (ignored by git)
```
 
## Tests
 
```powershell
python -m pytest tests
```
 
The ledger, status and report logic run without network access or API credits.
 
## Limitations
 
- **Rule-based understanding, not an LLM.** Unusual phrasing, heavy mispronunciation or very garbled speech can fail. The confirm card is the safety net.
- **One entry per sentence**, and **item names are single words** ("basmati rice" is read as "basmati" or "rice").
- With two unknown words and no `ne`/`ko`, the parser may swap customer and item. Check the confirm card.
- **Profit is gross profit** (sales minus cost of goods). It excludes rent, wages and stock on hand. It needs a catalog cost price and a quantity on the sale, in the catalog's unit.
- **Udhaar counts as a sale when given.** Payments count as collections, not sales.
- Names spoken in Devanagari and typed in Latin script count as different customers.
- **Demo-grade auth:** salted PBKDF2 hashes, in-memory sessions, no HTTPS, no email verification, no password reset.
- **Local deployment.** Data lives in local JSON and SQLite files, and the undo history resets on restart.
- Speech is limited to 30 seconds per recording (Prisma REST limit).
## Future work
 
- LLM-based parsing for free-form speech and several entries per sentence
- Customer phone numbers and sending reminders directly
- Cloud hosting with a proper database, HTTPS and password reset
- Stock tracking, and net profit with expenses
- More Indian languages and dialect testing
