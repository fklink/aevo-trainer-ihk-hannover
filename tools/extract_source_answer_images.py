import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "assets_answers"
META_PATH = ROOT / "source-question-images.json"


def annot_text(annot):
    for key in ("/Contents", "/T"):
        value = annot.get(key)
        if value:
            text = str(value).strip()
            if text and text.lower() != "navidlodhia":
                return text
    rc = annot.get("/RC")
    if rc:
        stripped = re.sub(r"<[^>]+>", " ", str(rc))
        stripped = re.sub(r"\s+", " ", stripped).strip()
        if stripped:
            return stripped
    return ""


def page_annots(page):
    annots = page.get("/Annots")
    if not annots:
        return []
    if hasattr(annots, "get_object"):
        annots = annots.get_object()
    return [ref.get_object() for ref in annots]


def load_font(size):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def draw_annotations(img, page):
    width, height = img.size
    media = page.mediabox
    page_width = float(media.width)
    page_height = float(media.height)
    scale_x = width / page_width
    scale_y = height / page_height
    draw = ImageDraw.Draw(img)

    for annot in page_annots(page):
        text = annot_text(annot)
        if not text:
            continue
        rect = [float(value) for value in annot.get("/Rect", [])]
        if len(rect) != 4:
            continue
        left, bottom, right, top = rect
        x = int(left * scale_x)
        y = int((page_height - top) * scale_y)
        rect_height = max(1, int((top - bottom) * scale_y))
        font_size = max(12, int(rect_height * 0.9))
        font = load_font(font_size)
        draw.text((x, y), text, fill=(0, 0, 0), font=font)


def main():
    meta = json.loads(META_PATH.read_text(encoding="utf-8-sig"))
    OUTPUT_DIR.mkdir(exist_ok=True)
    extracted = 0
    skipped = []

    for item in meta["items"]:
        source = ROOT / item["source"]
        target = OUTPUT_DIR / Path(item["image"]).name
        try:
            reader = PdfReader(str(source))
            if len(reader.pages) < 2 or not reader.pages[1].images:
                skipped.append({"source": item["source"], "reason": "no second-page image"})
                continue
            page = reader.pages[1]
            image = reader.pages[1].images[0]
            with Image.open(__import__("io").BytesIO(image.data)) as img:
                rendered = img.convert("RGB")
                draw_annotations(rendered, page)
                rendered.save(target)
            extracted += 1
        except Exception as exc:
            skipped.append({"source": item["source"], "reason": type(exc).__name__ + ": " + str(exc)})

    print(f"extracted={extracted} skipped={len(skipped)}")
    if skipped:
        (OUTPUT_DIR / "skipped.json").write_text(
            json.dumps(skipped, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
