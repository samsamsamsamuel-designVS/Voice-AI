# Voice AI

A commented Python app following your reference image:

**Microphone → speech-to-text → language model → text-to-speech → speakers**

The interface runs locally in your browser using Streamlit. Record a question,
stop recording to send it automatically, and hear an AI-generated answer. This is turn-based recording, not
an always-listening assistant. No microphone drivers or FFmpeg are needed.

## Start on your Mac

The project already contains a `.venv` virtual environment and `.env` settings.

1. Open `.env` and replace `your_openai_api_key_here` with your OpenAI API key.
2. In Terminal:

   ```bash
   cd "/Users/samuellee/Desktop/AI Projects/Voice AI"
   source .venv/bin/activate
   python -m streamlit run app.py
   ```

3. Open http://localhost:8501 if the browser does not open automatically.
4. Keep the app tab active. **Hold Space to record; release Space to send.**
   Allow microphone access when asked, then hold Space again if you released it
   during the permission prompt. Alternatively, click **Start recording**, speak,
   then click **Stop and send**. The shortcut does not intercept typing in fields
   and is not a system-wide hotkey. Switching tabs/windows cancels the recording.
5. Releasing Space or stopping the recording automatically sends your question. The app shows
   progress through each AI stage; there is no separate Send button.
6. Listen to the answer. If autoplay is blocked, press Play. **Your next question**
   appears automatically when playback finishes; **Clear conversation** starts fresh.

Stop the server with `Ctrl+C` in Terminal.

For a fresh installation (Python 3.11 or newer):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
# Only if .env is missing; do not overwrite your saved key:
cp -n .env.example .env
python -m streamlit run app.py
```

## Settings

| Variable | Purpose | Default |
| --- | --- | --- |
| `OPENAI_API_KEY` | Your private API key | Placeholder; replace it |
| `OPENAI_MODEL` | Writes the answer | `gpt-4.1-mini` |
| `OPENAI_STT_MODEL` | Transcribes your recording | `gpt-transcribe` |
| `OPENAI_TTS_MODEL` | Reads the answer aloud using Realtime | `gpt-realtime-2.1-mini` |
| `OPENAI_VOICE` | Built-in speaking voice | `marin` |

Refresh after editing `.env`. Shell environment variables take precedence over
the file. Models must be available to your OpenAI project. Each submitted question
uses paid API requests; audio retries make another speech request. Replaying
already generated audio does not make an API request.

The image mentions a cloned voice. This version uses a built-in voice: it does
not clone anyone's voice. Custom voice creation is a separate workflow requiring
account eligibility and the speaker's consent.

## Learn from the code

- `app.py`: draws the five stages, captures microphone input, manages session
  history, shows progress, and plays the generated audio.
- `voice_service.py`: `transcribe()` handles speech recognition; `answer()` calls
  the Responses API; `speak()` requests audio over a WebSocket. `pcm_to_wav()`
  adds a WAV header to the returned raw audio samples.
- `.env`: private key and model settings, excluded from Git.
- `.env.example`: shareable settings template containing no credentials.
- `tests/test_voice_service.py`: offline tests using simulated service responses.

Comments explain the major steps and why they are needed. Conversation history
is kept in the browser session's server memory, capped at ten exchanges. Refresh
may reset the session; history is not saved to disk. Audio is buffered until
generation finishes. The Realtime model is instructed to read the reply verbatim,
but generative speech can differ from the displayed text.

## Troubleshooting

- **SSL certificate error:** the voice connection explicitly loads `certifi`'s
  trusted CA bundle, including on Macs where Python's default bundle is missing.
  Restart the app after updating the code. Certificate and hostname verification
  remain enabled.
- **No microphone:** enable the browser in macOS System Settings → Privacy &
  Security → Microphone, and allow microphone access for localhost in the browser.
  Select your microphone in the browser/system settings. Use localhost, not an
  unsecured remote IP, because browser recording requires a secure context.
- **No sound:** check your selected system output device and volume; press Play
  if the browser blocked autoplay. Stop playback before recording another question.
- **Authentication/quota error:** check your API key, OpenAI project access and API
  billing. A ChatGPT subscription does not itself configure this app's API access.
- **Model error:** set a model supported by the corresponding API and your project.
  `OPENAI_TTS_MODEL` must support Realtime audio, not the older Speech API.
- **Voice failure:** the text reply remains available. Return to the conversation
  and click **Retry audio**. This does not regenerate the written reply.
- **Long recording:** questions are limited to two minutes / 24 MB before upload.

Recordings and text are sent to OpenAI for processing. The key stays in the Python
backend. `.env` is ignored by Git, but don't share it manually. Clearing the local
conversation does not delete any provider-side logs. This app only answers
questions; it cannot operate your computer. It can use OpenAI's hosted web search
when facts are uncertain, current, or explicitly requested. The model decides
when to search; uncertainty detection is not guaranteed. Web-backed replies show
clickable inline sources and a “Used web search” label. Citation markers are
omitted from spoken audio. If evidence is insufficient, Alice is instructed to
say so. Search uses the same API key and incurs additional API charges; the
configured reply model must support the Responses API web search tool.

## Verification

```bash
python -m unittest discover -s tests -v
python -m py_compile app.py voice_service.py
```

Offline tests do not require an API key. A real microphone-to-speaker check needs
your API key, model access, and browser microphone permission.

## Official API references

- [File transcription](https://developers.openai.com/api/docs/guides/speech-to-text)
- [Text generation](https://developers.openai.com/api/docs/guides/text)
- [Realtime conversations](https://developers.openai.com/api/docs/guides/realtime-conversations)
- [Speech API migration notice](https://developers.openai.com/api/docs/guides/text-to-speech)
- [Custom voices](https://developers.openai.com/api/docs/guides/custom-voices)

The documentation checked on November 14, 2026 recommends Realtime for the
replacement speech workflow; the old Speech API models are scheduled to retire
January 6, 2027. This project therefore uses Realtime only for the final speaking
stage, preserving the inspectable three-stage pipeline from your diagram.
