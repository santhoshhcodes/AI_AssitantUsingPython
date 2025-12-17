from faster_whisper import WhisperModel

# Load model once
model = WhisperModel(
    "small",
    device="cpu",
    compute_type="int8"
)

def transcribe_audio(audio_file: str) -> str:
    """
    Transcribe & TRANSLATE any language → English
    """
    print("Running Faster-Whisper on:", audio_file)

    try:
        segments, info = model.transcribe(
            audio_file,
            task="translate",  
            beam_size=1,
            vad_filter=True,
            temperature=0.0
        )

        text = " ".join(seg.text for seg in segments).strip()

        print("Detected language:", info.language, "prob:", info.language_probability)
        print("Translated Text (EN):", text)

        return text

    except Exception as e:
        print("Whisper Error:", e)
        return ""
