import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUESTION_RE = re.compile(r"^Frage\s+(\d+):?$", re.IGNORECASE)


def clean_text(value):
    value = re.sub(r"\s+", " ", value or "").strip()
    value = value.replace(" ,", ",").replace(" .", ".")
    return value


def line_text(lines, start, end):
    return clean_text(" ".join(lines[start:end]))


def split_ocr(lines):
    question_idx = None
    task_idx = None
    for i, line in enumerate(lines):
        if QUESTION_RE.match(line.strip()):
            question_idx = i
        if line.strip().lower().startswith("aufgabe"):
            task_idx = i
            break
    if question_idx is None:
        question_idx = -1
    if task_idx is None:
        task_idx = len(lines)

    question = line_text(lines, question_idx + 1, task_idx)
    after_task = [clean_text(line) for line in lines[task_idx + 1 :] if clean_text(line)]
    if after_task and re.search(r"kreuzen|füllen|bringen", after_task[0], re.IGNORECASE):
        after_task = after_task[1:]
    return question, after_task


def group_rows(lines, expected_count):
    if expected_count <= 0:
        return []
    groups = []
    current = []
    for index, line in enumerate(lines):
        if not current:
            current.append(line)
            continue
        remaining_lines = len(lines) - index
        remaining_groups = expected_count - len(groups)
        previous = current[-1]
        starts_new = previous.endswith((".", "!", "?")) and len(groups) + 1 < expected_count
        must_split = remaining_lines <= remaining_groups
        if starts_new or must_split:
            groups.append(clean_text(" ".join(current)))
            current = [line]
        else:
            current.append(line)
    if current:
        groups.append(clean_text(" ".join(current)))

    if len(groups) > expected_count:
        groups = groups[: expected_count - 1] + [clean_text(" ".join(groups[expected_count - 1 :]))]
    while len(groups) < expected_count:
        groups.append("")
    return groups


def import_ocr():
    questions_path = ROOT / "questions.json"
    ocr_path = ROOT / "ocr-text.json"
    data = json.loads(questions_path.read_text(encoding="utf-8"))
    ocr_items = json.loads(ocr_path.read_text(encoding="utf-8-sig"))
    by_id = {}
    for item in ocr_items:
        match = re.search(r"q(\d+)\.", item["name"])
        if match:
            by_id[int(match.group(1))] = item

    for question in data["questions"]:
        question.pop("nameReplacements", None)
        item = by_id.get(question["id"])
        if not item:
            continue
        image_path = ROOT / "assets_pdf" / f"q{question['id']:02d}.png"
        if image_path.exists():
            question["image"] = f"assets_pdf/q{question['id']:02d}.png"
        lines = item.get("lines") or []
        prompt, answer_lines = split_ocr(lines)
        if prompt:
            question["question"] = prompt
        question["ocrText"] = clean_text(item.get("text", ""))
        question["ocrLines"] = lines

        if question["type"] == "choice":
            question["options"] = group_rows(answer_lines, int(question.get("optionCount", 0)))
        elif question["type"] == "sequence":
            question["rows"] = group_rows(answer_lines, int(question.get("optionCount", 0)))
        elif question["type"] == "matrix":
            question.setdefault("ocrAnswerLines", answer_lines)

    questions_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "questions.js").write_text(
        "window.QUESTIONS_DATA = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    import_ocr()
