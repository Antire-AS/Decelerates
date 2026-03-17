import os
import json
from glob import glob
from PIL import Image
import pytesseract

# Sett sti til tesseract.exe (må være installert)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Riktig sti til slides-mappen din
SLIDES_DIR = r"C:\Users\patri\Downloads\whisper_input\slides_290824"

# Output-fil
OUTPUT_JSON = os.path.join(SLIDES_DIR, "slides_290824_ocr.json")

def main():
    if not os.path.isdir(SLIDES_DIR):
        print("Fant ikke slides-mappen:", SLIDES_DIR)
        return

    files = sorted(glob(os.path.join(SLIDES_DIR, "*.jpg")))
    print(f"Fant {len(files)} bilder i {SLIDES_DIR}")

    slides = []

    for fpath in files:
        fname = os.path.basename(fpath)
        print("OCR:", fname)

        try:
            img = Image.open(fpath)
            text = pytesseract.image_to_string(img, lang="nor+eng")
        except Exception as e:
            print(f"Feil ved OCR av {fname}:", e)
            text = ""

        slides.append({
            "file": fname,
            "text": text.strip()
        })

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(slides, f, ensure_ascii=False, indent=2)

    print("Ferdig. Lagret:", OUTPUT_JSON)


if __name__ == "__main__":
    main()