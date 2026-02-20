# Armenian Voice Assistant (STT -> Gemini -> TTS)

This project records Armenian speech, transcribes it, generates an Armenian answer with Gemini, and speaks the reply as MP3.
It also supports SAS HR knowledge retrieval from call recordings + FAQ Excel.

## 1) Project Files

| File | Purpose |
|---|---|
| `STTT.py` | Main interactive call session (multi-turn loop). |
| `STT.py` | Audio recording + Armenian speech-to-text helpers. |
| `TTS.py` | Armenian text-to-speech helpers (save/play MP3). |
| `gemini.py` | Gemini response generation (with or without knowledge). |
| `prepare_sas_knowledge.py` | Build knowledge JSON from recordings + FAQ Excel. |
| `sas_knowledge.py` | Knowledge loading, parsing, retrieval, and context formatting. |
| `requirements.txt` | Python dependencies. |
| `.env` | API keys (`ELEVENLABS_API_KEY`, `GEMINI_API_KEY`). |
| `data/call_records.rar` | Source call recordings archive. |
| `data/transcripts/` | Generated transcript `.txt` files. |
| `data/sas_knowledge.json` | Built knowledge base used by assistant. |
| `data/session_history.json` | Temporary session history (auto-deleted by default). |
| `voice_input/` | Recorded user audio (`.wav`). |
| `tts_output/` | Assistant reply audio (`.mp3`). |

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

Optional (for playback):

```bash
brew install ffmpeg
```

## 3) Build Knowledge (One-Time / When Data Changes)

Build from recordings + FAQ:

```bash
source .venv/bin/activate
python prepare_sas_knowledge.py --faq "data/Հաճախակի տրվող հարցեր.xlsx"
```

This creates/updates:
- `data/transcripts/*.txt`
- `data/sas_knowledge.json`

If transcripts already exist and you only want to rebuild JSON:

```bash
python prepare_sas_knowledge.py --skip-transcribe --faq "data/Հաճախակի տրվող հարցեր.xlsx"
```

## 4) Run Assistant (Hands-Free Call Session)

```bash
source .venv/bin/activate
python STTT.py --knowledge-file data/sas_knowledge.json
```

Call behavior:
- Assistant listens automatically for each turn.
- When you stop speaking (silence), it ends recording and starts answering.
- Assistant transcribes, answers, and speaks the reply.
- After reply audio, it automatically starts listening again.
- Press Enter at any time to end the full call session.

History behavior:
- During call: history is written to `data/session_history.json`.
- On call end: history file is deleted automatically.
- Use `--keep-history` to keep the JSON.

## 5) `STTT.py` Parameters

| Parameter | Default | Description |
|---|---|---|
| `--input-file` | `None` | Optional input WAV filename template in `voice_input/`. |
| `--output-file` | `None` | Optional output MP3 filename template in `tts_output/`. |
| `--voice-id` | `JBFqnCBsd6RMkjVDRZzb` | ElevenLabs voice ID for assistant reply. |
| `--tts-model` | `eleven_v3` | ElevenLabs TTS model ID. |
| `--no-play` | `False` | Disable playback (still saves MP3). |
| `--knowledge-file` | `data/sas_knowledge.json` | Knowledge JSON path. |
| `--top-k` | `5` | Number of retrieved knowledge chunks per turn. |
| `--no-knowledge` | `False` | Disable retrieval and use base Gemini prompt only. |
| `--history-file` | `data/session_history.json` | Temporary conversation history JSON path. |
| `--history-turns` | `4` | Number of previous turns included as context. |
| `--keep-history` | `False` | Keep history JSON instead of auto-deleting. |
| `--silence-seconds` | `1.2` | Silence duration that ends a user turn. |
| `--energy-threshold` | `0.012` | Voice activity threshold for speech detection. |

Examples:

```bash
python STTT.py --knowledge-file data/sas_knowledge.json
python STTT.py --knowledge-file data/sas_knowledge.json --no-play
python STTT.py --knowledge-file data/sas_knowledge.json --history-turns 8
python STTT.py --knowledge-file data/sas_knowledge.json --keep-history
python STTT.py --knowledge-file data/sas_knowledge.json --silence-seconds 1.0 --energy-threshold 0.015
python STTT.py --no-knowledge
```

## 6) `prepare_sas_knowledge.py` Parameters

| Parameter | Default | Description |
|---|---|---|
| `--rar` | `data/call_records.rar` | Path to call recordings archive. |
| `--extract-dir` | `data/call_recordings` | Directory to extract archive files. |
| `--transcripts-dir` | `data/transcripts` | Directory for generated transcript `.txt` files. |
| `--faq` | `None` | Path to FAQ Excel (`.xlsx`). |
| `--knowledge-out` | `data/sas_knowledge.json` | Output knowledge JSON file. |
| `--max-files` | `0` | Limit transcriptions to first N files (`0` = all). |
| `--skip-transcribe` | `False` | Skip transcription and rebuild JSON from existing transcripts. |

Examples:

```bash
python prepare_sas_knowledge.py --faq "data/Հաճախակի տրվող հարցեր.xlsx"
python prepare_sas_knowledge.py --max-files 50 --faq "data/Հաճախակի տրվող հարցեր.xlsx"
python prepare_sas_knowledge.py --skip-transcribe --faq "data/Հաճախակի տրվող հարցեր.xlsx"
```

## 7) Run From Another Folder

Use absolute paths:

```bash
source /path/to/STT-TTS/.venv/bin/activate
python /path/to/STT-TTS/STTT.py --knowledge-file /path/to/STT-TTS/data/sas_knowledge.json
```
