# Campus Customs — Usability Improvements (Problem 9)

> **Status: BUILT and verified end to end (2026-10-06).** Each section says what we added, why it helps a shopper or the business, and **how a grader can see it** in the running app.

**Run the app** (two terminals):

```bash
cd backend && source .venv/bin/activate && uvicorn main:app --reload --port 8000
npm --prefix frontend run dev
```

Open the URL Vite prints (5173 or the next free port). Test accounts are in `TEST_ACCOUNTS.md`.

**Context from our data** (`data/campus_customs.db`):

- **Sold-out sizes are common.** 77 of 102 products have at least one sold-out size (145 of 612 size rows are at 0). Only 25 products have every size in stock.
- **The catalogue is large and flat.** 102 products across 6 garment types, priced from $32 to $98.

---

## Front end

### 1. Suggested-question chips in the chat panel

**What we added:**

- **3–4 tappable suggestion chips** above the chat's message box. They show when the chat is empty and after every agent reply, and hide while the agent is working. Tapping a chip **sends it as a message**.
- **The chips follow context:**

| Situation | Chips |
|---|---|
| Empty chat, guest | "What hoodies do you have?" · "Gifts under $50" · "Quarter-zips in size M?" · "When are you open?" |
| Empty chat, logged in | "What's in my cart?" · "What hoodies do you have?" · "Gifts under $50" · "When are you open?" |
| **A product pop-up is open** | The chips **name that product**: "Is the Sailing Left Chest Hoodie in stock in M?" · "What colors does the Sailing Left Chest Hoodie come in?" · "Show me items similar to the Sailing Left Chest Hoodie" |
| After search results | "Which of these are under $50?" · "Do any of these come in XL?" · "Show me the gray ones" · "Gifts under $50" |
| After a reply about one item | Follow-ups about that item |

- **Typing indicator:** animated dots plus "Campus Customs is typing…" in the chat, and "typing…" in the header, while the agent works.
- **Message box:** a multi-line text area. **Enter sends**, **Shift+Enter adds a new line**, and the box grows up to about 5 lines. Line breaks are kept in the sent bubble.
- **Style:** the chips use the site's Yale-blue outline style and fill blue on hover.

**Why it helps:**

- **Shopper:** removes the "blank box" problem, because people often don't know what the assistant can do. One tap is faster than typing, especially on a phone.
- **Shopper:** product-aware chips make the bot's page awareness visible. The shopper sees it already knows which item they're looking at.
- **Business:** more chat engagement leads to more product cards seen, which leads to more Put Into Cart. Chips also steer people to questions the agent answers well (stock, sizes, hours) instead of off-topic ones.

**How to see it:**

1. On any page, click the **round blue chat button** (bottom right). Four chips appear above the message box.
2. **Click "What hoodies do you have?"**. It's sent as your message, the chips disappear, and "Campus Customs is typing…" shows. When the reply arrives (with hoodie cards), new follow-up chips appear: "Which of these are under $50?", and so on.
3. Close the chat. Go to **Products**, click the **Sailing Left Chest Hoodie** card to open its pop-up, then open the chat again. The chips now name that hoodie. Click **"Is the Sailing Left Chest Hoodie in stock in M?"**; the answer is "Yes, M is in stock (25 available)".
4. In the message box, type `Thanks!`, press **Shift+Enter**, then type `What are your hours on Saturday?`. The box shows two lines. Press **Enter** to send both lines as one message.

---

### 2. Search, filters, sort and stock badges on the Products page

**What we added** (on the **Products** page):

- **Search box:** results update as you type, with a 250 ms delay. It uses the **same search engine as the chat agent**.
- **Category filter:** All · Hoodies · Crewnecks · T-Shirts · Quarter-Zips · Jackets & Fleece · Long Sleeve.
- **"Size in stock" filter:** S · M · L · XL. It shows only items you can actually buy in that size.
- **Sort dropdown:** Featured (the default, with sold-out items last) · Price: low to high · Price: high to low · Name: A to Z.
- **Also kept from the approved plan:** price bands (Under $40 · $40–$70 · Over $70), an "In stock only" toggle, a live product count, and "Clear filters".
- **Updates without reloading:** every change updates the results **instantly with no page reload** (client-side routing plus a fetch). The filters live in the URL (for example `/products?q=navy+hoodie&size=XL&sort=price_asc`), so views can be shared and the Back button works.
- **Inventory badge on each card,** from **real inventory data**, with at most one badge per card:
  - **"Sold out"** when the product's total across all sizes is **0**;
  - **"Low stock"** when the total is **under 5**;
  - otherwise **"Only 2 left in XL"** when one size has **3 or fewer** left, or **"Low stock in S, XL"** / **"Low stock in 3 sizes"** when several do;
  - **with a size filter on,** the badge talks only about **that size** (for example, with XL selected, only items low in XL are badged).
- **Backend:** every product from `GET /api/products` now includes **`total_in_stock`**, computed server-side from the `inventory` table. The same endpoint gained `category`, `min_price`, `max_price`, `size`, `in_stock`, and `sort` query parameters.
- **Single-item pop-up:** sold-out sizes stay **greyed out, struck through, and unclickable**, as before.

**Why it helps:**

- **Shopper:** 102 products in one grid is a lot to scroll. Search and filters get them to "navy hoodie in my size" in seconds. The size filter matters because 77 products are missing at least one size, so shoppers no longer open items only to find their size greyed out.
- **Shopper:** badges show scarcity **before** clicking, following our harness rule that stock-outs are shown clearly, never hidden.
- **Business:** fewer dead-end clicks, faster paths to things we can actually sell, and "Low stock" creates healthy urgency.

**How to see it:**

1. Click **Products** in the nav. The count reads "102 products".
2. Type **`berkeley`** in the search box. Without reloading, the grid narrows to **2 products** and the URL becomes `?q=berkeley`. Clear it, then type **`navy hoodie`**.
3. Click the size **XL** pill. The count updates to 19, and the URL gains `&size=XL`.
4. Click the **Hoodies** category pill, then choose **"Price: low to high"** in **Sort**. The cards re-order instantly, starting at $45.
5. Press the browser's **Back** button to step back through the filters. Click **"Clear filters"** to reset them.
6. **Badges** (real data):
   - With no filters, the first cards show **"Only 2 left in L"** on *2025 Yale Vs Harvard T Shirt* (L = 2), **"Only 2 left in XL"** on *Basic Hoodie Big Yale* (XL = 2), and **"Low stock in M, XL"** on *Benjamin Franklin T Shirt*.
   - Click the **XL** size pill: only items with 3 or fewer left in XL keep a badge (13 of 77).
   - The **"Sold out"** (total 0) and **"Low stock"** (total < 5) badges don't occur in today's data, since every total is 9 or more. To see them, run the backend against a **copy** of the database with a product zeroed:
     - `cp data/campus_customs.db /tmp/demo.db`
     - `sqlite3 /tmp/demo.db "update inventory set quantity=0 where product_id='2025-yale-vs-harvard-t-shirt'"`
     - in `backend/`: `CAMPUS_DB=/tmp/demo.db uvicorn main:app --port 8000`
     - The T-shirt then shows a black **"Sold out"** badge. Both badges were verified this way.
7. **Greyed-out sizes:** click **Sailing Left Chest Hoodie**. In the pop-up, size **L** is greyed out and can't be clicked, because it has 0 in stock.

---

## Agent / backend

### 3. `suggest_alternatives`: in-stock alternatives when a size is sold out

**What we added:**

- **New tool** `suggest_alternatives(product, size)` in `backend/tools.py`. It returns an **`AlternativesResult`** (`backend/models.py`) with:
  - **(a) `other_sizes_in_stock`:** the **same product in other sizes that are in stock**, nearest to the requested size first;
  - **(b) `similar_in_size`:** **up to 3 similar products in the same category** that **have the requested size in stock**. They're ranked by shared colors, theme (college or sport), tags, and closeness in price, and never include an item that's sold out in that size;
  - **`cards`:** the **same `ProductCard` list** the website renders (the original first, then the similar items), plus `why` (a short reason for each) and `has_alternative`.
- **The server guarantees the cards reach the page:** any cards `suggest_alternatives` returns are added to the reply, even if the agent forgets to list them.
- **Prompt rule** (`prompts/prompt.md`): **never just say "sold out", always offer an alternative if one exists.** The agent says the size is sold out, calls the tool, and offers both the other sizes and the similar items in the same reply.

**Why it helps:**

- **Shopper:** "Sold out" stops being a dead end. They see right away what they *can* buy in their size.
- **Business:** sold-out sizes are frequent (145 size rows at 0), so recovering even some of those into an in-stock purchase protects revenue.
- **Accuracy:** suggestions are ranked by code from the database, not invented by the model.

**How to see it** (real sold-out sizes in the current data):

1. Open the chat and type **`Do you have the Sailing Left Chest Hoodie in L?`** (L has 0 in stock).
2. Reply: "**Size L is sold out right now** in the Sailing Left Chest Hoodie. **M, XL, S, XXL, and XS** are available in that hoodie, or the **Squash Left Chest Hoodie**, **Crew Left Chest Hoodie**, and **Yale Mom Hoodie** have L in stock."
3. **Four cards** appear under the reply: the Sailing hoodie first, then the three similar hoodies. Click one of the alternatives; its pop-up shows **L available**.
4. Second example: type **`Do you have the Benjamin Franklin Fleece Jacket in XS?`**. XS is sold out, so the reply offers S, M, L, or XL, plus 3 other fleece jackets that have XS.
5. In `output/audit_trail.json`, these requests list `"tool_calls": ["lookup_product", "suggest_alternatives"]`.

---

### 4. Faster and cheaper: model routing, caching, limits, and an audit trail

**What we added:**

- **Model routing** (`agent.choose_route`):
  - **Simple questions** (greetings, a price or stock lookup, a named product, store hours, "what's in my cart?") go to the **cheap/fast model**: `FAST_MODEL` on `/chat/completions` with **reasoning off**.
  - **Multi-step or unclear questions** go to the **stronger model**: `SMART_MODEL` on `/responses` with **reasoning on**. These include comparisons, advice and gift questions, 3 or more constraints (for example "gray hoodie in XL under $70 for my dad"), several questions at once, and long messages.
  - **Fallback:** if a fast-tier run fails, it retries once on the smart tier.
- **Both model names live in `hw4/.env`** (`FAST_MODEL`, `SMART_MODEL`, `SMART_REASONING_EFFORT`; it was `backend/.env` before Problem 13) and are documented in **`hw4/.env.example`**. Per William's choice, both are `gpt-6-luna`; the tiers differ by API and reasoning. Change either name to switch models.
- **Caching:** catalogue **and** inventory lookups are cached in memory for **`CACHE_TTL_SECONDS=60`**. Stock answers can therefore be up to 60 seconds old; this is a deliberate speed trade-off. `db.invalidate_cache()` clears the cache after a data edit.
- **Limits per turn:**
  - **Tool calls:** at most **`MAX_TOOL_CALLS_PER_TURN=8`**, plus a cap of 8 model requests.
  - **History:** cut to the **last `MAX_HISTORY_MESSAGES=10`** messages on the server before it's sent to the model, for both guests and logged-in shoppers.
  - **Prompt rule:** browsing questions should answer from search results instead of looking up every item. The gift question went from 8 tool calls and about 14.6k input tokens to 1 tool call and about 8.4k.
- **Audit trail:** every chat request appends an entry to **`output/audit_trail.json`**, a valid JSON array with the newest entry last. Each entry has:
  - the timestamp, the user (id or "guest"), and a preview of the question;
  - **`tier`, `model`, `api`, `reasoning_effort`, `route_reason`**, and `fallback_to_smart`;
  - `elapsed_ms`, `tool_calls`, `history_messages_sent`, input and output tokens;
  - cache hits and misses, the cards shown, and the `outcome`.

  It holds no emails or passwords.
- **Status check:** `GET /api/chat/status` shows both tiers, the limits, the cache settings and counters, and the audit file path.

**Why it helps:**

- **Business (cost):** most shop questions are simple lookups. They now run on the cheap tier with no reasoning tokens, and the expensive tier is kept for questions that need it. The tool and history caps bound the worst-case cost of any one message.
- **Shopper (speed):** the fast tier and cached lookups reply sooner.
- **Accountability:** the audit trail shows exactly which model handled each request and why.

**How to see it:**

1. Open the chat and send these three messages:
   - **`Hi there!`**
   - **`How much is the Basic Hoodie Big Yale?`**
   - **`I need a gray hoodie in XL under $70 for my dad`**
2. Open **`output/audit_trail.json`**, newest entries at the bottom:
   - "Hi there!" → `"tier": "fast"`, `"api": "chat.completions"`, `"reasoning_effort": "none"`, `"route_reason": "simple question"`.
   - The Basic Hoodie price → `"tier": "fast"`, `"route_reason": "simple question (0 constraints, names a product)"`.
   - The gray hoodie gift → `"tier": "smart"`, `"api": "responses"`, `"reasoning_effort": "medium"`, `"route_reason": "4 constraints (price/size/color/type/topic)"`, `"tool_calls": ["search_products"]`.
3. **Caching:** within 60 seconds, ask something else. The new entry's `"cache"` shows `catalogue_hits` / `inventory_hits` instead of misses.
4. **History cap:** have a longer conversation (more than 10 messages). `"history_messages_sent"` never exceeds **10**.
5. **Live config:** visit **`http://localhost:8000/api/chat/status`** to see `routing.fast` / `routing.smart` (models from `.env`), `limits` (8 tool calls, 10 history messages), `cache.ttl_seconds: 60` with hit and miss counters, and `audit_trail`.
6. **Model names:** open **`hw4/.env`** (local only) and **`hw4/.env.example`** (in the repo) to see `FAST_MODEL` and `SMART_MODEL`.
