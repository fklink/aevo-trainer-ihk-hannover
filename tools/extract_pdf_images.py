from pathlib import Path
import sys

from PIL import Image
from pypdf import PdfReader


def extract(pdf_path, output_dir, scale=2, prefix="page"):
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    reader = PdfReader(str(pdf_path))
    for page_number, page in enumerate(reader.pages, start=1):
        if not page.images:
            continue
        image = page.images[0]
        source = output_dir / f"page-{page_number:03d}-{image.name}"
        source.write_bytes(image.data)
        with Image.open(source) as img:
            img = img.convert("RGB")
            if scale != 1:
                img = img.resize((img.width * scale, img.height * scale), Image.Resampling.LANCZOS)
            target = output_dir / f"{prefix}{page_number:02d}.png"
            img.save(target)
        source.unlink(missing_ok=True)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit("usage: extract_pdf_images.py PDF OUTPUT_DIR [SCALE] [PREFIX]")
    extract(
        sys.argv[1],
        sys.argv[2],
        int(sys.argv[3]) if len(sys.argv) > 3 else 2,
        sys.argv[4] if len(sys.argv) > 4 else "page",
    )
