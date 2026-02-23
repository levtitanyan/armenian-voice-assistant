# Armenian Voice Assistant (STT -> FAQ/Gemini -> TTS)

Armenian HR assistant that:
1. Records voice from microphone.
2. Transcribes speech with ElevenLabs STT.
3. Answers from `data/faq.json` first (similar question matching).
4. Falls back to Gemini + `data/knowledge.json` context.
5. Speaks answer with ElevenLabs TTS.
6. Saves full session artifacts in `data/conversations/Conversation_###/`.

Main runner: `script/main_runner.py`

## Quick Start

### 1) Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env` in project root:

```env
ELEVENLABS_API_KEY=your_elevenlabs_key
GEMINI_API_KEY=your_gemini_key
```

Optional local playback (if `ffplay` is missing):

```bash
brew install ffmpeg
```

### 2) Prepare call audio

Put raw call audio in:

`data/call_records/`

Supported formats: `.m4a`, `.wav`, `.mp3`, `.ogg`, `.flac`, `.aac`, `.mp4`

If you have an archive:

```bash
mkdir -p data/call_records
unrar x -o+ data/call_records.rar data/call_records/
# or
unar -o data/call_records data/call_records.rar
```

### 3) Build transcripts + knowledge JSON

`script/build_dataset.py` does this:
1. Reads files from `data/call_records/`.
2. Reuses existing `.txt` transcripts from `data/transcripts/` when present.
3. Transcribes only missing ones.
4. Writes/updates `data/knowledge.json`.

Run:

```bash
.venv/bin/python script/build_dataset.py
```

Ranges:

```bash
# first 10
.venv/bin/python script/build_dataset.py --start-index 0 --max-files 10

# 11 to 20
.venv/bin/python script/build_dataset.py --start-index 10 --max-files 10

# custom chunk
.venv/bin/python script/build_dataset.py --start-index 35 --max-files 20
```

### 4) Run assistant

```bash
.venv/bin/python script/main_runner.py
```

Loop behavior:
1. Speak, then press `Enter` to finish the turn.
2. Assistant answers and starts listening again automatically.
3. Press `Esc` during recording to stop.
4. On stop, session is saved under `data/conversations/Conversation_###/`.

## FAQ JSON (Q/A Source)

File: `data/faq.json`

Format:

```json
{
  "items": [
    {
      "id": 1,
      "questions": ["barev", "բարև", "բարև ձեզ"],
      "answer": "..."
    }
  ]
}
```

Notes:
- `id` is the stable answer number.
- `questions` are variants that map to the same answer.
- One `id` should map to one final answer text.

## Generate Voice Files For FAQ Answers

Script: `script/faq-to-voice.py`

Generates one MP3 per FAQ answer id (for example `001_answer.mp3`, `002_answer.mp3`) and saves to `data/voice-answers/`.

```bash
.venv/bin/python script/faq-to-voice.py
```

Custom paths/options:

```bash
.venv/bin/python script/faq-to-voice.py \
  --faq-json data/faq.json \
  --output-dir data/voice-answers \
  --overwrite
```

Also writes manifest file:

`data/voice-answers/index.json`

## Project Structure

| Path | Purpose |
|---|---|
| `script/main_runner.py` | Main voice loop (STT -> FAQ/Gemini -> TTS) |
| `script/build_dataset.py` | Builds/updates transcripts and `data/knowledge.json` |
| `script/faq-to-voice.py` | Generates per-FAQ-answer MP3 files from `data/faq.json` |
| `script/json_analysis.py` | Summarizes `data/knowledge.json` |
| `script/STT.py` | Recording + transcription |
| `script/TTS.py` | Speech synthesis + playback + cache |
| `script/gemini.py` | Gemini response wrapper |
| `data/faq.json` | FAQ answers + question variants |
| `data/knowledge.json` | HR knowledge dataset used as Gemini context |
| `data/conversations/` | Saved session folders |
| `data/voice-answers/` | Pre-generated FAQ answer voices |

## Conversation Artifacts

Each run creates:

`data/conversations/Conversation_###/`

with:
- `voice_input/0001.wav`, `0002.wav`, ...
- `tts_output/0001.mp3`, `0002.mp3`, ...
- `conversation.json` (full turn history)

## Useful Checks

```bash
# raw audio count
find data/call_records -type f \( -iname '*.wav' -o -iname '*.m4a' -o -iname '*.mp3' -o -iname '*.ogg' -o -iname '*.flac' -o -iname '*.aac' -o -iname '*.mp4' \) | wc -l

# transcript count
find data/transcripts -type f -iname '*.txt' | wc -l

# knowledge item count
.venv/bin/python - <<'PY'
import json
from pathlib import Path
p = Path('data/knowledge.json')
print(len(json.loads(p.read_text(encoding='utf-8'))) if p.exists() else 0)
PY
```

## Keep Local (Do Not Push)

- `.env`
- `.venv/`
- `data/*.rar`
- `data/*.xlsx`
- `data/call_records/`
- `data/conversations/`
- `data/voice-answers/`
