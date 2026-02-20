# Armenian Voice Assistant (STT -> Gemini -> TTS)

This project:
1. records Armenian speech from microphone,
2. transcribes with ElevenLabs STT,
3. answers with Gemini using a provided JSON knowledge file,
4. speaks the answer with ElevenLabs TTS.

The main entrypoint is `main_runner.py`.

## 1) Start From Zero -> End (Runbook)

### Step 1: Setup environment

```bash
cd /Users/levon/Downloads/armenian-voice-assistant
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env` in project root:

```env
ELEVENLABS_API_KEY=your_elevenlabs_key
GEMINI_API_KEY=your_gemini_key
```

Optional for local playback:

```bash
brew install ffmpeg
```

### Step 2: Download/import audio files

Put raw call audio files (`.m4a`, `.wav`, `.mp3`, `.ogg`, `.flac`, `.aac`) under:

`data/call_recordings/`

Example (if you use the existing archive):

```bash
mkdir -p data/call_recordings
# option A
unrar x -o+ data/call_records.rar data/call_recordings/
# option B
unar -o data/call_recordings data/call_records.rar
```

### Step 2.1: Download Excel file (`Հաճախակի տրվող հարցեր.xlsx`)

Download the Excel file and place it in `data/`.

Browser/manual:
1. Download the `.xlsx` file from your source.
2. Save it as `data/Հաճախակի տրվող հարցեր.xlsx`.

CLI (if you have a direct download URL):

```bash
mkdir -p data
curl -L "<DIRECT_XLSX_URL>" -o "data/Հաճախակի տրվող հարցեր.xlsx"
```

Verify:

```bash
ls -lh "data/Հաճախակի տրվող հարցեր.xlsx"
```

### Step 3: Build transcript dataset from audio

Generate or append transcripts:

```bash
python build_dataset.py \
  --audio-dir data/call_recordings \
  --dataset-out data/sas_dataset.jsonl \
  --skip-existing
```

Process a specific chunk (example: next 20 after first 35):

```bash
python build_dataset.py \
  --audio-dir data/call_recordings \
  --dataset-out data/sas_dataset.jsonl \
  --start-index 35 \
  --max-files 20
```

### Step 4: Convert/apply dataset into `data/sas_knowledge.json`

Run this once after new audio transcriptions are added:

```bash
python - <<'PY'
import json
from pathlib import Path

dataset = Path("data/sas_dataset.jsonl")
knowledge = Path("data/sas_knowledge.json")

items = json.loads(knowledge.read_text(encoding="utf-8")) if knowledge.exists() else []
if not isinstance(items, list):
    raise SystemExit("data/sas_knowledge.json must be a JSON array")

existing_paths = set()
for it in items:
    if isinstance(it, dict):
        meta = it.get("meta", {})
        if isinstance(meta, dict) and isinstance(meta.get("path"), str):
            existing_paths.add(str(Path(meta["path"]).resolve()))

next_id = 1
for it in items:
    iid = str(it.get("item_id", "")) if isinstance(it, dict) else ""
    if iid.startswith("audio-"):
        try:
            next_id = max(next_id, int(iid.split("-")[1]) + 1)
        except Exception:
            pass

added = 0
for line in dataset.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    audio_path = str(Path(row["audio_path"]).resolve())
    if audio_path in existing_paths:
        continue
    items.append({
        "item_id": f"audio-{next_id:05d}",
        "source_type": "call_recording_transcript",
        "source": Path(audio_path).name,
        "text": row.get("transcript", ""),
        "meta": {"path": audio_path},
    })
    next_id += 1
    added += 1
    existing_paths.add(audio_path)

knowledge.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Added {added} items to {knowledge}")
PY
```

### Step 5: Run assistant with a given JSON

```bash
source .venv/bin/activate
python main_runner.py data/sas_knowledge.json
```

Loop behavior:
1. It records microphone input.
2. Press `Enter` to stop recording each turn.
3. It transcribes + answers using knowledge JSON + current session history.
4. It speaks and saves reply audio.
5. At prompt:
   - press `Enter` to stop the assistant loop,
   - or type anything and press `Enter` to continue next turn.
6. On exit it deletes `data/current_session_conversation.jsonl` automatically.

## 2) Metadata For Staged Files (Important)

These are the key files in the audio -> JSON staging pipeline.

| Path | Role | Metadata / Format |
|---|---|---|
| `data/call_recordings/**/*` | Raw downloaded audio staging area | File metadata: filename, extension, size, modified time, full path |
| `data/sas_dataset.jsonl` | Transcription staging output from `build_dataset.py` | JSONL rows: `id`, `audio_path`, `transcript` |
| `data/sas_knowledge.json` | Knowledge used by `main_runner.py` | JSON array rows: `item_id`, `source_type`, `source`, `text`, `meta.path` |
| `voice_input/*.wav` | Live user turns recorded by assistant | Per-turn WAV files (`0001.wav`, `0002.wav`, ...) |
| `tts_output/*.mp3` | Assistant spoken responses | Per-turn MP3 files (`0001.mp3`, `0002.mp3`, ...) |
| `data/current_session_conversation.jsonl` | Temporary current session context | JSONL rows: `timestamp`, `knowledge_json`, `input_audio_path`, `output_audio_path`, `user_text`, `assistant_text`; deleted on exit |

Quick check commands:

```bash
# count staged raw audio files
find data/call_recordings -type f \( -iname '*.wav' -o -iname '*.m4a' -o -iname '*.mp3' -o -iname '*.ogg' -o -iname '*.flac' -o -iname '*.aac' \) | wc -l

# count transcript rows
wc -l data/sas_dataset.jsonl

# count knowledge items
python - <<'PY'
import json
from pathlib import Path
p = Path("data/sas_knowledge.json")
print(len(json.loads(p.read_text(encoding="utf-8"))) if p.exists() else 0)
PY
```

Git staged file metadata (optional):

```bash
git diff --cached --name-status
git diff --cached --numstat
```

## 3) Core Files

| Path | Purpose |
|---|---|
| `main_runner.py` | Main loop runner using knowledge JSON + current-session conversation awareness |
| `build_dataset.py` | Batch-transcribe raw audio into JSONL dataset |
| `STT.py` | Microphone recording and ElevenLabs speech-to-text |
| `TTS.py` | ElevenLabs text-to-speech synthesis/playback |
| `gemini.py` | Gemini API call wrapper and Armenian response policy |
| `requirements.txt` | Python dependencies |

## 4) Keep Local (Do Not Push)

- `.env`
- `.venv/`
- `data/*.rar`
- `data/*.xlsx`
- `data/*.json`
- `data/*.jsonl`
- `data/call_recordings/`
- `voice_input/`
- `tts_output/`
