# Campus Customs: Yale Merch Shop + AI Shopping Assistant

AI Foundation · Homework 4 · William Siagian

**Campus Customs** is a demo web shop for Yale University merchandise. It has 102 products, live stock for each size, accounts and a saved cart. A **chat assistant** answers shopping questions from the real database:
- prices, sizes and stock;
- "what hoodies do you have?";
- alternatives when a size is sold out;
- store hours.

The assistant is a **PydanticAI agent**, served by a **FastAPI** backend. The storefront is a **React + Vite + TypeScript** app.

---

## Repository layout

```
hw4/
├── AI_prompts.md          # every prompt used to build this, by problem
├── requirements.txt       # backend Python dependencies (pinned)
├── .env.example           # settings template (placeholders only) → copy to .env
├── .gitignore
├── README.md
├── frontend/              # Vite React TypeScript app (the storefront + chat widget)
├── backend/
│   ├── main.py            # FastAPI app — run with: uvicorn main:app --reload --port 8000
│   ├── agent.py           # ┐
│   ├── models.py          # │ the agent
│   ├── tools.py           # │
│   └── prompts/           # │
│       └── prompt.md      # ┘
└── output/
    ├── harness.md         # how everything works (start with its "Start Here" section)
    ├── design.md          # design decisions and reasoning, per problem
    ├── usability.md       # the 4 usability improvements and how to see them
    ├── app_check.html     # hands-on app review with screenshots
    ├── app_check_images/  # screenshots linked from app_check.html
    └── audit_trail.json   # append-only log of every agent step
```

### The agent: four files in `backend/`
| File | What it is |
|---|---|
| `prompts/prompt.md` | The system prompt: voice, tool-use rules, stock wording, product-card rules, and **Safety rules**. |
| `agent.py` | Builds the PydanticAI `Agent`, routes each question to a fast or smart model tier, and runs it with limits (`run_chat`). It also checks the reply's numbers and writes the audit log. |
| `tools.py` | The 7 tools the agent can call: `search_products`, `lookup_product`, `suggest_alternatives`, `get_store_info`, `get_my_account`, `get_saved_chats`, `get_current_page`. |
| `models.py` | Every Pydantic type: the chat API request and reply, the agent's structured output, its per-request dependencies, and each tool's result. |

The other backend modules support the web app around the agent:
- `config.py`: settings;
- `db.py`: SQLite access and cache;
- `cards.py`: product cards;
- `history.py`: saved chats;
- `factcheck.py`: number checking;
- `audit.py`: the audit log;
- `auth.py` and `cart.py`: accounts and cart;
- `scripts/`: benchmark and audit summary.

---

## 1. Get the data pack (not in this repo)

The database and product images are **not in git**. Put the data pack inside `hw4/` like this:

```
hw4/
└── data/
    ├── campus_customs.db   # SQLite: catalogue, inventory, users, chat_messages
    └── products/           # product images referenced by the catalogue (*.jpg)
```

- The backend refuses to start with a clear message if either one is missing.
- On first run, it adds the tables it needs (`sessions`, `cart_items`) to the database.
- *(Optional)* AI on-model photos go in `data/model_photos/`, with a `manifest.json`. Without them, the shop just shows the regular product photos.

## 2. Requirements

- **Python 3.13** (3.11+ should work)
- **Node.js 20.19+** (tested on Node 24)
- A **Portkey API key** with access to the `gpt-6-luna` model. Without a key, the shop works but the chat assistant replies with an error.

## 3. One-time setup

From the `hw4/` folder:

```bash
cp .env.example .env
```

Open `.env` and replace `your-portkey-key-here` with your real key. The other values are working defaults. `.env` is gitignored, so it never gets committed.

```bash
python3 -m venv backend/.venv && backend/.venv/bin/pip install -r requirements.txt
```

```bash
cd frontend && npm install
```

## 4. Run it (two terminals)

**Terminal 1: backend** (API on http://localhost:8000)

```bash
cd backend && source .venv/bin/activate && uvicorn main:app --reload --port 8000
```

With the virtual environment already active, this is simply `cd backend && uvicorn main:app --reload --port 8000`.

**Terminal 2: front end** (the shop on http://localhost:5173)

```bash
cd frontend && npm run dev
```

Open **http://localhost:5173**. Vite forwards `/api` and `/images` to the backend on port 8000, so start the backend first. If 5173 is busy, run `PORT=5174 npm run dev`.

### Quick checks
- http://localhost:8000/api/health shows the backend is up.
- http://localhost:8000/api/chat/status shows the models, every limit, and whether the key is configured (it never shows the key).
- In the shop, open the chat (bottom right) and ask *"What hoodies do you have?"*. You should get product cards.

### Try it
- **Browse:** Products page → search, category, size-in-stock and price filters, sort, and "Low stock" / "Sold out" badges.
- **Pop-up:** click a product. Sold-out sizes are greyed out, and you can click the photo to zoom to 175%.
- **Chat:**
  - *"Is the School of Engineering 1/4 zip in stock in S?"* → it says the size is sold out and offers alternatives.
  - With a product pop-up open: *"Do you have this in pink?"*
- **Accounts:** click the profile icon → **Create Account**. Test-account passwords are kept out of this repo. Logged-in shoppers' carts and chats are saved to their account.

---

## 5. Settings (`.env`)

| Variable | Default | Meaning |
|---|---|---|
| `PORTKEY_API_KEY` | *(required)* | Your Portkey key. |
| `PORTKEY_BASE_URL` | `https://api.portkey.ai/v1` | OpenAI-compatible gateway. |
| `FAST_MODEL` / `SMART_MODEL` | `gpt-6-luna` / `gpt-6-luna` | Simple questions go to fast (reasoning off). Multi-step questions go to smart (reasoning `medium`). |
| `MAX_TOOL_CALLS_PER_TURN` / `MAX_MODEL_REQUESTS_PER_TURN` | 8 / 8 | Per-message caps that stop tool loops. |
| `MAX_HISTORY_MESSAGES` | 10 | How many earlier messages the model sees. |
| `MAX_MESSAGE_CHARS` | 1000 | Longest chat message accepted. |
| `CACHE_TTL_SECONDS` | 60 | In-memory cache for catalogue and inventory. |
| `AUDIT_TRAIL_PATH` | `output/audit_trail.json` | The append-only agent audit log. |

`config.py` reads `.env` from `backend/`, then `hw4/`, then up to two parent folders. The first file that sets a value wins.

## 6. Learn more

- **`output/harness.md`** is the full reference. Start with **Start Here** for the request flow. Then:
  - §13: every model field;
  - §14: every tool;
  - §15: safety rules;
  - §16: specs, limits and run commands.
- **`output/design.md`** explains why things were built the way they were.
- **`output/app_check.html`** has a screenshot walkthrough. Open it in a browser from the `output/` folder so the images load.
- **`AI_prompts.md`** has the prompts behind each problem.

## Notes

- **Not in git:**
  - `.env`, which holds the API key;
  - `data/`, the database and product images;
  - `TEST_ACCOUNTS.md`, the local test passwords;
  - product-photo copies in `output/model_photo_sources/`;
  - `node_modules/`, `.venv/` and caches.
- **Third-party photos:** the homepage lifestyle and lookbook photos in `frontend/public/models/` come from yalebulldogblue.com and lesdeux.com. They're used for this class project only.
