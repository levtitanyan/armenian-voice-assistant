# Armenian Voice Assistant (STT -> Gemini -> TTS)

This project records Armenian speech, transcribes it with ElevenLabs STT, generates an Armenian response with Gemini, and speaks it back with ElevenLabs TTS.

## 1) Project Files (What Each File Does)

| Path | Purpose |
|---|---|
| `STTT.py` | Main end-to-end runner: record -> transcribe -> Gemini answer -> TTS reply. |
| `STT.py` | Speech-to-text utilities: microphone recording and Armenian transcription. |
| `TTS.py` | Text-to-speech utilities: synthesize Armenian MP3 and optional playback. |
| `gemini.py` | Gemini client + Armenian answer generation prompt. |
| `build_dataset.py` | Transcribes audio files and appends rows to a JSONL dataset. |
| `requirements.txt` | Python dependencies. |
| `.env` | Local API keys (not for GitHub). |
| `.gitignore` | Files/folders excluded from Git. |
| `voice_input/` | Saved microphone recordings (`.wav`). |
| `tts_output/` | Saved assistant replies (`.mp3`). |
| `data/` | Local data folder for recordings, dataset JSON/JSONL, FAQ files. |

## 2) Setup

```bash
cd /path/to/your/project
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env` in project root:

```env
ELEVENLABS_API_KEY=your_elevenlabs_key
GEMINI_API_KEY=your_gemini_key
```

Optional (for local audio playback):

```bash
brew install ffmpeg
```

## 3) Run Full Pipeline

```bash
source .venv/bin/activate
python STTT.py
```

Flow:
1. Records your microphone input.
2. Transcribes speech to text.
3. Sends text to Gemini (Armenian answer).
4. Converts answer to MP3 and plays/saves it.

## 4) Build Dataset From Audio (Code + Command)

`build_dataset.py` takes audio files, transcribes them, and writes dataset rows to JSONL.

Run:

```bash
python build_dataset.py --audio-dir data/call_recordings --dataset-out data/sas_dataset.jsonl
```

Limit to first 50 files:

```bash
python build_dataset.py --audio-dir data/call_recordings --dataset-out data/sas_dataset.jsonl --max-files 50
```

First 40 files:

```bash
python build_dataset.py --audio-dir data/call_recordings --dataset-out data/sas_dataset.jsonl --start-index 0 --max-files 40
```

Next 40 files (files 41-80):

```bash
python build_dataset.py --audio-dir data/call_recordings --dataset-out data/sas_dataset.jsonl --start-index 40 --max-files 40
```

Skip files already present in dataset:

```bash
python build_dataset.py --audio-dir data/call_recordings --dataset-out data/sas_dataset.jsonl --skip-existing
```

Overwrite dataset file:

```bash
python build_dataset.py --audio-dir data/call_recordings --dataset-out data/sas_dataset.jsonl --overwrite
```

Row format written to JSONL:

```json
{"id":"sample-00001","audio_path":"/abs/path/file.m4a","transcript":"..."}
```

Tip:
- Use `--skip-existing` to resume safely if previous runs were interrupted.

## 5) Run With Downloaded JSON (Separate Guide)

If you downloaded a JSON file, place it in `data/` (example: `data/sas_knowledge.json`).

Current code version does not automatically use `sas_knowledge.json` inside `STTT.py`.
It is treated as local data storage unless you extend runtime retrieval logic.

## 6) `STTT.py` Options (Including Conversation Save / No Save)

```bash
python STTT.py \
  [--input-file INPUT_FILE] \
  [--output-file OUTPUT_FILE] \
  [--voice-id VOICE_ID] \
  [--tts-model TTS_MODEL] \
  [--no-play] \
  [--save-conversation | --no-save-conversation] \
  [--conversation-file CONVERSATION_FILE]
```

| Parameter | Default | Description |
|---|---|---|
| `--input-file` | auto-incremented `0001.wav`, `0002.wav`, ... | Input recording filename inside `voice_input/`. |
| `--output-file` | auto-incremented `0001.mp3`, `0002.mp3`, ... | Output reply filename inside `tts_output/`. |
| `--voice-id` | `JBFqnCBsd6RMkjVDRZzb` | ElevenLabs voice ID for reply speech. |
| `--tts-model` | `eleven_v3` | ElevenLabs TTS model. |
| `--no-play` | off | Save MP3 but skip immediate playback. |
| `--save-conversation` | off | Save conversation row to JSONL after each run. |
| `--no-save-conversation` | on (default behavior) | Explicitly disable conversation saving. |
| `--conversation-file` | `data/conversations.jsonl` | Destination JSONL file for saved conversation rows. |

### Conversation Not Saved (Default)

```bash
python STTT.py
```

### Conversation Saved

```bash
python STTT.py --save-conversation
```

### Conversation Saved to Custom File

```bash
python STTT.py --save-conversation --conversation-file data/my_calls.jsonl
```

Each saved conversation row format:

```json
{"timestamp":"2026-02-20T17:30:00","input_audio_path":"...wav","output_audio_path":"...mp3","user_text":"...","assistant_text":"..."}
```

## 7) Run Each Module Separately

STT only:

```bash
python STT.py
```

Gemini only:

```bash
python gemini.py
```

TTS only:

```bash
python TTS.py
```

## 8) GitHub: What To Keep Local

Keep local (do not push):
- `.env`
- `data/` files (`.rar`, `.xlsx`, `.json`, `.jsonl`)
- `voice_input/`
- `tts_output/`
- `.venv/`

Push code/docs only:
- `STTT.py`, `STT.py`, `TTS.py`, `gemini.py`, `build_dataset.py`, `requirements.txt`, `README.md`, `.gitignore`
