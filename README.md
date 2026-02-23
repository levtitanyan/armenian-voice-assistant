# Armenian Voice Assistant

Voice HR assistant pipeline:
1. Record user speech from microphone.
2. Transcribe with selected STT provider (`gemini` or `elevenlabs`).
3. Use Gemini to match user intent against `data/faq.json` question variants.
4. If FAQ match exists, use FAQ answer.
5. If no FAQ match, generate short Armenian answer with Gemini using `data/knowledge.json` + current chat history.
6. Speak final answer with ElevenLabs TTS.
7. Save full session artifacts in a new `data/conversations/Conversation_###/` folder.

Main runtime: `script/main_runner.py`

## Requirements

- Python 3.10+
- Microphone access
- API keys:
  - `GEMINI_API_KEY`
  - `ELEVENLABS_API_KEY` (or `XI_API_KEY`)

Install:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env` in project root:

```env
GEMINI_API_KEY=your_gemini_key
ELEVENLABS_API_KEY=your_elevenlabs_key
```

Optional local playback dependency (`ffplay`):

```bash
brew install ffmpeg
```

## Quick Start

Run assistant (default: auto recording + Gemini STT):

```bash
.venv/bin/python script/main_runner.py
```

Run with explicit STT provider:

```bash
.venv/bin/python script/main_runner.py --stt-provider gemini
.venv/bin/python script/main_runner.py --stt-provider elevenlabs
```

Run in manual recording mode (Enter ends turn, Esc stops loop):

```bash
.venv/bin/python script/main_runner.py --manual-recording
```

Use custom knowledge JSON:

```bash
.venv/bin/python script/main_runner.py --knowledge-json data/knowledge.json
```

## Runtime Behavior

### Auto mode (default)
- Assistant prints: `Listening... start speaking. Press Esc to stop conversation.`
- Recording starts on detected speech and auto-stops on silence.
- Assistant replies with text + voice.
- It listens again automatically.
- Press `Esc` during listening/recording to stop and save conversation.

### Manual mode (`--manual-recording`)
- Assistant prints: `Recording... press Enter to finish turn, Esc to stop conversation.`
- Press `Enter` to finish each turn.
- Press `Esc` to stop and save conversation.

## Conversation Artifacts

Each run creates:

`data/conversations/Conversation_###/`

Containing:
- `voice_input/0001.wav`, `0002.wav`, ...
- `tts_output/0001.mp3`, `0002.mp3`, ...
- `conversation.json` (turn history, response source, file paths, metadata)

## Data Files

- `data/faq.json`: FAQ Q/A source. Expected shape:

```json
{
  "items": [
    {
      "id": 1,
      "questions": ["բարև", "barev"],
      "answer": "..."
    }
  ]
}
```

- `data/knowledge.json`: fallback knowledge context for Gemini generation.

## Prebuilt FAQ Voice Files

Generate/refresh one MP3 per FAQ answer:

```bash
.venv/bin/python script/faq-to-voice.py
```

Options:

```bash
.venv/bin/python script/faq-to-voice.py \
  --faq-json data/faq.json \
  --output-dir data/voice-answers \
  --overwrite
```

Notes:
- Files are generated as `{id}_answer.mp3` (zero-padded).
- Manifest is written to `data/voice-answers/index.json`.
- Runtime uses prebuilt audio only when manifest answer text matches current FAQ answer text; otherwise it safely falls back to fresh TTS generation.

## Build Knowledge Dataset

Build/update `data/knowledge.json` from `data/call_records` + `data/transcripts`:

```bash
.venv/bin/python script/build_dataset.py
```

Chunked processing:

```bash
.venv/bin/python script/build_dataset.py --start-index 0 --max-files 10
.venv/bin/python script/build_dataset.py --start-index 10 --max-files 10
```

What it does:
- Reuses existing transcript `.txt` files when available.
- Transcribes only missing audio files.
- Appends structured items into `data/knowledge.json`.

## STT/TTS/Gemini Defaults In Code

From current code defaults:
- STT provider default: `gemini`
- STT Gemini model: `gemini-2.5-flash-lite`
- FAQ match model: `gemini-2.5-flash-lite`
- Answer generation model: `gemini-2.5-flash-lite`
- ElevenLabs STT model: `scribe_v2`
- ElevenLabs TTS model: `eleven_v3`

If you want to change model IDs, edit:
- `script/STT.py`
- `script/gemini.py`

## Single-Turn STT Test Script

`script/STT.py` runs one recording + transcription and exits (not a loop):

```bash
.venv/bin/python script/STT.py
```

Use `script/main_runner.py` for continuous conversation loop.

## Project Layout

- `script/main_runner.py`: end-to-end assistant loop.
- `script/STT.py`: recording + transcription.
- `script/gemini.py`: FAQ semantic matching + fallback generation.
- `script/TTS.py`: speech synthesis + playback.
- `script/faq-to-voice.py`: prebuild FAQ answer audio files.
- `script/build_dataset.py`: dataset builder for knowledge context.
- `script/common.py`: shared path/text helpers.

## Troubleshooting

### `404 NOT_FOUND model ... is not found`
- Model ID is invalid or unavailable for your key.
- Use valid model names in `script/STT.py` and `script/gemini.py`.

### Assistant prints empty transcription
- Speech may be too short/quiet or filtered as non-Armenian.
- Try clearer/louder input or switch STT provider:

```bash
.venv/bin/python script/main_runner.py --stt-provider elevenlabs
```

### No audio playback
- Install ffmpeg so `ffplay` is available, or keep file output only.
