import json
import re
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
META_PATH = ROOT / "source-question-images.json"
OUT_PATH = ROOT / "source-answers.json"


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


def annotation_kind(value):
    if re.fullmatch(r"[Xx]|\d+", value.strip()):
        return "mark"
    return "comment"


def extract_answer_tokens(pdf_path):
    reader = PdfReader(str(pdf_path))
    if len(reader.pages) < 2:
        return []
    page = reader.pages[1]
    tokens = []
    for annot in page_annots(page):
        text = annot_text(annot)
        if not text:
            continue
        rect = [float(v) for v in annot.get("/Rect", [])]
        if len(rect) != 4:
            continue
        value = text.strip()
        tokens.append(
            {
                "text": value,
                "kind": annotation_kind(value),
                "x": (rect[0] + rect[2]) / 2,
                "y": (rect[1] + rect[3]) / 2,
                "rect": rect,
            }
        )
    return tokens


def main():
    meta = json.loads(META_PATH.read_text(encoding="utf-8-sig"))
    by_source = {}
    errors = []
    for item in meta["items"]:
        source = item["source"]
        if source in by_source:
            continue
        path = ROOT / source
        try:
            tokens = extract_answer_tokens(path)
            by_source[source] = tokens
        except Exception as exc:
            errors.append({"source": source, "error": type(exc).__name__ + ": " + str(exc)})
    OUT_PATH.write_text(json.dumps({"answers": by_source, "errors": errors}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"sources={len(by_source)} with_answers={sum(bool(v) for v in by_source.values())} errors={len(errors)}")


if __name__ == "__main__":
    main()
