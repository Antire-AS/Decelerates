import os
import json
import sys

def srt_to_timeline(srt_path, output_path):

    timeline = []

    with open(srt_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    i = 0

    while i < len(lines):

        line = lines[i].strip()

        if line.isdigit():

            time_line = lines[i+1].strip()
            text_line = lines[i+2].strip()

            start = time_line.split(" --> ")[0]
            h, m, s = start.split(":")
            s = s.split(",")[0]

            seconds = int(h)*3600 + int(m)*60 + int(s)

            timeline.append({
                "time": f"{h}:{m}:{s}",
                "seconds": seconds,
                "text": text_line
            })

            i += 4
        else:
            i += 1

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(timeline, f, ensure_ascii=False, indent=2)

    print("Saved:", output_path)


base = r"C:\Users\patri\Downloads\transksrt\whisper_input"

lectures = {
    "ffsformidler": "ffsformidler",
    "ffskunde": "ffskunde",
    "ffslære": "ffslære",
    "ffspraktisk": "ffspraktisk"
}

for name in lectures:

    srt = os.path.join(base, name, f"{name}.srt")
    out = os.path.join(base, "Videosubtime", f"{name}_timeline.json")

    srt_to_timeline(srt, out)