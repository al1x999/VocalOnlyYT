import os
import gc
import sys
import torch
import soundfile as sf
from pathlib import Path
from typing import Dict, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
TEMP_SEP_DIR = BASE_DIR / "temp" / "separated"
TEMP_SEP_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR = BASE_DIR / "server" / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Set torch model cache directory inside server/models
os.environ["TORCH_HOME"] = str(MODELS_DIR)
os.environ["DEMUCS_CACHE"] = str(MODELS_DIR)

LOADED_MODEL = None
CURRENT_DEVICE = None


def get_device() -> torch.device:
    """Detects available hardware acceleration (CUDA GPU vs CPU)."""
    global CURRENT_DEVICE
    if CURRENT_DEVICE is not None:
        return CURRENT_DEVICE

    if torch.cuda.is_available():
        CURRENT_DEVICE = torch.device("cuda")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        CURRENT_DEVICE = torch.device("mps")
    else:
        # Multi-threaded CPU fallback
        threads = max(1, (os.cpu_count() or 4) // 2)
        torch.set_num_threads(threads)
        CURRENT_DEVICE = torch.device("cpu")

    return CURRENT_DEVICE


def load_separator_model(model_name: str = "mdx_extra"):
    """Loads Demucs / MDX-Net model lazily onto target device."""
    global LOADED_MODEL
    if LOADED_MODEL is not None:
        return LOADED_MODEL

    device = get_device()
    print(f"[AI Engine] Loading '{model_name}' on {device}...", flush=True)

    from demucs.pretrained import get_model
    model = get_model(name=model_name)
    model.to(device)
    model.eval()

    LOADED_MODEL = model
    return LOADED_MODEL


def separate_audio(input_wav_path: Path, output_dir: Path) -> Tuple[Path, Path]:
    """
    Separates full audio WAV file into vocals.wav and instrumental.wav.
    Preserves human voice quality, harmony, reverb, and stereo imaging.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    vocal_path = output_dir / "vocals.wav"
    no_vocal_path = output_dir / "instrumental.wav"

    if vocal_path.exists() and no_vocal_path.exists():
        return vocal_path, no_vocal_path

    device = get_device()
    model = load_separator_model("mdx_extra")

    from demucs.apply import apply_model
    from demucs.audio import AudioFile

    print(f"[AI Engine] Separating audio: {input_wav_path.name}", flush=True)
    wav = AudioFile(input_wav_path).read(streams=0, samplerate=model.samplerate, channels=model.audio_channels)
    ref = wav.mean(0)
    wav = (wav - ref.mean()) / ref.std()

    with torch.no_grad():
        sources = apply_model(model, wav[None].to(device), shifts=1, split=True, overlap=0.25)[0]

    sources = sources * ref.std() + ref.mean()

    # Demucs HT / MDX output order: [drums, bass, other, vocals]
    drums = sources[0].cpu()
    bass = sources[1].cpu()
    other = sources[2].cpu()
    vocals = sources[3].cpu()

    # Instrumental is the sum of drums + bass + other
    instrumental = drums + bass + other

    # Save 44.1kHz stereo WAV files
    sf.write(str(vocal_path), vocals.t().numpy(), model.samplerate)
    sf.write(str(no_vocal_path), instrumental.t().numpy(), model.samplerate)

    # Free RAM / VRAM
    del wav, sources, drums, bass, other, vocals, instrumental
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return vocal_path, no_vocal_path
