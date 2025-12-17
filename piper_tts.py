import subprocess
import uuid
import os
import base64

PIPER_EXE = r"C:\Users\LENOVO\piper\piper.exe"            # adjust to your piper.exe path
PIPER_MODEL = r"C:\Users\LENOVO\piper\models\en_US-amy-medium.onnx"  # adjust model path

def synthesize(text: str) -> str:
    if not text or not text.strip():
        return ""

    MAX_TTS_CHARS = 500
    if len(text) > MAX_TTS_CHARS:
        text = text[:MAX_TTS_CHARS]

    import re
    text = re.sub(r"[^\x00-\x7F]+", "", text)

    out_file = f"piper_out_{uuid.uuid4().hex}.wav"

    cmd = [
        PIPER_EXE,
        "--model", PIPER_MODEL,
        "--output_file", out_file
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        proc.stdin.write(text.encode("utf-8"))
        proc.stdin.close()

        proc.communicate(timeout=45)

        if proc.returncode != 0:
            return ""

        with open(out_file, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode("utf-8")

        return audio_b64

    except Exception as e:
        print("Piper error:", e)
        return ""
    finally:
        if os.path.exists(out_file):
            os.remove(out_file)
