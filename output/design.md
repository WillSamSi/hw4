# Campus Customs — Design Notes

This file records the design decisions behind changes to the app. It grows with each problem.

---

## Problem 10 — On-Model Photos for Recommended Items

### 1. Goal

Make some of the home page's recommended items ("Weather's Getting Cold, But We Keep You Warm") show **a person wearing the product**, the way real apparel shops do. The flat catalogue photos stay the source of truth for what the product looks like.

**Result:** **10 of the 12** carousel items now show an on-model photo. The two that don't are Yale Mom Hoodie and School of Music Fleece Sweater, which weren't in either batch.

### 2. Constraints we discovered (and how they shaped the design)

| Constraint | What we found | Design consequence |
|---|---|---|
| **Our Portkey key can't generate images** | Portkey's `/v1/models` lists `gpt-image-*`, FLUX, and so on, but that's Azure's general **catalogue**, not models our key can use. Every request from our key reaches only the **`gpt-6-luna` text** deployment (Azure replied that the image request was sent to `gpt-5.6-luna`). Image **edit** and **generate** calls on 5 image models all returned 400 errors, and nothing was billed. | Image generation can't run inside the app or the backend. We wrote `backend/scripts/generate_model_photos.py` anyway, so it works as soon as an image-capable key exists. |
| **Claude can't generate photos** | Claude (the coding assistant) reads and checks images but only outputs text and code. | We **split the work**: William generates images in **Google Gemini**, and Claude prepares inputs, writes prompts, **reviews every result**, and wires it into the site. |
| **AI image models garble logos and crests** | Small crests and lettering are where image models fail most. Seen here: a wrong Divinity crest, an added period in "YALE.", and a strap covering the lettering. | **A human-review step before anything ships.** Only photos marked `reviewed: true` appear on the site. |
| **Reference photos of other brands' products** | The Les Deux sweater photo William shared is a different product from ours. | Used **only as a style reference** (pose, backdrop), never as a product photo. |
| **Shoppers must not be misled** | An AI image can't be the definitive product photo. | Every on-model image is labelled **"AI-generated preview"**, and the **real photo is always first** in the pop-up. |

### 3. Pipeline (human-in-the-loop)

```
 catalogue photo (data/products/*.jpg)
        │  cleaned copy served by the API (black bars trimmed, squared)
        ▼
 Claude: pick items + write per-item prompts (garment, colors, exact lettering/crest, pose, backdrop)
        │  output/model_photo_sources/{PROMPTS.md, round2/PROMPTS_ROUND2.md, round2/REDO_*.md}
        ▼
 William: generate in Google Gemini (product photo [+ crest close-up] + prompt)
        ▼
 Claude: review against the real product (side-by-side close-ups of lettering + crest)
        ├─ ✅ matches        → save web copy + original, manifest reviewed: true → live
        ├─ ✏️ tiny flaw       → careful retouch (documented), keep the untouched original
        └─ ❌ wrong / covered → save as a rejected attempt, write a targeted redo prompt
```

**Prompt design choices:**

- **Same backdrop everywhere** (warm beige linen studio) so the photos read as one set and match William's style reference.
- **Every prompt names the exact graphics** (for example "white arched YALE", "red shield, white cross in a circle over an open book") and says *"Do not add, remove or change any text or logos."*
- **Left-chest logos:** angled and side poses tell the model to turn so the **wearer's left chest faces the camera**.
- **Props** (tote, backpack, cap) must be **plain**, with no other brands, and must **not cover any logo**.
- **Crest close-ups:** for detailed crests, a cropped and enlarged close-up is uploaded as a second reference. This fixed the Divinity crest.
- **Source photos:** round-2 sources were upscaled to 2048 px. The catalogue originals are only 650–970 px; upscaling gives a cleaner input but can't add detail.

### 4. Review results

| Product | Pose | Attempts | Outcome |
|---|---|---|---|
| District Vit Crewneck Vintage Bulldog | front | 1 | ✅ matches |
| Champion Reverse Weave Hoodie 1 | front | 1 | ✅ matches (arched YALE + Champion C on the sleeve) |
| Branford 1 4 Zip | front | 1 | ✅ matches |
| Divinity School Fleece Sweater | front | 2 | ❌ round 1 had the wrong crest (brick/checker shield) → ✅ round 2, using a crest close-up |
| Brooks Brothers Bomber Jacket Yale | three-quarter side, hand in pocket | 1 | ✏️ Gemini added a period ("YALE."). We **retouched** the 27-pixel dot to match the real "YALE"; the original is kept. |
| Super Heavyweight Crewneck Arched Yale Crest | hands in jeans pockets | 1 | ✅ matches |
| School of Art Fleece Sweater | tote bag | 1 | ✅ matches |
| Yale Law School 1 4 Zip | angled, hand in pocket | 1 | ✅ matches (minor: the crest's right half is dark green instead of black, barely visible at display size) |
| Berkeley 1 4 Zip | front, hand in pocket | 1 | ✅ product matches. Gemini left out the requested cap (a styling miss only). |
| Yale Sports Hoodie Hockey | backpack | 3 | ❌❌ the strap or hand covered the lettering ("ALE / OCKEY") → ✅ attempt 3, with the **bag carried by its handle at the side** |

**Lesson:** Gemini kept putting the backpack strap on the shoulder nearest the camera. Rewording "which shoulder" didn't fix it; **removing the shoulder strap from the pose** did.

### 5. Implementation

**Storage** (`data/model_photos/`):

```
data/model_photos/
├── <product_id>.jpg            # 1400 px web copy (the only file the site serves)
├── originals/                  # full-res Gemini output + rejected attempts, for provenance
│   ├── <product_id>.jpg
│   ├── divinity-school-fleece-sweater_round1-wrong-crest.jpg
│   ├── yale-sports-hoodie-hockey_attempt1-covered.jpg
│   └── yale-sports-hoodie-hockey_attempt2-covered.jpg
└── manifest.json               # one entry per product
```

**`manifest.json` entry:**

```json
{
  "product_id": "brooks-brothers-bomber-jacket-yale",
  "file": "brooks-brothers-bomber-jacket-yale.jpg",
  "original": "originals/brooks-brothers-bomber-jacket-yale.jpg",
  "generator": "Google Gemini, round 2 (generated by William from …)",
  "received": "2026-10-06",
  "pose": "three-quarter side, hand in pocket",
  "retouched": true,
  "reviewed": true,
  "review_note": "Matches after a small retouch: …",
  "attempts": ["… (only when more than one try was needed)"]
}
```

**Backend:**

| Piece | File | Notes |
|---|---|---|
| `Product.model_image_url` | `backend/models.py` | `str \| None`, set **only** for photos that pass review |
| `_load_model_photos()` | `backend/db.py` | Reads `manifest.json` and returns a URL only if `reviewed: true` **and** the file exists. Cached with the catalogue (`CACHE_TTL_SECONDS`, 60 s). |
| Static mount `/images/on-model` | `backend/main.py` | Serves `data/model_photos/`. It's mounted before the `/images/{filename}` route, which serves the cleaned catalogue photos. |
| `generate_model_photos.py` | `backend/scripts/` | Generates through the API directly (`images.edit`, `input_fidelity="high"`). It's unused because of the key limitation, but ready if the key changes. |

**Front end:**

| Where | Behavior |
|---|---|
| Product card (home carousel + Products page), `ProductCard.tsx` | Shows the **on-model photo by default** and **cross-fades to the real product photo on hover or keyboard focus**. A small **"AI-generated preview"** label sits bottom-right and hides on hover. Stock badges still show. |
| Product pop-up, `ProductModal.tsx` | Gallery = **[real product photo, on-model photo]**, with the real photo first. The on-model view carries the caption *"AI-generated preview · see the first photo for the exact product"*. |
| Types, `types.ts` | `Product.model_image_url?: string \| null` |

**Adding or replacing a photo:**

1. Put the reviewed image in `data/model_photos/<product_id>.jpg`.
2. Add or update its manifest entry with `"reviewed": true`.
3. It goes live within 60 s (the cache TTL), with no code change.

To pull a photo, set `"reviewed": false`.

### 6. Why these choices

- **Gate on `reviewed`, not on the file existing.** Rejected or held renders can sit in the folder for the record without any risk of showing up on the site.
- **The real photo comes first in the pop-up.** The pop-up is where shoppers decide on size and buy, so the accurate image leads. The on-model photo is for browsing and inspiration.
- **Hover-swap on cards.** Shoppers get both the lifestyle feel and the exact product without opening the pop-up.
- **Clear AI labelling.** Honest to shoppers, and consistent with the harness rule never to misrepresent products.
- **Stored with the data, not in `frontend/public/`.** Product imagery belongs with the catalogue and is served by the backend like the other product images, so a future admin tool or the agent could use it.

### 7. Limitations and next steps

- **Legal:** these are AI renders of real Yale-branded products. They're fine for this class project; a real store would need licensing and brand approval for marks and crests.
- **Small details:** small crest details can still be slightly off (Law School crest color), so human review remains essential.
- **Coverage:** 2 carousel items still use flat photos (Yale Mom Hoodie, School of Music Fleece Sweater), and the other ~90 catalogue items have none.
- **Automation:** an image-capable Portkey key would let `generate_model_photos.py` batch-generate. Claude could then pre-screen results automatically by comparing lettering and crests, leaving final approval to a human.

---

## Sign-Up Promo Label (feature request, no problem number)

### Goal
Invite visitors to create an account with a small floating offer: **"Sign up now, and receive 15% Off on your first purchase."**

### Behavior
| Rule | Decision | Why |
|---|---|---|
| **Where** | Fixed to the **right edge, vertically centered**, on **Home (`/`) and Products (`/products`)** only | As requested; it stays out of the nav (top) and the chat button (bottom-right). |
| **Not on the pop-up** | Hidden while a **product pop-up** is open (and while the sign-up pop-up is open); it reappears when they close | As requested; a promo shouldn't interrupt someone choosing a size. |
| **Who sees it** | **Guests only**, hidden once logged in | Logged-in shoppers already have an account, and the offer is for new sign-ups. |
| **Click** | Opens the existing **Create Account** pop-up, whose subtitle becomes "…get 15% off your first purchase" | Reuses the existing sign-up flow; the offer is confirmed at the moment of signing up. |
| **Dismiss** | A small **×** hides it for the rest of the **browser session** (`sessionStorage`) | Not nagging, but it can return on a later visit. |
| **Look** | A Yale-blue card with a gold "15% OFF" badge; it slides in from the edge after page load and **lifts out slightly on hover or focus** | The "hovering" feel requested, matching the site's colors and type. Stacking: above page content, below the nav, pop-ups, and chat. |

### Scope boundaries
- **Page-only:** the chat agent is **not** told about the offer. Its prompt still says *never mention discounts*. A draft that added the offer to the prompt was reverted at William's request.
- **Not yet applied:** there's no checkout, so the 15% isn't calculated or stored anywhere. When checkout is built, it needs a "first order" check per account (for example a `first_order_discount_used` flag or an orders table). The copy lives in one place (`frontend/src/store.ts → PROMO`), so the percentage and wording can change without touching components.

### Files
- `frontend/src/components/PromoTab.tsx`: the label, its visibility rules, and opening the sign-up pop-up.
- `frontend/src/components/AuthModal.tsx`: an optional `promo` prop for the offer subtitle.
- `frontend/src/store.ts`: the `PROMO` constant (percentage and label text).
- `frontend/src/App.tsx`: mounts `<PromoTab />` app-wide; the component decides where to show.
- `frontend/src/index.css`: the `.promo-tab` styles.

### Verified (2026-10-06)
- **Placement:** shown on Home and Products, centered vertically (384 px in a 768 px window).
- **Pop-ups:** hidden while a product pop-up is open and back after closing it.
- **Sign-up:** clicking it opens Create Account with the offer subtitle.
- **Dismiss:** × hides it for the session, including on Home.
- **Login:** hidden when logged in as Test User, and back after logging out.

---

## Agent Design: Hierarchy Decision and Fact-Checker (`v2-fact-check`)

### Decision
- **No agent hierarchy for now.** Facts like stock and product details come from deterministic tools. A "stock agent" or "product agent" would add an LLM call in front of a database query with no accuracy gain.
- **Planned order:**
  1. **E, fact-checker:** done, below.
  2. **D, direct answers for simple questions:** next.
  3. **B, specialist agents:** when checkout or account changes arrive and need isolated permissions.
  4. **C, orchestrator:** only for genuine multi-step planning.
- **Full reasoning, baseline, and measurement plan:** harness §10.

### Why the fact-checker first
The core rule of the shop chatbot is **never invent prices or quantities**. The prompt asks for this; the fact-checker **enforces it in code**. It's deterministic: it adds no model call when the reply is right and adds no new failure modes.

### How it works
- **Claims:** regexes find `$` amounts and stock-count phrases in the reply, ignoring things like "57 Broadway", "10 AM", "27 hoodies" and "1/4 zip".
- **Facts:**
  - every `price`, `quantity`, `total_in_stock`, `size_quantity`, `qty`, and `cart_subtotal` value from this turn's tool results;
  - price × 2–10 (line totals);
  - numbers the shopper typed, such as a budget.
- **On a mismatch** (decided by William: "retry once, then fall back to the DB"):
  - **Retry** on the same tier with a correction note, then re-check.
  - If it's still wrong, send a **database-built reply** listing each product's real price and in-stock sizes.
- **Audit:** every entry gets `fact_check.status` (`pass`, `no_claims`, `fixed_by_retry`, or `fallback`) and the flagged texts, so behavior in production is measurable.

### Measured result (harness §10.6)
- **Same benchmark:** v1 and v2 were each run on the same 10 questions, and both scored **10/10 correct**.
- **Fact-check outcome:** 5 replies were checked and all passed; there were **0 false alarms and 0 retries**.
- **Overhead:** **0.027 ms** per reply.
- **Planted errors:** caught in an offline scripted test, through both the retry path and the fallback path.
- **Decision:** keep it.

### Files
- `backend/factcheck.py`: claim extraction, fact collection, comparison, and the correction prompt.
- `backend/agent.py`: `run_chat` runs the check, the retry and `factcheck_fallback()`; the audit gains `fact_check` and `fast_tier_error`.
- `backend/scripts/run_benchmark.py`: the 10-question benchmark against the live backend.
- `backend/scripts/audit_summary.py`: compares runs by `agent_version` and tier.
- `backend/config.py`, `backend/.env`: `AGENT_VERSION` (now `v2-fact-check`).

### Limitations
- **Only numbers are checked.** It doesn't verify colors, sizes named without counts ("M is available"), or descriptions. Those still rely on the prompt rules and tool use.
- **Phrasing coverage:** stock phrasing outside the regex patterns (for example "a couple left") isn't checked. If the audit shows misses, extend the patterns.


---

## Product Image Zoom in the Pop-Up (feature request, no problem number)

### Goal
Let shoppers inspect fabric, print, and stitching up close in the single-item pop-up without leaving it.

### Behavior
- **Hover:** the photo shows a `zoom-in` (+) cursor.
- **Click:** zooms to **175%** (`ZOOM = 1.75`), centred on the clicked spot. The cursor becomes `zoom-out` (−).
- **Move while zoomed:** the magnified area follows the pointer. The point under the cursor stays under the cursor, so moving toward an edge reveals that edge.
- **Click again:** zooms back out.
- **Esc:** the first press zooms out (the event is stopped so the pop-up stays open), and the second closes the pop-up as before.
- **Thumbnails:** switching between the flat photo and the on-model photo always starts un-zoomed.
- **Keyboard and touch:**
  - The frame is a focusable `role="button"` with `aria-pressed` and a label that flips between "Zoom in…" and "Zoom out…". Enter/Space toggles zoom, centred.
  - A tap toggles. A drag of more than 6 px pans instead of toggling, and `touch-action: none` while zoomed stops the page from scrolling.

### How it works (and why)
- **CSS transform with `transform-origin`, not a second high-res image or a canvas.** The photo is scaled with `transform: scale(1.75)`, and `transform-origin` is set to the pointer's position as a percentage of the frame.
- **Why the pan follows the pointer:** with origin at (x%, y%), that point is fixed under scaling, so the area under the cursor is always the area being magnified. At 0% or 100% the photo's edge lines up with the frame's edge, so no blank space ever shows.
- **Why this approach:**
  - No extra image requests are needed: it uses the same cleaned `/images/...` file already loaded.
  - It's GPU-composited, so it's smooth.
  - It's about 70 lines in one component.
- **Clipping:** the photo is wrapped in a `.zoom-frame` with `overflow: hidden`, so the magnified photo stays inside the left column and never covers the details.
- **Transition:** a 0.25 s ease on `transform` makes zooming in and out feel smooth. Origin changes during panning apply instantly, so the pan doesn't lag.
- **Pointer events rather than mouse events:** one code path covers mouse, pen, and touch.
- **175% is the requested level.** The photos are about 1000 px or more, and the pop-up shows them at roughly 400–600 px, so 175% stays sharp rather than pixelated.

### Files
- `frontend/src/components/ZoomImage.tsx` (new): zoom state, origin tracking, keyboard handling, and tap-versus-drag.
- `frontend/src/components/ProductModal.tsx`: the gallery renders `<ZoomImage>` instead of a plain `<img>`.
- `frontend/src/index.css`: `.zoom-frame` (clip, cursors, focus ring, transition).

### Verified (2026-10-07, Browser pane, Champion Reverse Weave Hoodie)
| Check | Result |
|---|---|
| Hover cursor | `zoom-in` ✅ |
| Click at (30%, 35%) | `scale(1.75)`, origin `30% 35%`, cursor `zoom-out`. The screenshot shows the YALE crest magnified and clipped to the frame ✅ |
| Move to (80%, 70%) while zoomed | Origin follows to `80% 70%` ✅ |
| Drag (more than 6 px) | Stays zoomed and pans ✅ |
| Click again | `none`, cursor back to `zoom-in` ✅ |
| Esc while zoomed | Zooms out, and the pop-up stays open ✅ |
| Switch to the on-model thumbnail while zoomed | Resets to un-zoomed ✅ |
| `npm run build` and lint | Clean ✅ |

### Limitations
- Zoom is fixed at 175%, with no scroll-wheel or pinch zoom levels, as requested.
- On touch screens, the "+/−" cursors don't exist. Tap and drag give the same result.

---

## Problem 12: Append-Only Audit Log of Agent Steps

### Goal
Record what the agent actually did on every turn: each tool it called, with short arguments and results, why the run stopped, who asked, and which model answered. The record must be a log that can't be rewritten.

### Where it's hooked in, and why there
- **`run_chat()` in `agent.py`, in one `finally:` block.** Every agent run goes through `run_chat`, so this is the only place that sees all of a turn's runs: the fast try, the smart fallback and the fact-check retry. The `finally` covers normal replies, limit hits, declines and crashes alike.
- **Built from the run's messages, not from the tools.** Logging inside each tool would miss tools added later, couldn't see the stop reason, and would mix auditing with business logic.
- **`capture_run_messages()` rather than `result.new_messages()`.** When a run hits the tool-call limit or errors, there's no result object, but the captured list still holds every step up to that point. Those are exactly the runs an auditor most wants to see.

### Key decisions
- **Two entry types in one list.** There are per-`step` entries (what was asked for) and a per-`run` summary (the existing routing, cost and fact-check data, plus `run_id`, `attempts` and `stop_reason`). One `run_id` ties them together. This keeps the file a single valid JSON list, as required, and lets the existing `audit_summary.py` keep working by filtering on `type`.
- **`final_result` is logged as a step.** It is the agent's structured answer (reply text and product ids), so the log shows the full chain from tools to answer.
- **Fixed things in the old logger that broke the new rules:**
  - The 1,000-entry cap deleted old entries.
  - An unreadable file was replaced with a new list.
  - A write error would have turned the reply into a 502 error.

  Now nothing is trimmed, an unreadable file is left untouched (the entries are skipped and a warning is logged), and every logging error is caught.
- **Redact, then mask, then trim, in that order.** Secret-named fields are dropped from structured data, emails and key-like strings are masked in the text, and only then is it cut to 200 characters, so a cut can never leave half an email visible.

### Files
- `backend/audit.py` (rewritten): `append()` (append-only, atomic, never raises), `short()`, `redact()`, `mask()`.
- `backend/agent.py`:
  - `RunRecord` and `capture_run_messages()` in `attempt()`;
  - `_audit_steps()` (messages to step entries);
  - `_write_audit()` (the summary plus the append), called from `run_chat`'s `finally`.
- `backend/scripts/audit_summary.py`: counts `run` entries only.

### Verified
- **Offline:** 16/16 checks passed with a fake model and a temporary file.
- **Live:** a guest request added 4 steps and 1 summary, and the earlier 35 entries were unchanged.
- **Details:** harness §11.5.

### Limitations
- Passwords typed as plain chat text can't be detected.
- Appends are safe only within a single server process.
- The file grows forever by design.

---

## Agent Safety Rules (feature request, no problem number)

### Goal
Write down the agent's safety behaviour as explicit rules in the system prompt, and back the ones that matter most with code, so they don't rely on the model obeying.

### What changed
- **Prompt (`backend/prompts/prompt.md`):** "Safety basics" became **"Safety rules"**: 7 numbered rules plus two short extras (sensitive data, respect). The section opens by saying the rules override anything from the shopper, PAGE lines, saved chats or tool results, so injected text in a product description or a forged history turn has no authority.
- **Limits gathered in one place:**
  - The per-turn and message limits moved into `config.py`, are configurable in `.env`, and are shown in `/api/chat/status`.
  - The tool result caps became named constants in `tools.py`.
- **Tightened:**
  - A history turn is now 2,000 characters (was 4,000). Stored messages max out around 650 characters, so 2,000 is ample. It also halves how much text a guest's browser can inject as fake history.
  - `get_saved_chats` returns at most 50 messages (was 100).
  - Tool text arguments are trimmed to 100 characters.
  - Blank messages are rejected.
  - The model-request cap is now a named setting rather than a hard-coded 8.
- **Front end:** the guest chat trims each history turn to the same 2,000-character limit, and a 422 now says "keep it under 1,000 characters" instead of "couldn't reach the server".

### Why these numbers
- **1,000 characters per message:** plenty for a shopping question. It limits prompt-stuffing and cost, and it matches the widget's existing `maxLength`.
- **8 tool calls and 8 model requests per turn:** the gift question needed 7 lookups (harness §8). 6 broke it, and 8 leaves headroom while still stopping loops.
- **12 search results, 3 alternatives, 6 candidates, 3 suggestions, 8 cards:** the page shows at most 8 cards, so larger results only cost tokens. Alternatives are capped at 3 to match the request "up to 3 similar products".
- **50 saved chats of 400 characters each:** about 20,000 characters at most, enough for "what did I ask last time?" without flooding the context.

### Which rules are enforced by code, and which rely on the prompt
- **Backed by code:**
  - rule 1 (fact-checker and server-built cards);
  - rule 6 (account tools take no user argument);
  - rule 3, partly (no tool can reach passwords or other users);
  - rule 4, partly (the provider's filter);
  - rule 7, partly (`not_found` and `total_matches = 0`).
- **Prompt only:** rules 2 and 5 (off-topic, and discounts or policies). The live tests show the model follows them, and the audit log will surface any lapses.

### Verified (2026-10-07)
- **Offline:** 9/9 limit checks passed.
- **Live:** 9 rule questions were all handled correctly, including two role-change attempts that got past the provider's filter and were refused by the prompt rules. Details are in harness §12.3.

### Files
- `backend/prompts/prompt.md`
- `backend/config.py`
- `backend/models.py`
- `backend/history.py`
- `backend/agent.py`
- `backend/tools.py`
- `backend/main.py`
- `backend/.env.example`
- `frontend/src/components/ChatWidget.tsx`

---

## Harness Documentation: Reference Sections (feature request, no problem number)

### Goal
Make `output/harness.md` understandable to someone who has never seen the project, without losing the build log.

### Decisions
- **Kept the problem-by-problem log (§1–12) and added a reference layer:**
  - a **Start Here** block at the top: what the project is, a "need → section" map, and the **request flow** walkthrough;
  - four reference sections at the end: **§13 Model Fields**, **§14 Tools and Abilities**, **§15 Safety Rules**, **§16 Specs & How to Run**.

  The log explains *why* things are the way they are; the reference explains *what* they are now.
- **A real example for the request flow.** It follows the live 2026-10-07 audit run ("School of Engineering 1/4 zip in size S?") through `search_products` → `lookup_product` → `suggest_alternatives` → `final_result`, so every step can be checked against `output/audit_trail.json`.
- **Real values only.** Every number in §13–16 was read from the code: `config.py`, `tools.py` constants, `models.py` field limits, `agent.py` routing rules, `vite.config.ts`, and `history.py`.
- **Stale lines fixed in place, not deleted:**
  - the `/api/chat/status` description;
  - the `tools.py` list in §4.1;
  - the search tool's return type and the missing `suggest_alternatives` in §4.4;
  - §5.1's outdated "confirm every search result with `lookup_product`";
  - a note that §4.3's single-model setup became two tiers;
  - a table row missing its closing `|`.

---

## Problem 13: Publish to GitHub (`hw4/`, public repo)

### Goal
Put all the work in a `hw4/` folder and publish it as a **public** GitHub repo that anyone can run, without leaking the API key, the database, product images, or test passwords.

### What changed
- **Folder:** everything moved from the homework folder into **`hw4/`**:
  - `AI_prompts.md`, `backend/`, `frontend/` and `output/`;
  - plus local-only `data/`, `TEST_ACCOUNTS.md` and `joke.txt`.
- **Root files:**
  - **`requirements.txt`**: moved from `backend/`, and now **pinned** to the tested versions (FastAPI 0.142.2, pydantic-ai-slim 2.54.0, …). The virtual environment was rebuilt from it to prove it installs cleanly.
  - **`.env.example`**: a placeholder key (`your-portkey-key-here`) and default settings only.
  - **`.gitignore`** and **`README.md`**.
- **The `.env` file:** the real `.env` moved to `hw4/.env` and is gitignored.
- **API key lookup:** `config.py` now reads `backend/.env`, then `hw4/.env`, then **two** parent folders. William's key stays in `AI Foundation/.env`, which is now two levels up, and never enters the repo.
- **Clear error for a missing data pack:** if `data/campus_customs.db` or `data/products/` is missing, `main.py` stops with a clear message instead of a stack trace.

### Kept out of git, and why
| Path | Why |
|---|---|
| `.env`, `.env.*` (except `.env.example`) | Real settings and key |
| `data/`, `*.db` | The local-only data pack: database (with password hashes) and product images |
| `TEST_ACCOUNTS.md` | Test-account passwords |
| `output/model_photo_sources/**/*.jpg` | Copies of product photos used as image-generation sources (the "no product images" rule). The prompt `.md` files and style-reference PNGs are kept. |
| `.venv/`, `node_modules/`, `__pycache__/`, `backend/.image_cache/`, `frontend/dist/` | Rebuildable |
| `.DS_Store`, `.claude/`, `*.tmp` | Local and editor files |

### Decision: third-party homepage photos
`frontend/public/models/` holds 7 photos from yalebulldogblue.com and lesdeux.com. Asked whether to keep them local or publish, **William chose to push them anyway**, so the cloned site looks complete. The README notes their source and class-only use.

### Checks before pushing
- **Forbidden files:** none staged (`.env`, `.db`, `data/`, `TEST_ACCOUNTS.md`, product copies).
- **Contents:** every staged file was scanned. There was no test password, no Portkey key prefix, no GitHub token, no `sk-` key and no password hash. `.env.example` has only the placeholder.
- **The app runs from `hw4/`:** 102 products, images served, and a live chat answer of "$68.00" for the Basic Hoodie Big Yale.
