import os
import json
import sys
from glob import glob
from faster_whisper import WhisperModel

def main():
    if len(sys.argv) < 2:
        print("Usage: py -3.11 transcribe_folder_large_json_gpu.py <AUDIO_DIR>")
        sys.exit(1)

    audio_dir = sys.argv[1]

    if not os.path.isdir(audio_dir):
        print("No such folder:", audio_dir)
        sys.exit(1)

    output_json = os.path.join(audio_dir, f"{os.path.basename(audio_dir)}_largev3_transcript.json")

    model = WhisperModel(
        "large-v3",
        device="cuda",
        compute_type="float16"
    )

    files = sorted(glob(os.path.join(audio_dir, "*.wav")))
    print(f"Found {len(files)} chunks in {audio_dir}")

    all_chunks = []

    for fpath in files:
        fname = os.path.basename(fpath)
        print("Transcribing:", fname)

        segments, info = model.transcribe(
            fpath,
            beam_size=5,
            language="no",
            vad_filter=True,
        )

        chunk_data = {"file": fname, "segments": []}

        for seg in segments:
            chunk_data["segments"].append({
                "start": seg.start,
                "end": seg.end,
                "text": seg.text.strip()
            })

        all_chunks.append(chunk_data)

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    print("Saved:", output_json)

if __name__ == "__main__":
    main()