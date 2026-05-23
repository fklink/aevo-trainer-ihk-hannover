# mark_quality.py
# Nutzung:
# python mark_quality.py questions.json

import json
import re
import sys
from pathlib import Path


INPUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("questions.json")
OUTPUT = Path(sys.argv[2]) if len(sys.argv) > 2 else INPUT


SUSPICIOUS_PATTERNS = [
    (r"\bMEIche\b", "welche", "ocr_word"),
    (r"\bAMei\b", "zwei", "ocr_word"),
    (r"\bnvei\b", "zwei", "ocr_word"),
    (r"\bzvæi\b", "zwei", "ocr_word"),
    (r"\bvemittelt\b", "vermittelt", "ocr_word"),
    (r"\bTemin\b", "Termin", "ocr_word"),
    (r"\bwahmehmen\b", "wahrnehmen", "ocr_word"),
    (r"\bAsbider\b", "Ausbilder", "ocr_word"),
    (r"\bAusalbildenden\b", "Auszubildenden", "ocr_word"),
    (r"\buntericht\b", "unterricht", "ocr_word"),
    (r"\bAn[Ww]ort\b", "Antwort", "ocr_word"),
    (r"\bAn[Ww]orten\b", "Antworten", "ocr_word"),
    (r"\bkitte\b", "Bitte", "ocr_word"),
    (r"\bBewerbungsuntedagen\b", "Bewerbungsunterlagen", "ocr_word"),
    (r"\bBetriebsvereinbahrung\b", "Betriebsvereinbarung", "ocr_word"),
    (r"\bVergüturg\b", "Vergütung", "ocr_word"),
    (r"\bGebrauchsanæisung\b", "Gebrauchsanweisung", "ocr_word"),
    (r"\bm Laufe\b", "im Laufe", "missing_letter"),
    (r"\bSie I\b", "Sie", "stray_character"),
    (r"\b14jährige\b", "14-jährige", "missing_hyphen"),
    (r"[Ææ•]", None, "suspicious_character"),
    (r"\s{2,}", " ", "double_space"),
    (r"\s+[?!.,;:]", None, "space_before_punctuation"),
]


def add_issue(issues, issue_type, field, value, suggestion=None):
    issues.append({
        "type": issue_type,
        "field": field,
        "value": str(value)[:180],
        "suggestion": suggestion,
    })


def check_text(value, field, issues):
    if not isinstance(value, str) or not value:
        return

    for pattern, suggestion, issue_type in SUSPICIOUS_PATTERNS:
        for match in re.finditer(pattern, value):
            add_issue(issues, issue_type, field, match.group(0), suggestion)

    if re.search(r"[A-ZÄÖÜ]{2,}[a-zäöüß]", value):
        add_issue(issues, "mixed_case_ocr", field, value)

    if re.search(r"\b[a-zäöüß]{1,2}[A-ZÄÖÜ][a-zäöüß]+\b", value):
        add_issue(issues, "letter_case_inside_word", field, value)


def check_options(q, issues):
    options = q.get("options")

    if not isinstance(options, list):
        return

    real_options = 0
    empty_indexes = []

    for i, option in enumerate(options):
        field = f"options[{i}]"

        if option is None:
            empty_indexes.append(i)
            add_issue(issues, "empty_option", field, "null")
            continue

        if not isinstance(option, str):
            add_issue(issues, "invalid_option_type", field, type(option).__name__)
            continue

        if option.strip() == "":
            empty_indexes.append(i)
            add_issue(issues, "empty_option", field, "")
            continue

        real_options += 1
        check_text(option, field, issues)

        if len(option) > 220:
            add_issue(issues, "possibly_merged_options", field, option)

    if empty_indexes:
        add_issue(
            issues,
            "empty_options",
            "options",
            "Leere Antwortoptionen an Position(en): "
            + ", ".join(str(i + 1) for i in empty_indexes),
        )

    declared_count = q.get("optionCount")
    if declared_count is not None and declared_count != real_options:
        add_issue(
            issues,
            "option_count_mismatch",
            "options",
            f"optionCount={declared_count}, realOptions={real_options}",
        )

    if len(empty_indexes) >= 2:
        add_issue(
            issues,
            "many_empty_options",
            "options",
            f"{len(empty_indexes)} leere Antwortoptionen",
        )


def check_rows(q, issues):
    rows = q.get("rows")

    if not isinstance(rows, list):
        return

    empty_indexes = []

    for i, row in enumerate(rows):
        field = f"rows[{i}]"

        if row is None:
            empty_indexes.append(i)
            add_issue(issues, "empty_row", field, "null")
            continue

        if not isinstance(row, str):
            add_issue(issues, "invalid_row_type", field, type(row).__name__)
            continue

        if row.strip() == "":
            empty_indexes.append(i)
            add_issue(issues, "empty_row", field, "")
            continue

        check_text(row, field, issues)

        if len(row) > 260:
            add_issue(issues, "possibly_merged_rows", field, row)

    if empty_indexes:
        add_issue(
            issues,
            "empty_rows",
            "rows",
            "Leere Zeilen an Position(en): "
            + ", ".join(str(i + 1) for i in empty_indexes),
        )


def check_correct_count(q, issues):
    expected = q.get("expectedCorrectCount")
    correct = q.get("correct")

    if expected is None or not isinstance(correct, list):
        return

    if expected != len(correct):
        add_issue(
            issues,
            "correct_count_mismatch",
            "correct",
            f"expected={expected}, actual={len(correct)}",
        )


def check_sequence_consistency(q, issues):
    if q.get("type") != "sequence":
        return

    rows = q.get("rows")
    values = q.get("values")
    correct = q.get("correct")

    if isinstance(rows, list) and isinstance(correct, list):
        real_rows = len([r for r in rows if isinstance(r, str) and r.strip()])
        if real_rows != len(correct):
            add_issue(
                issues,
                "sequence_solution_length_mismatch",
                "correct",
                f"rows={real_rows}, correct={len(correct)}",
            )

    if isinstance(rows, list) and isinstance(values, list):
        real_rows = len([r for r in rows if isinstance(r, str) and r.strip()])
        if len(values) < real_rows:
            add_issue(
                issues,
                "sequence_values_too_short",
                "values",
                f"rows={real_rows}, values={len(values)}",
            )


def check_import_warnings(q, issues):
    warnings = q.get("importWarnings") or []

    if not isinstance(warnings, list):
        return

    for warning in warnings:
        add_issue(issues, "existing_import_warning", "importWarnings", warning)


def mark_question(q):
    issues = []

    check_text(q.get("question"), "question", issues)
    check_text(q.get("task"), "task", issues)

    check_options(q, issues)
    check_rows(q, issues)

    check_correct_count(q, issues)
    check_sequence_consistency(q, issues)
    check_import_warnings(q, issues)

    q["qualityFlags"] = sorted(set(issue["type"] for issue in issues))
    q["qualityIssues"] = issues
    q["needsReview"] = bool(issues)


def main():
    data = json.loads(INPUT.read_text(encoding="utf-8"))

    if isinstance(data, list):
        questions = data
    else:
        questions = data.get("questions", [])

    for q in questions:
        if isinstance(q, dict):
            mark_question(q)

    OUTPUT.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    marked = sum(1 for q in questions if isinstance(q, dict) and q.get("needsReview"))

    print(f"Fertig: {OUTPUT}")
    print(f"Datensätze gesamt: {len(questions)}")
    print(f"Markierte Datensätze: {marked}")


if __name__ == "__main__":
    main()
