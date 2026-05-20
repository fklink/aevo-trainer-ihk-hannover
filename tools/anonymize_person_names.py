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
COMPANY_NAMES = [
    "Nordblick", "Maventa", "Bergfeld", "Solvion", "Altrona", "Westhafen",
    "Noventis", "Klarwerk", "Rheinpunkt", "Valora", "Hansewerk", "Primora",
    "Aventra", "Lunaris", "Modulix", "Feldwerk", "Terval", "Konova",
]
COMPANY_BY_SUFFIX = {
    "GmbH": ["Nordblick GmbH", "Maventa GmbH", "Klarwerk GmbH", "Primora GmbH", "Aventra GmbH", "Konova GmbH"],
    "KG": ["Bergfeld KG", "Westhafen KG", "Rheinpunkt KG", "Feldwerk KG"],
    "AG": ["Solvion AG", "Altrona AG", "Hansewerk AG", "Lunaris AG"],
    "OHG": ["Noventis OHG", "Valora OHG", "Rheinpunkt OHG", "Terval OHG", "Modulix OHG"],
}

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
    47: [("last", ["Ausbilder Kurz", "Kurz"])],
}

QUESTION_COMPANY_GROUPS = {
    1: [["Erwo GmbH"]],
    10: [["Erwo GmbH"]],
    11: [["Energie Süd AG"]],
    12: [["Schuster KG"]],
    18: [["VWN AG", "VWN"]],
    19: [["Envo GmbH"]],
    20: [["VWN AG"]],
    21: [["Lohmeyer OHG"]],
    26: [["Menoka GmbH"]],
    32: [["Deichgraf GmbH"]],
    35: [["Peters"]],
    38: [["Elektro-Max"]],
    47: [["Heinrich Mann OHG", "Heinrich Mann"]],
}

GLOBAL_EXTRA_REPLACEMENTS = {
    "Peter": "Paul",
    "Paula": "Nora",
    "Felix": "Mats",
    "Miguel": "Jan",
    "Juan": "Tobias",
    "Franzi": "Lena",
    "Franz": "Leon",
    "Alberto": "Noah",
    "Iberto": "Noah",
    "Pepe": "Tim",
    "Irina": "Laura",
    "Irinas": "Lauras",
    "llrina": "Laura",
    "\"rina": "Laura",
    "Carmen": "Mara",
    "Carmens": "Maras",
    "Hans": "Ben",
    "Jule": "Lea",
    "Manuel Wagner": "Jonas Richter",
    "Manuel": "Jonas",
    "Alexandra": "Clara",
    "Christian": "David",
    "Charlotte": "Sophie",
    "Hugo Schmidt": "Finn Berger",
    "Sabine Klein": "Anna Keller",
    "Torsten Mantey": "Julian Fischer",
    "Katharina Theis": "Julia Hoffmann",
    "Otto Adam": "Paul Brandt",
    "Herr Nose": "Herr Weber",
    "Nose": "Weber",
    "Herr Kribbe": "Herr Schmitt",
    "Kribbe": "Schmitt",
    "Erwo GmbH": "Nordblick GmbH",
    "Classic & Co.": "Nova & Co.",
    "Classic & Co": "Nova & Co",
    "Peters Bürobedarf OHG": "Terval Bürobedarf OHG",
    "Seedeich GmbH": "Aventra GmbH",
    "Felixus GmbH": "Konova GmbH",
}


def pick_unused(pool, used):
    choices = [item for item in pool if item not in used]
    if not choices:
        choices = pool
    value = RNG.choice(choices)
    used.add(value)
    return value


def company_replacement_for(aliases, used_companies):
    canonical = aliases[0]
    suffix_match = re.search(r"\b(GmbH|KG|AG|OHG)\b", canonical)
    if suffix_match:
        pool = COMPANY_BY_SUFFIX[suffix_match.group(1)]
        replacement = pick_unused(pool, used_companies)
    else:
        replacement = pick_unused(COMPANY_NAMES, used_companies)
    return {alias: replacement for alias in sorted(aliases, key=len, reverse=True)}


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
METADATA_KEYS = {
    "id", "title", "sourceTitle", "source", "category", "image", "handlungsfeld",
    "sourceQuestionNumber", "points", "type", "optionCount", "solutionAvailable",
}


def content_payload(question):
    return {key: value for key, value in question.items() if key not in METADATA_KEYS and key != "nameReplacements"}


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
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    used_first = set()
    used_last = set()
    used_companies = set()

    for question in data["questions"]:
        previous = question.get("nameReplacements")
        if isinstance(previous, dict) and previous:
            reverse = {new: old for old, new in sorted(previous.items(), key=lambda item: len(item[1]), reverse=True)}
            question.update(replace_recursive(content_payload(question), reverse))
            question.pop("nameReplacements", None)

        replacements = {}
        for kind, aliases in QUESTION_NAME_GROUPS.get(question["id"], []):
            replacements.update(replacement_for(kind, aliases, used_first, used_last))
        if replacements:
            question.update(replace_recursive(content_payload(question), replacements))

        company_replacements = {}
        for aliases in QUESTION_COMPANY_GROUPS.get(question["id"], []):
            company_replacements.update(company_replacement_for(aliases, used_companies))
        if company_replacements:
            question.update(replace_recursive(content_payload(question), company_replacements))

        question.update(replace_recursive(content_payload(question), GLOBAL_EXTRA_REPLACEMENTS))

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "questions.js").write_text(
        "window.QUESTIONS_DATA = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
