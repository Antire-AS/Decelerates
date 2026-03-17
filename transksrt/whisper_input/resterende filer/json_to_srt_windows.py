import json
import sys
import os


def sec_to_ts(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int((t - int(t)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    if len(sys.argv) < 3:
        print("Usage: py -3.11 json_to_srt_windows.py input.json output.srt")
        sys.exit(1)

    input_json = sys.argv[1]
    output_srt = sys.argv[2]

    if not os.path.exists(input_json):
        print("Fant ikke JSON:", input_json)
        sys.exit(1)

    with open(input_json, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    all_segments = []
    offset = 0.0

    # sorter chunkene riktig (part_000, part_001 ...)
    chunks_sorted = sorted(chunks, key=lambda c: c.get("file", ""))

    for chunk in chunks_sorted:
        segs = chunk.get("segments", [])

        for seg in segs:
            start = float(seg.get("start", 0.0)) + offset
            end = float(seg.get("end", 0.0)) + offset
            text = seg.get("text", "").strip()

            if text:
                all_segments.append((start, end, text))

        if segs:
            max_local_end = max(float(s.get("end", 0.0)) for s in segs)
        else:
            max_local_end = 0.0

        offset += max_local_end

    all_segments.sort(key=lambda x: x[0])

    with open(output_srt, "w", encoding="utf-8") as out:
        for i, (start, end, text) in enumerate(all_segments, start=1):
            out.write(f"{i}\n")
            out.write(f"{sec_to_ts(start)} --> {sec_to_ts(end)}\n")
            out.write(text + "\n\n")

    print("SRT lagret:", output_srt)


if __name__ == "__main__":
    main()