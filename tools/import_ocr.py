import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUESTION_RE = re.compile(r"^Frage\s+(\d+):?$", re.IGNORECASE)


def clean_text(value):
    value = re.sub(r"\s+", " ", value or "").strip()
    value = value.replace(" ,", ",").replace(" .", ".")
    value = re.sub(r"\bAn[Ww]ort\b", "Antwort", value)
    value = re.sub(r"\bAn[Ww]orten\b", "Antworten", value)
    value = re.sub(r"\bkitte\b", "Bitte", value)
    return value


def line_text(lines, start, end):
    return clean_text(" ".join(lines[start:end]))


def multiline_text(lines):
    cleaned = [clean_text(line) for line in lines if clean_text(line)]
    if not cleaned:
        return ""
    max_len = max(len(line) for line in cleaned) or 1
    paragraphs = []
    current = cleaned[0]
    for line in cleaned[1:]:
        previous = current.split("\n")[-1]
        previous_short = len(previous) < max_len * 0.72
        sentence_break = previous.endswith((".", "!", "?"))
        starts_like_sentence = bool(re.match(r"^[A-ZÄÖÜ0-9]", line))
        if sentence_break and (previous_short or starts_like_sentence):
            paragraphs.append(current)
            current = line
        elif previous_short and starts_like_sentence and not previous.endswith((",", "-", "und", "oder")):
            paragraphs.append(current)
            current = line
        else:
            current += " " + line
    paragraphs.append(current)
    return "\n".join(paragraphs)


def extract_task_text(lines):
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("aufgabe"):
            task = clean_text(line)
            if i + 1 < len(lines) and re.search(r"kreuzen|füllen|fÃ¼llen|bringen|nummerieren", lines[i + 1], re.IGNORECASE):
                task = clean_text(task + " " + lines[i + 1])
            return task
    return ""


NUMBER_WORDS = {
    "eine": 1, "einen": 1,
    "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "fuenf": 5,
    "sechs": 6, "sieben": 7, "acht": 8, "neun": 9, "zehn": 10,
    "elf": 11, "zwölf": 12, "zwoelf": 12,
}


def expected_correct_count(task_text):
    text = (task_text or "").lower()
    digit = re.search(r"\b(\d+)\s+richtige", text)
    if digit:
        return int(digit.group(1))
    for word, value in NUMBER_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\s+richtige", text):
            return value
    if re.search(r"\bdie\s+richtige\s+antwort\b|\brichtige\s+antwort\b", text):
        return 1
    return None


def is_continuation_line(previous, line):
    previous = clean_text(previous).lower()
    line = clean_text(line)
    if not previous or not line:
        return False
    if line[0].islower():
        return True
    if previous.endswith((",", ";", ":", "-", "–")):
        return True
    if re.search(r"\b(und|oder|sowie|mit|ohne|durch|für|fÃ¼r|bei|im|in|der|die|das|den|dem|des|ein|eine|einen|einem|einer)$", previous):
        return True
    if re.match(r"^(dass|damit|weil|wenn|wobei|sowie|und|oder|bzw\.|bzw|z\. b\.|z\.b\.)\b", line, re.IGNORECASE):
        return True
    if re.match(r"^[a-zÃ¤Ã¶Ã¼ÃŸ]", line):
        return True
    return False


def is_missing_period_boundary(previous, line):
    previous = clean_text(previous)
    line = clean_text(line)

    if not previous or not line:
        return False
    if previous.endswith((".", "!", "?", ",", ";", ":", "-")):
        return False
    if is_continuation_line(previous, line):
        return False
    if len(previous) > 130:
        return False
    if len(re.findall(r"\w+", previous, flags=re.UNICODE)) < 5:
        return False

    return bool(re.match(r"^(Auf|Aus|Bei|Da|Das|Der|Die|Ein|Eine|Es|Im|In|Nur|Tobias|[A-ZÄÖÜ][a-zäöüß]+)\b", line))


def finish_sentence(value):
    value = clean_text(value)
    word_count = len(re.findall(r"\w+", value, flags=re.UNICODE))
    if value and word_count >= 5 and not value.endswith((".", "!", "?")):
        return value + "."
    return value


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

    question = multiline_text(lines[question_idx + 1 : task_idx])
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
        continuation = is_continuation_line(previous, line)
        missing_period_boundary = is_missing_period_boundary(previous, line)
        starts_new = previous.endswith((".", "!", "?")) and len(groups) + 1 < expected_count
        must_split = remaining_lines <= remaining_groups and not continuation
        if missing_period_boundary or (starts_new and not continuation) or must_split:
            group_text = clean_text(" ".join(current))
            groups.append(finish_sentence(group_text) if missing_period_boundary else group_text)
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
        image_candidates = [
            ROOT / "assets" / f"q{question['id']:03d}.png",
            ROOT / "assets" / f"q{question['id']:02d}.png",
            ROOT / "assets" / f"q{question['id']:02d}.jpg",
        ]
        for image_path in image_candidates:
            if image_path.exists():
                question["image"] = str(image_path.relative_to(ROOT)).replace("\\", "/")
                break
        lines = item.get("lines") or []
        prompt, answer_lines = split_ocr(lines)
        task = extract_task_text(lines)
        if prompt:
            question["question"] = prompt
        if task:
            question["task"] = task
        question["ocrText"] = clean_text(item.get("text", ""))
        question["ocrLines"] = lines

        if question["type"] == "choice":
            question["options"] = group_rows(answer_lines, int(question.get("optionCount", 0)))
        elif question["type"] == "sequence":
            question["rows"] = group_rows(answer_lines, int(question.get("optionCount", 0)))
        elif question["type"] == "matrix":
            question.setdefault("ocrAnswerLines", answer_lines)

        expected = expected_correct_count(task)
        if expected is not None:
            question["expectedCorrectCount"] = expected
            actual = len(question.get("correct") or [])
            warnings = [warning for warning in question.get("importWarnings", []) if "Erwartet" not in warning]
            if question.get("type") == "choice" and actual != expected:
                warnings.append(f"Erwartet {expected} richtige Antwort(en), erkannt {actual}.")
            if warnings:
                question["importWarnings"] = warnings
            else:
                question.pop("importWarnings", None)

    questions_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "questions.js").write_text(
        "window.QUESTIONS_DATA = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    import_ocr()
