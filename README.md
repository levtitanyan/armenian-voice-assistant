# Armenian Voice Assistant (STT -> Gemini -> TTS)

This project records your voice in Armenian, transcribes it, gets a Gemini response in Armenian, then generates and plays back an MP3 reply.

## 1) Setup

```bash
cd /path/to/your/project
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
ELEVENLABS_API_KEY=your_elevenlabs_key
GEMINI_API_KEY=your_gemini_key
```

Optional (for playback with `ffplay`):

```bash
brew install ffmpeg
```

## 2) Run

Run the script that orchestrates the full pipeline (STT -> Gemini -> TTS).
In this project, that script is `STTT.py`.

```bash
source .venv/bin/activate
python STTT.py
```

Press Enter to stop recording.

## 3) Output Folders

- Input recordings: `voice_input/`
- Generated replies: `tts_output/`

## 4) Useful Options

```bash
python STTT.py --no-play
python STTT.py --input-file my_input.wav --output-file my_reply.mp3
```

If your full-pipeline script has a different filename, run that file instead of `STTT.py`.
