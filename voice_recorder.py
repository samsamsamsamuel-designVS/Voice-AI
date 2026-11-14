"""Bridge the keyboard-controlled browser recorder to the Python pipeline."""

import base64
import io
from pathlib import Path

from streamlit.components.v2 import component


_recorder = component(
    "push_to_talk_recorder",
    html='<button type="button">Start recording</button>'
         '<p role="status" aria-live="polite">Hold Space to record. Release to send.</p>',
    css='button {background:#209c9f;color:white;border:0;border-radius:10px;'
        'padding:12px 20px;cursor:pointer;font:16px sans-serif;}'
        'p {font:14px sans-serif;color:#626b70;}',
    js=Path(__file__).with_name("recorder.js").read_text(),
)


def record_question(turn_id: int):
    # A trigger is delivered once. The app also advances turn_id before making
    # requests, so unrelated reruns never resubmit a completed recording.
    result = _recorder(key=f"mic_{turn_id}", on_recording_change=lambda: None)
    encoded = result.recording
    if not encoded:
        return None
    if not isinstance(encoded, str) or len(encoded) > 32_000_000:
        raise ValueError("Recording is too large. Please record a shorter question.")
    return io.BytesIO(base64.b64decode(encoded, validate=True))
