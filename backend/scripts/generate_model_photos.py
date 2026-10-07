"""Generate AI on-model photos for a few products (Problem 10).

Takes each product's real catalogue photo (the cleaned copy the API serves) and asks an
image-edit model, via Portkey, to show a person wearing that exact garment. Results go to
data/model_photos/<product_id>.jpg plus manifest.json; the API then exposes them as
Product.model_image_url. Every image is labelled "AI-generated preview" in the UI and
must be reviewed against the real product before it's kept.

Run from backend/ (costs one image generation per product):
    .venv/bin/python scripts/generate_model_photos.py district-vit-crewneck-vintage-bulldog ...
"""

from __future__ import annotations

import base64
import io
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402  (loads .env, including PORTKEY_API_KEY)
from openai import OpenAI  # noqa: E402
from PIL import Image  # noqa: E402

from db import ROOT, get_product  # noqa: E402

IMAGE_MODEL = os.getenv("IMAGE_MODEL", "gpt-image-2")
OUT_DIR = ROOT / "data" / "model_photos"
MANIFEST = OUT_DIR / "manifest.json"
CLEAN_DIR = config.BACKEND / ".image_cache"

PROMPT = (
    "Studio fashion photo for a university merch shop. A friendly young adult model stands facing the camera, "
    "wearing EXACTLY the garment in the reference image: same {kind}, same color ({colors}), and the same graphics, "
    "lettering, crest and logo placement, reproduced faithfully. Do not add, remove or change any text or logos on the "
    "garment. Plain neutral trousers. Warm beige linen studio backdrop, soft even lighting, framed from mid-thigh up, "
    "garment fully visible and centered. Photorealistic."
)


def generate(product_id: str, client: OpenAI) -> dict:
    p = get_product(product_id)
    if p is None:
        raise SystemExit(f"Unknown product_id: {product_id}")
    src = CLEAN_DIR / Path(p.image_url).name
    if not src.exists():
        raise SystemExit(f"Cleaned photo missing ({src}); open /images/{src.name} once via the API first.")

    prompt = PROMPT.format(kind=p.garment_type, colors=", ".join(p.colors[:3]) or "as shown")
    started = time.perf_counter()
    with open(src, "rb") as f:
        result = client.images.edit(
            model=IMAGE_MODEL,
            image=f,
            prompt=prompt,
            size="1024x1024",
            quality="high",
            input_fidelity="high",  # keep the garment's logos/lettering as close to the input as possible
        )
    png = base64.b64decode(result.data[0].b64_json)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{product_id}.jpg"
    Image.open(io.BytesIO(png)).convert("RGB").save(out, "JPEG", quality=88)
    return {
        "product_id": product_id,
        "name": p.name,
        "file": out.name,
        "source_photo": src.name,
        "model": IMAGE_MODEL,
        "prompt": prompt,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seconds": round(time.perf_counter() - started, 1),
        "reviewed": False,  # set true after checking it matches the real product
    }


def main(ids: list[str]) -> None:
    client = OpenAI(api_key=os.environ["PORTKEY_API_KEY"], base_url=config.PORTKEY_BASE_URL)
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    for pid in ids:
        print(f"Generating {pid} with {IMAGE_MODEL}…", flush=True)
        entry = generate(pid, client)
        manifest[pid] = entry
        MANIFEST.write_text(json.dumps(manifest, indent=2))
        print(f"  saved data/model_photos/{entry['file']} in {entry['seconds']}s")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    main(sys.argv[1:])
