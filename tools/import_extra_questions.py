import json
import re
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

from import_ocr import clean_text, group_rows, split_ocr


ROOT = Path(__file__).resolve().parents[1]


def points_from_text(text):
    match = re.search(r"erhalten Sie\s+(\d+)\s+von\s+100\s+Punkten", text or "", re.IGNORECASE)
    return int(match.group(1)) if match else 1


def infer_type(title, text):
    haystack = f"{title} {text}".lower()
    if any(word in haystack for word in ["reihenfolge", "nummerieren", "richtige reihenfolge"]):
        return "sequence"
    if any(word in haystack for word in ["raster", "zuordnen", "ordnen sie", "zuordnung"]):
        return "sequence"
    return "choice"


@lru_cache(maxsize=None)
def detect_answer_boxes(image_path):
    image_path = Path(image_path)
    image = Image.open(image_path).convert("L")
    width, height = image.size
    arr = np.array(image)
    mask = arr < 70
    x_start = int(width * 0.55)
    seen = np.zeros(mask.shape, dtype=bool)
    boxes = []
    for y in range(height):
        for x in range(x_start, width):
            if not mask[y, x] or seen[y, x]:
                continue
            stack = [(x, y)]
            seen[y, x] = True
            min_x = max_x = x
            min_y = max_y = y
            count = 0
            while stack:
                cx, cy = stack.pop()
                count += 1
                min_x, max_x = min(min_x, cx), max(max_x, cx)
                min_y, max_y = min(min_y, cy), max(max_y, cy)
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if x_start <= nx < width and 0 <= ny < height and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((nx, ny))
            box_w = max_x - min_x + 1
            box_h = max_y - min_y + 1
            ratio = box_w / box_h if box_h else 0
            if 14 <= box_w <= 90 and 14 <= box_h <= 90 and 0.55 <= ratio <= 1.55 and count >= 60:
                boxes.append(
                    {
                        "cx": (min_x + max_x) / 2,
                        "cy": (min_y + max_y) / 2,
                        "bbox": [min_x, min_y, max_x, max_y],
                    }
                )
    deduped = []
    for box in sorted(boxes, key=lambda item: (item["cy"], item["cx"])):
        if not deduped or abs(deduped[-1]["cy"] - box["cy"]) > 6 or abs(deduped[-1]["cx"] - box["cx"]) > 6:
            deduped.append(box)
    return deduped, width, height


def token_to_image_y(token_y, image_height):
    media_height = 824.76
    return (media_height - token_y) / media_height * image_height


def derive_correct(meta_item, qtype, row_count, source_answers):
    tokens = source_answers.get(meta_item["source"], [])
    if not tokens or row_count <= 0:
        return None
    boxes, image_width, image_height = detect_answer_boxes(ROOT / meta_item["image"])
    if not boxes:
        return None
    right_column = [
        box for box in boxes
        if box["cx"] >= image_width * 0.78
        and (box["bbox"][2] - box["bbox"][0] + 1) >= 25
        and (box["bbox"][3] - box["bbox"][1] + 1) >= 25
    ]
    if len(right_column) >= min(row_count, 1):
        boxes = right_column
    boxes = sorted(boxes, key=lambda item: (item["cy"], -item["cx"]))
    if len(boxes) >= row_count:
        # Keep the actual answer column, not text fragments detected elsewhere.
        boxes = boxes[-row_count:] if boxes[0]["cy"] < image_height * 0.25 else boxes[:row_count]
        boxes = sorted(boxes, key=lambda item: item["cy"])
    if not boxes:
        return None

    if qtype == "choice":
        correct = []
        for token in tokens:
            if not re.search(r"[Xx]", token.get("text", "")):
                continue
            token_y = token_to_image_y(float(token["y"]), image_height)
            nearest_index = min(range(len(boxes)), key=lambda i: abs(boxes[i]["cy"] - token_y))
            correct.append(nearest_index + 1)
        return sorted(set(correct)) or None

    correct = [None] * row_count
    for token in tokens:
        match = re.search(r"\d+", token.get("text", ""))
        if not match:
            continue
        token_y = token_to_image_y(float(token["y"]), image_height)
        nearest_index = min(range(len(boxes)), key=lambda i: abs(boxes[i]["cy"] - token_y))
        if nearest_index < row_count:
            correct[nearest_index] = int(match.group(0))
    return correct if any(value is not None for value in correct) else None


def visible_answer_box_count(meta_item):
    boxes, image_width, _ = detect_answer_boxes(ROOT / meta_item["image"])
    right_column = [
        box for box in boxes
        if box["cx"] >= image_width * 0.78
        and (box["bbox"][2] - box["bbox"][0] + 1) >= 25
        and (box["bbox"][3] - box["bbox"][1] + 1) >= 25
    ]
    return len(right_column) or len(boxes)


def main():
    questions_path = ROOT / "questions.json"
    meta = json.loads((ROOT / "source-question-images.json").read_text(encoding="utf-8"))
    ocr_items = json.loads((ROOT / "ocr-extra.json").read_text(encoding="utf-8-sig"))
    source_answers = json.loads((ROOT / "source-answers.json").read_text(encoding="utf-8"))["answers"]
    meta_by_name = {Path(item["image"]).name: item for item in meta["items"]}

    data = json.loads(questions_path.read_text(encoding="utf-8"))
    base_questions = [question for question in data["questions"] if int(question["id"]) <= 48]
    imported = []

    for item in ocr_items:
        meta_item = meta_by_name.get(item["name"])
        if not meta_item:
            continue
        prompt, answer_lines = split_ocr(item.get("lines") or [])
        if not prompt:
            prompt = clean_text(item.get("text", ""))
        qtype = infer_type(meta_item["title"], item.get("text", ""))
        answer_box_count = visible_answer_box_count(meta_item)
        question = {
            "id": int(meta_item["id"]),
            "title": f"Zusatzfrage {int(meta_item['id']) - 48}: {meta_item['title']}",
            "points": points_from_text(item.get("text", "")),
            "type": qtype,
            "image": meta_item["image"],
            "question": prompt,
            "ocrText": clean_text(item.get("text", "")),
            "ocrLines": item.get("lines") or [],
            "source": meta_item["source"],
            "category": meta_item["category"],
            "solutionAvailable": False,
        }
        if qtype == "choice":
            expected = answer_box_count or len(answer_lines)
            options = group_rows([line for line in answer_lines if line], expected)
            question["optionCount"] = len(options)
            question["options"] = options
        else:
            expected = answer_box_count or len(answer_lines)
            rows = group_rows(answer_lines, expected)
            question["optionCount"] = len(rows)
            question["rows"] = rows
            question["values"] = list(range(1, len(rows) + 1))
        correct = derive_correct(meta_item, qtype, int(question["optionCount"]), source_answers)
        if correct:
            question["correct"] = correct
            question["solutionAvailable"] = True
        else:
            question["solutionAvailable"] = False
        imported.append(question)

    data["questions"] = base_questions + imported
    questions_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "questions.js").write_text(
        "window.QUESTIONS_DATA = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )
    print(f"base={len(base_questions)} imported={len(imported)} total={len(data['questions'])}")


if __name__ == "__main__":
    main()
