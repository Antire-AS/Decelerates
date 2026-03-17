import os
import json

BASE = r"C:\Users\patri\Downloads\whisper_input"

CONFIG = {
    "ffslære": "slides_220824",
    "ffsformidler": "slides_290824",
    "ffskunde": "slides_100624",
    "ffspraktisk": "slides_080524"
}


def load_transcript(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    segments = []
    offset = 0.0

    for chunk in sorted(data, key=lambda x: x["file"]):
        segs = chunk.get("segments", [])

        for s in segs:
            segments.append({
                "start": s["start"] + offset,
                "end": s["end"] + offset,
                "text": s["text"].strip()
            })

        if segs:
            offset += max(x["end"] for x in segs)

    return segments


def load_slides(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_alignment(segments, slides):

    total_time = segments[-1]["end"]
    slide_count = len(slides)

    slide_duration = total_time / slide_count

    aligned = []

    for i, slide in enumerate(slides):

        start = i * slide_duration
        end = (i + 1) * slide_duration

        spoken = [
            s["text"]
            for s in segments
            if s["start"] >= start and s["start"] < end
        ]

        aligned.append({
            "slide_file": slide["file"],
            "start_time": start,
            "end_time": end,
            "slide_text": slide["text"],
            "spoken_text": " ".join(spoken)
        })

    return aligned


def main():

    for lecture, slide_folder in CONFIG.items():

        print("Processing:", lecture)

        transcript_path = os.path.join(
            BASE,
            lecture,
            f"{lecture}_largev3_transcript.json"
        )

        slides_path = os.path.join(
            BASE,
            slide_folder,
            f"{slide_folder}_ocr.json"
        )

        segments = load_transcript(transcript_path)
        slides = load_slides(slides_path)

        aligned = build_alignment(segments, slides)

        out_path = os.path.join(
            BASE,
            lecture,
            f"{lecture}_aligned.json"
        )

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(aligned, f, ensure_ascii=False, indent=2)

        print("Saved:", out_path)


if __name__ == "__main__":
    main()