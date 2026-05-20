import json
import random
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RNG = random.Random(90420)

MALE_FIRST_NAMES = [
    "Tobias", "Noah", "Jonas", "David", "Nico", "Luca", "Ben", "Leon",
    "Mats", "Tim", "Finn", "Jan", "Paul", "Simon", "Julian", "Tom",
]
FEMALE_FIRST_NAMES = [
    "Lena", "Mara", "Clara", "Sophie", "Hanna", "Emma", "Lea", "Amelie",
    "Nora", "Marie", "Laura", "Sarah", "Mia", "Anna", "Julia", "Katharina",
]
LAST_NAMES = [
    "Berger", "Weber", "Schneider", "Fischer", "Keller", "Neumann",
    "Hoffmann", "Richter", "Wolf", "Schulz", "Krause", "Bauer",
    "Vogel", "Schmitt", "Hartmann", "Brandt", "Seidel", "Becker",
]

# Names observed in the current OCR-enriched question set. Aliases in one group
# are OCR variants or grammatical variants that should stay one replacement.
QUESTION_NAME_GROUPS = {
    1: [("male", ["Peter"]), ("female", ["Paula"]), ("male", ["Felix"])],
    5: [("male", ["Jens Fähnrich", "Jens", "Fähnrich"])],
    10: [("male", ["Peter"]), ("female", ["Paula"]), ("male", ["Felix"])],
    12: [("male", ["Horst Mann", "Herr Mann", "Herrn Mann", "Horst", "Mann"])],
    15: [("male", ["Holger Fraatz", "Holger", "Fraatz"])],
    16: [("male", ["Miguel"]), ("male", ["Juan"])],
    18: [("last", ["Herr Steilmann", "Herr Stellmann", "Steilmann", "Stellmann"])],
    19: [("last", ["Herrn Marwitz", "Marwitz"])],
    21: [("last", ["Herr König", "König"])],
    24: [("male", ["Friedhelm"])],
    25: [("female", ["Miriam", "Mirjam"])],
    27: [("female", ["Saskia"])],
    32: [("last", ["Herr Pauli", "Ausbilder Pauli", "Pauli"])],
    34: [("last", ["Herr Müller", "Müller"])],
    37: [("last", ["Heuer"]), ("male", ["Florian"])],
    38: [("last", ["Ausbilder Adam", "Adam"]), ("last", ["Ausbildungsbeauftragter Lehmann", "Lehmann"])],
    40: [("last", ["Ausbilder Schwarzer", "Herr Schwarze", "Schwarzer", "Schwarze"])],
    43: [("male", ["Bruno"])],
    45: [("male", ["Georg"])],
    46: [("female", ["Martina Koch", "Martina", "Koch"])],
    47: [("last", ["Ausbilder Kurz", "Kurz"]), ("company", ["Heinrich Mann", "Heinrich", "Mann"])],
}


def pick_unused(pool, used):
    choices = [item for item in pool if item not in used]
    if not choices:
        choices = pool
    value = RNG.choice(choices)
    used.add(value)
    return value


def replacement_for(kind, aliases, used_first, used_last):
    title_prefixes = ("Herr ", "Herrn ", "Ausbilder ", "Ausbilderin ", "Ausbildungsbeauftragter ")
    full_name = any(" " in alias and not alias.startswith(title_prefixes) for alias in aliases)
    has_title = any(alias.startswith(title_prefixes) for alias in aliases)
    if kind == "female":
        first = pick_unused(FEMALE_FIRST_NAMES, used_first)
    else:
        first = pick_unused(MALE_FIRST_NAMES, used_first)
    last = pick_unused(LAST_NAMES, used_last)

    replacements = {}
    for alias in sorted(aliases, key=len, reverse=True):
        if alias.startswith("Herrn "):
            replacements[alias] = "Herrn " + last
        elif alias.startswith("Herr "):
            replacements[alias] = "Herr " + last
        elif alias.startswith("Ausbilderin "):
            replacements[alias] = "Ausbilderin " + last
        elif alias.startswith("Ausbilder "):
            replacements[alias] = "Ausbilder " + last
        elif alias.startswith("Ausbildungsbeauftragter "):
            replacements[alias] = "Ausbildungsbeauftragter " + last
        elif kind == "company" and " " in alias:
            replacements[alias] = first + " " + last
        elif full_name and " " in alias:
            replacements[alias] = first + " " + last
        elif alias in LAST_NAME_HINTS:
            # Surnames that also appear after titles should remain surnames.
            replacements[alias] = last
        elif has_title and not full_name:
            replacements[alias] = last
        else:
            replacements[alias] = first
    return replacements


LAST_NAME_HINTS = {
    "Fähnrich", "Fraatz", "Mann", "Steilmann", "Stellmann", "Marwitz",
    "König", "Pauli", "Müller", "Heuer", "Adam", "Lehmann", "Schwarzer", "Schwarze",
    "Koch", "Kurz",
}


def replace_text(text, replacements):
    if not isinstance(text, str) or not text:
        return text
    for old, new in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        text = re.sub(r"\b" + re.escape(old) + r"\b", new, text)
    return text


def replace_recursive(value, replacements):
    if isinstance(value, str):
        return replace_text(value, replacements)
    if isinstance(value, list):
        return [replace_recursive(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: replace_recursive(item, replacements) for key, item in value.items()}
    return value


def main():
    path = ROOT / "questions.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    used_first = set()
    used_last = set()

    for question in data["questions"]:
        previous = question.get("nameReplacements")
        if isinstance(previous, dict) and previous:
            reverse = {new: old for old, new in sorted(previous.items(), key=lambda item: len(item[1]), reverse=True)}
            question.update(replace_recursive({k: v for k, v in question.items() if k != "nameReplacements"}, reverse))
            question.pop("nameReplacements", None)

        replacements = {}
        for kind, aliases in QUESTION_NAME_GROUPS.get(question["id"], []):
            replacements.update(replacement_for(kind, aliases, used_first, used_last))
        if replacements:
            question.update(replace_recursive({k: v for k, v in question.items() if k != "nameReplacements"}, replacements))

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "questions.js").write_text(
        "window.QUESTIONS_DATA = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
