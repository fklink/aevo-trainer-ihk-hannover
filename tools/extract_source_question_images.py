import json
from pathlib import Path

from PIL import Image
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "quelle" / "Prüfungsfragen HF bezogen"
OUTPUT_DIR = ROOT / "assets_extra"
META_PATH = ROOT / "source-question-images.json"


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    files = sorted({path.resolve(): path for path in SOURCE_ROOT.rglob("*") if path.is_file() and path.suffix.lower() == ".pdf"}.values())
    items = []
    skipped = []
    next_id = 49

    for pdf_path in files:
        try:
            reader = PdfReader(str(pdf_path))
            if not reader.pages or not reader.pages[0].images:
                skipped.append({"path": str(pdf_path.relative_to(ROOT)), "reason": "no first-page image"})
                continue
            image = reader.pages[0].images[0]
            target = OUTPUT_DIR / f"q{next_id:03d}.png"
            with Image.open(__import__("io").BytesIO(image.data)) as img:
                img.convert("RGB").save(target)
            items.append(
                {
                    "id": next_id,
                    "source": str(pdf_path.relative_to(ROOT)).replace("\\", "/"),
                    "image": str(target.relative_to(ROOT)).replace("\\", "/"),
                    "category": str(pdf_path.parent.relative_to(SOURCE_ROOT)).replace("\\", "/"),
                    "title": pdf_path.stem,
                }
            )
            next_id += 1
        except Exception as exc:
            skipped.append({"path": str(pdf_path.relative_to(ROOT)), "reason": type(exc).__name__ + ": " + str(exc)})

    META_PATH.write_text(
        json.dumps({"items": items, "skipped": skipped}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"extracted={len(items)} skipped={len(skipped)}")


if __name__ == "__main__":
    main()
