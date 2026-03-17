"""
generate_sections.py

Reads each *_timeline.json, sends a condensed transcript to Gemini,
asks it to identify thematic sections, and saves *_sections.json.

Run once:
    python transksrt/generate_sections.py
"""
import json
import os
import time
import re
from google import genai
from google.genai import types as genai_types
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

BASE = os.path.join(os.path.dirname(__file__), "whisper_input", "Videosubtime")

MODULES = {
    "ffsformidler": {
        "timeline": os.path.join(BASE, "ffsformidler_timeline.json"),
        "out":      os.path.join(BASE, "ffsformidler_sections.json"),
        "title":    "Forsikringsmegling i praksis",
    },
    "ffskunde": {
        "timeline": os.path.join(BASE, "ffskunde_timeline.json"),
        "out":      os.path.join(BASE, "ffskunde_sections.json"),
        "title":    "Behovsanalyse",
    },
    "ffslære": {
        "timeline": os.path.join(BASE, "ffslære_timeline.json"),
        "out":      os.path.join(BASE, "ffslære_sections.json"),
        "title":    "Juridisk ansvar og etikk",
    },
    "ffspraktisk": {
        "timeline": os.path.join(BASE, "ffspraktisk_timeline.json"),
        "out":      os.path.join(BASE, "ffspraktisk_sections.json"),
        "title":    "Praktiske øvelser",
    },
}

PROMPT_TEMPLATE = """\
Du er ekspert på norsk forsikringsopplæring. Nedenfor er et utdrag av en transkripsjon \
fra en FFS autorisasjonskursforelesning med tittel «{title}».

Transkripsjonen er samlet i tidsstemplede linjer. Din oppgave er å identifisere \
mellom 6 og 15 klare tematiske seksjoner/kapitler i forelesningen.

For hver seksjon, returner:
- title: kort norsk tittel (maks 5 ord)
- description: 1 setning om hva seksjonen handler om
- start_seconds: antall sekunder fra starten av videoen der seksjonen begynner
- start_time: tidsstempel i format MM:SS eller HH:MM:SS

Returner KUN gyldig JSON — en array av objekter uten noe annet tekst rundt.

Eksempel på format:
[
  {{"title": "Introduksjon", "description": "Foreleserne presenterer seg og kurset.", "start_seconds": 0, "start_time": "00:00"}},
  {{"title": "Kundens behov", "description": "Viktigheten av å forstå kundens forsikringsbehov.", "start_seconds": 420, "start_time": "07:00"}}
]

Transkripsjon (hvert 5. punkt vises):
{transcript}
"""


def condense(entries, step=5):
    """Return every `step`-th entry as a readable string."""
    lines = []
    for e in entries[::step]:
        lines.append(f"[{e['time']}] {e['text']}")
    return "\n".join(lines)


def extract_json(raw: str) -> list:
    """Strip markdown code fences and parse JSON."""
    raw = raw.strip()
    raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    return json.loads(raw)


def assign_entries_to_sections(sections: list, entries: list) -> list:
    """For each section, collect the timeline entries that fall within it."""
    sorted_sections = sorted(sections, key=lambda s: s["start_seconds"])
    result = []
    for i, sec in enumerate(sorted_sections):
        start = sec["start_seconds"]
        end = sorted_sections[i + 1]["start_seconds"] if i + 1 < len(sorted_sections) else float("inf")
        sec_entries = [e for e in entries if start <= e["seconds"] < end]
        result.append({
            "title": sec["title"],
            "description": sec.get("description", ""),
            "start_seconds": start,
            "start_time": sec["start_time"],
            "entries": sec_entries,
        })
    return result


def process_module(key: str, cfg: dict):
    print(f"\n{'='*60}")
    print(f"Processing: {cfg['title']}")

    if os.path.exists(cfg["out"]):
        print(f"  Already exists, skipping: {cfg['out']}")
        return

    with open(cfg["timeline"], encoding="utf-8") as f:
        entries = json.load(f)

    transcript = condense(entries, step=5)
    prompt = PROMPT_TEMPLATE.format(title=cfg["title"], transcript=transcript)

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    models_to_try = ["gemma-3-12b-it", "gemma-3-27b-it", "gemini-2.5-flash-lite-preview-06-17"]
    raw = None
    for attempt in range(3):
        for model_id in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model_id,
                    contents=prompt,
                )
                raw = response.text
                print(f"  Used model: {model_id}")
                break
            except Exception as e:
                err = str(e)[:140]
                print(f"  [{attempt+1}] Model {model_id} failed: {err}")
                time.sleep(5)
        if raw:
            break
        print(f"  All models failed on attempt {attempt+1}, waiting 30s...")
        time.sleep(30)
    if not raw:
        raise RuntimeError("All models failed after 3 attempts")

    print("  Raw LLM response (first 300 chars):", raw[:300])

    sections = extract_json(raw)
    print(f"  Identified {len(sections)} sections:")
    for s in sections:
        print(f"    [{s['start_time']}] {s['title']}")

    full_sections = assign_entries_to_sections(sections, entries)

    with open(cfg["out"], "w", encoding="utf-8") as f:
        json.dump(full_sections, f, ensure_ascii=False, indent=2)

    print(f"  Saved -> {cfg['out']}")
    return full_sections


if __name__ == "__main__":
    for key, cfg in MODULES.items():
        process_module(key, cfg)
        time.sleep(2)   # avoid rate limiting
    print("\nDone. All section files generated.")
