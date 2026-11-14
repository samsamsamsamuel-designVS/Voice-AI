"""Run with: python -m streamlit run app.py --server.address 127.0.0.1"""

import streamlit as st
from openai import APIConnectionError, APIStatusError, AuthenticationError, OpenAI, RateLimitError

from voice_service import Settings, answer, speak, transcribe
from audio_player import reply_player
from voice_recorder import record_question


def friendly_error(error: Exception) -> str:
    """Explain common failures without exposing API keys or raw request bodies."""
    if isinstance(error, AuthenticationError):
        return "OpenAI rejected the API key. Check OPENAI_API_KEY in .env."
    if isinstance(error, RateLimitError):
        return "API quota or rate limit reached. Check your API billing, or retry shortly."
    if isinstance(error, APIConnectionError):
        return "Could not reach OpenAI. Check your connection and try again."
    if isinstance(error, APIStatusError):
        return f"OpenAI returned HTTP {error.status_code}. Check model names and account access."
    if isinstance(error, (ValueError, RuntimeError, TimeoutError)):
        return str(error)
    return "The request failed. Check your connection and model settings, then try again."


st.set_page_config(page_title="Ask Alice", page_icon="🎙️", layout="centered")
st.markdown("""
<style>
.stApp {background: #f6f5f1; color: #263238;}
.pipeline {display: flex; gap: 10px; margin: 22px 0 28px; flex-wrap: wrap;}
.stage {flex: 1; min-width: 100px; border-radius: 18px; padding: 22px 10px;
        text-align: center; background: #fff; border: 1px dashed #879398;}
.stage b {display: block; margin: 10px 0 6px;}
.stage small {opacity: .85;}
.stt {background: #209c9f; color: white; border: 0;}
.llm {background: #edb54d; color: #263238; border: 0;}
.tts {background: #e96c42; color: white; border: 0;}
</style>
""", unsafe_allow_html=True)
st.title("🎙️ Ask Alice")
st.write("Ask out loud. Hear an answer.")
st.markdown("""
<div class="pipeline">
 <div class="stage">🎙️<b>You</b><small>Record a question</small></div>
 <div class="stage stt">≋<b>Speech → text</b><small>Understand your words</small></div>
 <div class="stage llm">✦<b>AI reply</b><small>Think it through</small></div>
 <div class="stage tts">♫<b>Text → speech</b><small>Give it a voice</small></div>
 <div class="stage">🔊<b>Speakers</b><small>Listen to the answer</small></div>
</div>
""", unsafe_allow_html=True)
st.caption("The voice is AI-generated. Stopping a recording automatically sends it and conversation text to OpenAI.")

# Streamlit re-runs this script on interactions. Session state preserves history
# in memory; each recording gets a new ID before processing to avoid resubmission.
if "history" not in st.session_state:
    st.session_state.history = []
    st.session_state.recording_id = 0
st.session_state.setdefault("pending_playback", None)

try:
    settings = Settings.load()
except ValueError as error:
    st.info(str(error))
    st.code("OPENAI_API_KEY=your_key_here", language="bash")
    st.stop()

with st.sidebar:
    st.header("Your setup")
    st.caption("Edit .env to change these settings, then refresh.")
    st.caption("Web search is available for uncertain or current facts. Searches incur additional API usage.")
    st.text(f"Reply: {settings.model}\nListen: {settings.stt_model}\nSpeak: {settings.tts_model}\nVoice: {settings.voice}")
    autoplay = st.toggle("Play answers automatically", value=True)
    st.caption("If your browser blocks autoplay, press Play on the audio player.")
    if st.button("Clear conversation"):
        st.session_state.history = []
        st.session_state.recording_id += 1
        st.session_state.pending_playback = None
        st.rerun()

if notice := st.session_state.pop("notice", None):
    st.warning(notice)

for index, message in enumerate(st.session_state.history):
    with st.chat_message(message["role"]):
        st.markdown(message.get("markdown", message["content"]))
        if message.get("searched"):
            st.caption("Used web search")
        if message.get("audio"):
            if (st.session_state.pending_playback is not None
                    and message.get("turn_id") == st.session_state.pending_playback):
                reply_player(message["audio"], message["turn_id"], autoplay)
            else:
                st.audio(message["audio"], format="audio/wav")
        elif message["role"] == "assistant":
            if st.button("Retry audio", key=f"retry_{index}"):
                try:
                    with st.spinner("Creating speech…"):
                        message["audio"] = speak(settings, message["content"])
                    st.rerun()
                except Exception as error:
                    st.error(friendly_error(error))

# Wait for the browser's playback-completed callback, not speech generation.
# When autoplay is blocked or disabled, the user can start the visible player.
if st.session_state.pending_playback is not None:
    st.stop()

question_area = st.empty()
with question_area.container():
    st.subheader("Your next question")
    st.caption("Hold Space to talk; release to send. Keep this browser tab active. You can also click Start / Stop. Maximum two minutes.")
    try:
        recording = record_question(st.session_state.recording_id)
    except ValueError as error:
        st.session_state.recording_id += 1
        st.session_state.notice = str(error)
        st.rerun()

if recording is not None:
    # The recorder returns completed audio on key release or a Stop click. Consume
    # this recorder immediately, even if an API request fails, so a rerun cannot
    # send the same recording again or repeatedly charge for a failed question.
    turn_id = st.session_state.recording_id
    st.session_state.recording_id += 1
    question_area.empty()
    try:
        # A context manager closes the HTTP client after this turn.
        with OpenAI(api_key=settings.api_key, timeout=60, max_retries=1) as client:
            with st.spinner("1 / 3 · Turning speech into text…"):
                question = transcribe(client, settings, recording.getvalue())
            with st.chat_message("user"):
                st.write(question)
            with st.spinner("2 / 3 · Thinking and searching the web if needed…"):
                reply = answer(client, settings, st.session_state.history, question)

        # Save the text before creating audio so a voice error cannot lose it.
        st.session_state.history.extend([
            {"role": "user", "content": question},
            {"role": "assistant", "content": reply.text, "markdown": reply.markdown,
             "searched": reply.searched, "turn_id": turn_id},
        ])
        # Bound audio memory as well as model context to the last ten exchanges.
        st.session_state.history = st.session_state.history[-20:]
        with st.chat_message("assistant"):
            st.markdown(reply.markdown)
            if reply.searched:
                st.caption("Used web search")
            try:
                with st.spinner("3 / 3 · Creating speech…"):
                    audio = speak(settings, reply.text)
                st.session_state.history[-1]["audio"] = audio
                st.session_state.pending_playback = turn_id
            except Exception as error:
                st.session_state.notice = friendly_error(error)

        # Render the saved reply and its event-aware player. Once playback ends,
        # the component clears pending_playback and the fresh recorder appears.
        st.rerun()
    except Exception as error:
        st.session_state.notice = friendly_error(error)
        st.rerun()
