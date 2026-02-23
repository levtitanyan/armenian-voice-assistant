# Armenian Voice Assistant (STT -> Gemini -> TTS)

This project:
1. records Armenian speech from microphone,
2. transcribes with ElevenLabs STT,
3. answers with Gemini using a provided JSON knowledge file,
4. speaks the answer with ElevenLabs TTS.

The main entrypoint is `script/main_runner.py`.

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

Put raw call audio files (`.m4a`, `.wav`, `.mp3`, `.ogg`, `.flac`, `.aac`, `.mp4`) under:

`data/call_records/`

Example (if you use the existing archive):

```bash
mkdir -p data/call_records
# option A
unrar x -o+ data/call_records.rar data/call_records/
# option B
unar -o data/call_records data/call_records.rar
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

### Step 3: Build transcripts + knowledge JSON

This step does all of this automatically:
1. Reads audio from `data/call_records`.
2. Reuses existing TXT in `data/transcripts` if matching transcript exists.
3. Transcribes only missing ones and creates new TXT files.
4. Writes/updates `data/knowledge.json`.

Run all remaining files:

```bash
python script/build_dataset.py
```

Chunk examples:

```bash
# first 10 files
python script/build_dataset.py --start-index 0 --max-files 10

# files 11 to 20
python script/build_dataset.py --start-index 10 --max-files 10

# next 20 after first 35
python script/build_dataset.py \
  --start-index 35 \
  --max-files 20
```

### Step 4: Run assistant

```bash
source .venv/bin/activate
python script/main_runner.py
```

Loop behavior:
1. It records microphone input.
2. Press `Enter` to finish a turn.
3. It transcribes + answers using knowledge JSON + current session history.
4. It immediately starts listening again after each answer (no continue prompt).
5. Press `Esc` during recording to stop the assistant loop.
6. On exit it saves the whole session under `io/Conversation_###/` with:
   - `voice_input/*.wav`
   - `tts_output/*.mp3`
   - `conversation.json`

## 2) Metadata For Staged Files (Important)

These are the key files in the audio -> JSON staging pipeline.

| Path | Role | Metadata / Format |
|---|---|---|
| `data/call_records/**/*` | Raw downloaded audio staging area | File metadata: filename, extension, size, modified time, full path |
| `data/transcripts/*.txt` | Reused/generated transcript staging | One TXT transcript per call recording |
| `data/knowledge.json` | Knowledge used by `script/main_runner.py` | JSON array rows: `item_id`, `source_type`, `source`, `text`, `meta.audio_path`, `meta.transcript_path` |
| `io/Conversation_###/voice_input/*.wav` | Live user turns recorded by assistant | Per-turn WAV files (`0001.wav`, `0002.wav`, ...) |
| `io/Conversation_###/tts_output/*.mp3` | Assistant spoken responses | Per-turn MP3 files (`0001.mp3`, `0002.mp3`, ...) |
| `io/Conversation_###/conversation.json` | Full session artifact saved on exit | JSON object: `conversation_id`, `started_at`, `ended_at`, `knowledge_json`, `turn_count`, `turns[]` |

Quick check commands:

```bash
# count staged raw audio files
find data/call_records -type f \( -iname '*.wav' -o -iname '*.m4a' -o -iname '*.mp3' -o -iname '*.ogg' -o -iname '*.flac' -o -iname '*.aac' -o -iname '*.mp4' \) | wc -l

# count transcript txt files
find data/transcripts -type f -iname '*.txt' | wc -l

# count knowledge items
python - <<'PY'
import json
from pathlib import Path
p = Path("data/knowledge.json")
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
| `script/main_runner.py` | Main loop runner using knowledge JSON + current-session conversation awareness |
| `script/build_dataset.py` | Reuse/create TXT transcripts and build `data/knowledge.json` |
| `script/json_analysis.py` | Analyze `data/knowledge.json` and produce HR answer summary/playbook |
| `script/STT.py` | Microphone recording and ElevenLabs speech-to-text |
| `script/TTS.py` | ElevenLabs text-to-speech synthesis/playback |
| `script/gemini.py` | Gemini API call wrapper and Armenian response policy |
| `requirements.txt` | Python dependencies |

## 4) Keep Local (Do Not Push)

- `.env`
- `.venv/`
- `data/*.rar`
- `data/*.xlsx`
- `data/*.json`
- `data/*.jsonl`
- `data/call_records/`
- `io/`
