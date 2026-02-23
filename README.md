# Armenian Voice Assistant

Armenian HR assistant pipeline:
1. Record user voice from microphone.
2. Transcribe speech with ElevenLabs STT.
3. Use Gemini to match the transcribed question against `questions` in `data/faq.json`.
4. If a FAQ match is found, use that FAQ answer.
5. If no match is found, generate an answer with Gemini using `data/knowledge.json` context.
6. Convert the final answer to speech with ElevenLabs TTS.

Main runner: `script/main_runner.py`

## Setup

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

Optional local playback dependency:

```bash
brew install ffmpeg
```

## Run Assistant

```bash
.venv/bin/python script/main_runner.py
```

Loop behavior:
1. The assistant listens automatically; when you start speaking, it records your turn.
2. When you stop speaking, the turn ends automatically and the assistant replies with voice.
3. After assistant playback ends, listening starts again for your next turn.
4. Press `Esc` during listening/recording to stop the session.
5. Optional: run with `--manual-recording` to use Enter/Esc turn control.
6. Conversation artifacts are saved under `data/conversations/Conversation_###/`.

## FAQ JSON Format

File: `data/faq.json`

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

## Generate Prebuilt FAQ Voices

Generate one MP3 per FAQ answer:

```bash
.venv/bin/python script/faq-to-voice.py
```

With custom options:

```bash
.venv/bin/python script/faq-to-voice.py \
  --faq-json data/faq.json \
  --output-dir data/voice-answers \
  --overwrite
```

## Build Knowledge Dataset

`script/build_dataset.py` builds/updates `data/knowledge.json` from `data/call_records` and `data/transcripts`:

```bash
.venv/bin/python script/build_dataset.py
```

Limit by range:

```bash
.venv/bin/python script/build_dataset.py --start-index 0 --max-files 10
```

## Project Structure

- `script/main_runner.py`: Main voice loop.
- `script/gemini.py`: Gemini FAQ matching + answer generation.
- `script/STT.py`: Recording + transcription.
- `script/TTS.py`: TTS generation + playback.
- `script/build_dataset.py`: Knowledge dataset builder.
- `script/faq-to-voice.py`: FAQ voice file generator.
- `script/common.py`: Shared path/text helpers.
- `data/faq.json`: FAQ questions and answers.
- `data/knowledge.json`: Knowledge context for fallback generation.
