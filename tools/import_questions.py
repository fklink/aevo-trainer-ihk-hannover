import subprocess
import sys
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


def main():
    import_script = TOOLS / "import_extra_questions.py"
    quality_script = TOOLS / "mark_quality.py"

    print(f"\n=== {import_script} ===")
    subprocess.run([sys.executable, str(import_script)], cwd=ROOT, check=True)

    print(f"\n=== {quality_script} questions.json ===")
    subprocess.run([sys.executable, str(quality_script), "questions.json"], cwd=ROOT, check=True)

    questions_path = ROOT / "questions.json"
    data = json.loads(questions_path.read_text(encoding="utf-8-sig"))
    (ROOT / "questions.js").write_text(
        "window.QUESTIONS_DATA = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
