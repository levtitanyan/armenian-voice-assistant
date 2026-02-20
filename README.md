# Armenian Voice Assistant (STT -> Gemini -> TTS)

This project records Armenian speech, transcribes it with ElevenLabs STT, generates an Armenian response with Gemini, and speaks it back with ElevenLabs TTS.

## 1) Project Files (What Each File Does)

| Path | Purpose |
|---|---|
| `STTT.py` | Main end-to-end runner: record -> transcribe -> Gemini answer -> TTS reply. |
| `STT.py` | Speech-to-text utilities: microphone recording and Armenian transcription. |
| `TTS.py` | Text-to-speech utilities: synthesize Armenian MP3 and optional playback. |
| `gemini.py` | Gemini client + Armenian answer generation prompt. |
| `requirements.txt` | Python dependencies. |
| `.env` | Local secrets (API keys). Not for GitHub. |
| `.gitignore` | Files/folders excluded from Git. |
| `voice_input/` | Saved microphone recordings (`.wav`). |
| `tts_output/` | Saved assistant replies (`.mp3`). |
| `data/call_records.rar` | Optional dataset archive (local only). |
| `data/sas_knowledge.json` | Optional dataset file (local only, not used by current code). |
| `data/Հաճախակի տրվող հարցեր.xlsx` | Optional FAQ data file (local only). |

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

## 4) Run Each Part Separately

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

## 5) Run With a Downloaded JSON (Separate Guide)

If you downloaded `sas_knowledge.json`, place it here:

```text
data/sas_knowledge.json
```

Current code version does not consume this JSON automatically in `STTT.py`.
It is stored as optional local data for future knowledge-enabled logic.

## 6) `STTT.py` Options (All Current Parameters)

```bash
python STTT.py \
  [--input-file INPUT_FILE] \
  [--output-file OUTPUT_FILE] \
  [--voice-id VOICE_ID] \
  [--tts-model TTS_MODEL] \
  [--no-play]
```

| Parameter | Default | Description |
|---|---|---|
| `--input-file` | auto timestamped `.wav` | Input recording filename inside `voice_input/`. |
| `--output-file` | auto timestamped `.mp3` | Output reply filename inside `tts_output/`. |
| `--voice-id` | `JBFqnCBsd6RMkjVDRZzb` | ElevenLabs voice ID for reply speech. |
| `--tts-model` | `eleven_v3` | ElevenLabs TTS model. |
| `--no-play` | off | Save MP3 but skip immediate playback. |

Examples:

```bash
python STTT.py
python STTT.py --no-play
python STTT.py --input-file my_input.wav --output-file my_reply.mp3
python STTT.py --voice-id JBFqnCBsd6RMkjVDRZzb --tts-model eleven_v3
```

## 7) GitHub: What To Keep Local

Keep local (do not push):
- `.env`
- `data/` files (`.rar`, `.xlsx`, `.json`)
- `voice_input/`
- `tts_output/`
- `.venv/`

Push code/docs only:
- `STTT.py`, `STT.py`, `TTS.py`, `gemini.py`, `requirements.txt`, `README.md`, `.gitignore`
