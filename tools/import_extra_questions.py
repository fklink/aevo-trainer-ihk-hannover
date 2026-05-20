import json
import re
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

from import_ocr import clean_text, expected_correct_count, extract_task_text, group_rows, split_ocr


ROOT = Path(__file__).resolve().parents[1]
HF_RE = re.compile(r"(?:^|/)HF\s*([1-4])(?:/|$)", re.IGNORECASE)
QUESTION_NUMBER_RE = re.compile(r"Frage\s+(\d+)\s*:", re.IGNORECASE)
PERSON_NAMES = {
    "peter", "paula", "felix", "miguel", "juan", "franzi", "franz", "alberto", "pepe",
    "irina", "carmen", "hans", "jule", "manuel", "alexandra", "christian", "charlotte",
    "hugo", "sabine", "torsten", "katharina", "otto", "markus", "paul", "nora", "mats",
    "jan", "tobias", "lena", "leon", "noah", "tim", "laura", "mara", "ben", "lea",
    "jonas", "clara", "david", "sophie", "finn", "anna", "julian", "julia",
}


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


def handlungsfeld_from_category(category):
    match = HF_RE.search(category or "")
    return int(match.group(1)) if match else None


def source_question_number(text):
    match = QUESTION_NUMBER_RE.search(text or "")
    return int(match.group(1)) if match else None


def normalize_for_dedupe(question):
    parts = [
        question.get("question", ""),
        " ".join(question.get("options") or []),
        " ".join(question.get("rows") or []),
    ]
    text = clean_text(" ".join(parts)).lower()
    text = re.sub(r"\b[a-zäöüß][\wäöüß.-]*\s+(gmbh|ag|kg|ohg)\b", " <firma> ", text)
    text = re.sub(r"\b(herrn?|frau|ausbilder(?:in)?|auszubildende[rmn]?)\s+[a-zäöüß][\wäöüß.-]*\b", " <person> ", text)
    for name in sorted(PERSON_NAMES, key=len, reverse=True):
        text = re.sub(rf"\b{re.escape(name)}\b", " <person> ", text)
    text = re.sub(r"\b\d{1,2}\s+jahre?\b", " <alter> ", text)
    text = re.sub(r"[^a-zäöüß0-9<>]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def sort_meta_items(items):
    def key(item):
        hf = handlungsfeld_from_category(item.get("category", ""))
        return (
            0 if hf else 1,
            hf or 99,
            item.get("category", ""),
            item.get("source", ""),
        )

    return sorted(items, key=key)


@lru_cache(maxsize=None)
def detect_answer_boxes(image_path):
    image_path = Path(image_path)
    image = Image.open(image_path).convert("L")
    width, height = image.size
    arr = np.array(image)
    mask = arr < 140
    def in_answer_column(x):
        return x <= width * 0.25 or x >= width * 0.65

    x_ranges = ((0, int(width * 0.25) + 1), (int(width * 0.65), width))
    seen = np.zeros(mask.shape, dtype=bool)
    boxes = []
    for y in range(height):
        for start_x, end_x in x_ranges:
            for x in range(start_x, end_x):
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
                        if 0 <= nx < width and 0 <= ny < height and in_answer_column(nx) and mask[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            stack.append((nx, ny))
                box_w = max_x - min_x + 1
                box_h = max_y - min_y + 1
                ratio = box_w / box_h if box_h else 0
                density = count / (box_w * box_h) if box_w and box_h else 1
                is_answer_box = (
                    45 <= box_w <= 140
                    and 45 <= box_h <= 140
                    and 0.75 <= ratio <= 1.25
                    and 0.02 <= density <= 0.22
                )
                if is_answer_box:
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


def source_comments(meta_item, source_answers):
    comments = []
    for token in source_answers.get(meta_item["source"], []):
        text = clean_text(token.get("text", ""))
        if not text:
            continue
        if token.get("kind") == "comment" or not re.fullmatch(r"[Xx]|\d+", text):
            comments.append((float(token.get("y", 0)), float(token.get("x", 0)), text))

    unique = []
    seen = set()
    for _, _, text in sorted(comments, key=lambda item: (-item[0], item[1])):
        if text in seen:
            continue
        seen.add(text)
        unique.append(text)
    return " ".join(unique) or None


def visible_answer_box_count(meta_item):
    boxes, image_width, _ = detect_answer_boxes(ROOT / meta_item["image"])
    right_column = [
        box for box in boxes
        if box["cx"] >= image_width * 0.72
    ]
    return len(right_column) or len(boxes)


def main():
    questions_path = ROOT / "questions.json"
    meta = json.loads((ROOT / "source-question-images.json").read_text(encoding="utf-8-sig"))
    ocr_items = json.loads((ROOT / "ocr-extra.json").read_text(encoding="utf-8-sig"))
    source_answers = json.loads((ROOT / "source-answers.json").read_text(encoding="utf-8-sig"))["answers"]
    ocr_by_name = {item["name"]: item for item in ocr_items}

    data = json.loads(questions_path.read_text(encoding="utf-8-sig"))
    manual_by_source = {
        question["source"]: question
        for question in data["questions"]
        if question.get("manualEdited") and question.get("source")
    }
    imported = []
    seen_fingerprints = set()
    next_id = 1

    for meta_item in sort_meta_items(meta["items"]):
        image_name = Path(meta_item["image"]).name
        legacy_image_name = f"q{int(meta_item['id']) + 48:03d}.png"
        item = ocr_by_name.get(image_name) or ocr_by_name.get(legacy_image_name)
        if not item:
            continue
        prompt, answer_lines = split_ocr(item.get("lines") or [])
        task = extract_task_text(item.get("lines") or [])
        if not prompt:
            prompt = clean_text(item.get("text", ""))
        qtype = infer_type(meta_item["title"], item.get("text", ""))
        answer_box_count = visible_answer_box_count(meta_item)
        handlungsfeld = handlungsfeld_from_category(meta_item.get("category", ""))
        answer_image = Path("assets_answers") / Path(meta_item["image"]).name
        question = {
            "id": next_id,
            "title": f"Frage {next_id}",
            "sourceTitle": meta_item["title"],
            "points": points_from_text(item.get("text", "")),
            "type": qtype,
            "image": meta_item["image"],
            "question": prompt,
            "task": task,
            "ocrText": clean_text(item.get("text", "")),
            "ocrLines": item.get("lines") or [],
            "source": meta_item["source"],
            "category": meta_item["category"],
            "solutionAvailable": False,
        }
        if (ROOT / answer_image).exists():
            question["answerImage"] = str(answer_image).replace("\\", "/")
        if handlungsfeld:
            question["handlungsfeld"] = handlungsfeld
        original_number = source_question_number(item.get("text", ""))
        if original_number:
            question["sourceQuestionNumber"] = original_number
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
        explanation = source_comments(meta_item, source_answers)
        if explanation:
            question["explanation"] = explanation

        expected_correct = expected_correct_count(task)
        if expected_correct is not None:
            question["expectedCorrectCount"] = expected_correct
            actual_correct = len(question.get("correct") or [])
            if qtype == "choice" and actual_correct != expected_correct:
                question.setdefault("importWarnings", []).append(
                    f"Erwartet {expected_correct} richtige Antwort(en), erkannt {actual_correct}."
                )

        if meta_item["source"] in manual_by_source:
            question = manual_by_source[meta_item["source"]]

        fingerprint = normalize_for_dedupe(question)
        if fingerprint and fingerprint in seen_fingerprints:
            continue
        if fingerprint:
            seen_fingerprints.add(fingerprint)
        imported.append(question)
        next_id += 1

    data["questions"] = imported
    questions_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "questions.js").write_text(
        "window.QUESTIONS_DATA = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )
    hf_count = sum(1 for question in imported if question.get("handlungsfeld"))
    print(f"imported={len(imported)} hf={hf_count} total={len(data['questions'])}")


if __name__ == "__main__":
    main()
