import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


def run_step(script_name):
    script_path = TOOLS / script_name
    print(f"\n=== {script_name} ===")
    subprocess.run([sys.executable, str(script_path)], cwd=ROOT, check=True)


def main():
    run_step("extract_source_question_images.py")
    run_step("extract_source_answer_images.py")


if __name__ == "__main__":
    main()
