// Browser-side push-to-talk. Python receives one completed WAV, never key events.
export default function(component) {
    const { parentElement, setTriggerValue } = component;
    const button = parentElement.querySelector('button');
    const status = parentElement.querySelector('[role="status"]');
    let held = false, busy = false, disposed = false, cancelled = false;
    let recorder = null, stream = null, timer = null;
    const say = text => { status.textContent = text; };
    const releaseMic = () => { stream?.getTracks().forEach(t => t.stop()); stream = null; };

    // Convert the browser's native recording format to the mono PCM WAV expected
    // by voice_service.py. No external encoder or microphone driver is needed.
    async function toWav(blob) {
        const context = new AudioContext();
        try {
            const audio = await context.decodeAudioData(await blob.arrayBuffer());
            const size = audio.length;
            const bytes = new ArrayBuffer(44 + size * 2);
            const view = new DataView(bytes);
            const word = (offset, text) => [...text].forEach((c, i) => view.setUint8(offset+i, c.charCodeAt(0)));
            word(0, 'RIFF'); view.setUint32(4, 36 + size*2, true); word(8, 'WAVE');
            word(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
            view.setUint16(22, 1, true); view.setUint32(24, audio.sampleRate, true);
            view.setUint32(28, audio.sampleRate*2, true); view.setUint16(32, 2, true);
            view.setUint16(34, 16, true); word(36, 'data'); view.setUint32(40, size*2, true);
            const channels = Array.from({length: audio.numberOfChannels}, (_, c) => audio.getChannelData(c));
            for (let i = 0; i < size; i++) {
                const sample = Math.max(-1, Math.min(1, channels.reduce((sum, ch) => sum+ch[i], 0)/channels.length));
                view.setInt16(44+i*2, sample * (sample < 0 ? 32768 : 32767), true);
            }
            const data = new Uint8Array(bytes);
            let binary = '';
            for (let i = 0; i < data.length; i += 8192) {
                binary += String.fromCharCode(...data.subarray(i, i+8192));
            }
            return btoa(binary);
        } finally { await context.close(); }
    }

    function stop(discard = false) {
        cancelled = discard;
        held = false;
        clearTimeout(timer);
        if (recorder?.state === 'recording') {
            recorder.stop();
            releaseMic();
            say(discard ? 'Recording cancelled. Hold Space to try again.' : 'Sending your question…');
            button.textContent = 'Start recording';
        }
    }

    async function start(fromKeyboard) {
        if (busy || disposed) return;
        busy = true;
        cancelled = false;
        say('Opening microphone…');
        try {
            stream = await navigator.mediaDevices.getUserMedia({audio: true});
            // Permission prompts can outlast the key press. Never start a hidden
            // recording if the user already released Space or switched tabs.
            if (disposed || cancelled || (fromKeyboard && !held)) {
                releaseMic(); busy = false;
                say('Microphone ready. Hold Space to record.');
                return;
            }
            const chunks = [];
            recorder = new MediaRecorder(stream);
            recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data); };
            recorder.onstop = async () => {
                if (disposed || cancelled) { busy = false; return; }
                try {
                    const wav = await toWav(new Blob(chunks, {type: recorder.mimeType}));
                    if (!disposed && !cancelled) setTriggerValue('recording', wav);
                } catch (_) {
                    busy = false;
                    say('Could not read that recording. Hold Space and speak a little longer.');
                } finally {
                    if (cancelled) busy = false;
                }
            };
            recorder.onerror = () => {
                stop(true); releaseMic(); busy = false;
                say('Microphone recording failed. Please try again.');
            };
            recorder.start();
            button.textContent = 'Stop and send';
            say('Recording… release Space to send (or click Stop).');
            // Stop just below the server's two-minute limit to allow encoder padding.
            timer = setTimeout(() => stop(), 119000);
        } catch (_) {
            releaseMic(); busy = false; held = false;
            say('Allow microphone access in your browser, then try again.');
        }
    }

    function keydown(event) {
        if (event.code !== 'Space' || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
        const target = event.composedPath()[0];
        // Keep normal typing, buttons, and media controls accessible.
        if (target !== button && target?.closest?.('input, textarea, select, button, audio, video, [contenteditable="true"], [role="button"]')) return;
        event.preventDefault();
        if (event.repeat || held || busy) return;
        held = true;
        start(true);
    }
    function keyup(event) {
        if (event.code === 'Space' && held) { event.preventDefault(); stop(); }
    }
    function blur() { if (busy) stop(true); }
    function visibility() { if (document.hidden) blur(); }
    button.onclick = () => { if (recorder?.state === 'recording') stop(); else start(false); };
    document.addEventListener('keydown', keydown);
    document.addEventListener('keyup', keyup);
    window.addEventListener('blur', blur);
    document.addEventListener('visibilitychange', visibility);
    return () => {
        disposed = true; stop(true); releaseMic();
        document.removeEventListener('keydown', keydown);
        document.removeEventListener('keyup', keyup);
        window.removeEventListener('blur', blur);
        document.removeEventListener('visibilitychange', visibility);
    };
}
