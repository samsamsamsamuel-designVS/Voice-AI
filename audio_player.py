"""A browser audio player that tells Python when playback actually finishes."""

import base64

import streamlit as st
from streamlit.components.v2 import component


# A timer would finish too early when playback pauses or buffers. The browser's
# ended event fires only after the actual audio reaches its end.
PLAYER_JS = """
export default function(component) {
    const { data, parentElement, setTriggerValue } = component;
    const player = parentElement.querySelector('audio');
    const hint = parentElement.querySelector('p');
    player.src = 'data:audio/wav;base64,' + data.audio;
    player.onended = () => setTriggerValue('finished', true);
    player.onerror = () => setTriggerValue('failed', true);
    if (data.autoplay) {
        player.play().catch(() => {
            hint.textContent = 'Press Play to hear the reply. Your next question appears when it finishes.';
        });
    }
    return () => {
        player.onended = null;
        player.onerror = null;
        player.pause();
    };
}
"""

_player = component(
    "voice_reply_player",
    html='<audio controls aria-label="Spoken reply" style="width:100%"></audio>'
         '<p>Listen to the reply. Your next question will appear automatically.</p>',
    css="p {font: 14px sans-serif; color: #626b70;}",
    js=PLAYER_JS,
)


def playback_finished():
    """Component callbacks run before Streamlit automatically reruns the app."""
    st.session_state.pending_playback = None


def playback_failed():
    # Don't leave the microphone hidden if the browser cannot play the audio.
    playback_finished()
    st.session_state.notice = "The browser could not play the reply. You can ask another question."


def reply_player(audio: bytes, turn_id: int, autoplay: bool):
    _player(
        key=f"reply_player_{turn_id}",
        data={"audio": base64.b64encode(audio).decode("ascii"), "autoplay": autoplay},
        on_finished_change=playback_finished,
        on_failed_change=playback_failed,
    )
