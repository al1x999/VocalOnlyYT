import os
import gc
import sys
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


def get_device(target: str = "auto"):
    """Detects available hardware acceleration (CUDA GPU vs CPU)."""
    global CURRENT_DEVICE
    import torch

    if target == "cpu":
        threads = max(1, (os.cpu_count() or 4) // 2)
        torch.set_num_threads(threads)
        return torch.device("cpu")
    elif target == "cuda" and torch.cuda.is_available():
        return torch.device("cuda")

    if CURRENT_DEVICE is not None:
        return CURRENT_DEVICE

    if torch.cuda.is_available():
        CURRENT_DEVICE = torch.device("cuda")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        CURRENT_DEVICE = torch.device("mps")
    else:
        # Multi-threaded CPU fallback capped to prevent 100% thread starvation
        threads = max(1, (os.cpu_count() or 4) // 2)
        torch.set_num_threads(threads)
        CURRENT_DEVICE = torch.device("cpu")

    return CURRENT_DEVICE


def load_separator_model(model_name: str = "mdx_extra", target_device: str = "auto"):
    """Loads Demucs / MDX-Net model lazily onto target device."""
    global LOADED_MODEL
    if LOADED_MODEL is not None and getattr(LOADED_MODEL, "_model_name", None) == model_name:
        return LOADED_MODEL

    device = get_device(target_device)
    print(f"[AI Engine] Loading '{model_name}' on {device} (Low-Resource Mode)...", flush=True)

    from demucs.pretrained import get_model
    model = get_model(name=model_name)
    model._model_name = model_name
    model.to(device)
    model.eval()

    LOADED_MODEL = model
    return LOADED_MODEL


def separate_audio(input_wav_path: Path, output_dir: Path, quality: str = "fast", device_setting: str = "auto") -> Tuple[Path, Path]:
    """
    Separates full audio WAV file into vocals.wav and instrumental.wav.
    Optimized for low GPU/CPU consumption and fast processing on low-end PCs.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    vocal_path = output_dir / "vocals.wav"
    no_vocal_path = output_dir / "instrumental.wav"

    if vocal_path.exists() and no_vocal_path.exists():
        return vocal_path, no_vocal_path

    import torch
    import soundfile as sf
    from demucs.apply import apply_model
    from demucs.audio import AudioFile

    # Quality preset mapping
    if quality == "high":
        model_name = "htdemucs_ft"
        shifts = 1
    elif quality == "balanced":
        model_name = "htdemucs"
        shifts = 0
    else: # fast (default)
        model_name = "mdx_extra"
        shifts = 0

    device = get_device(device_setting)
    model = load_separator_model(model_name, device_setting)

    print(f"[AI Engine] Separating audio: {input_wav_path.name} (Quality: {quality}, Shifts: {shifts}, Device: {device})", flush=True)
    wav = AudioFile(input_wav_path).read(streams=0, samplerate=model.samplerate, channels=model.audio_channels)
    ref = wav.mean(0)
    wav = (wav - ref.mean()) / ref.std()

    use_autocast = device.type == "cuda"

    with torch.no_grad():
        if use_autocast:
            try:
                with torch.cuda.amp.autocast():
                    sources = apply_model(model, wav[None].to(device), shifts=shifts, split=True, overlap=0.25)[0]
            except Exception:
                sources = apply_model(model, wav[None].to(device), shifts=shifts, split=True, overlap=0.25)[0]
        else:
            sources = apply_model(model, wav[None].to(device), shifts=shifts, split=True, overlap=0.25)[0]

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

    # Instantly unload AI model & purge all RAM / VRAM
    global LOADED_MODEL
    del model, wav, sources, drums, bass, other, vocals, instrumental
    LOADED_MODEL = None
    gc.collect()
    gc.collect()
    if torch.cuda.is_available():
        try:
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
        except Exception:
            pass

    print("[AI Engine] Separation finished. Model unloaded & RAM/VRAM freed cleanly.", flush=True)
    return vocal_path, no_vocal_path


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        in_wav = Path(sys.argv[1])
        out_d = Path(sys.argv[2])
        q = sys.argv[3] if len(sys.argv) > 3 else "fast"
        dev = sys.argv[4] if len(sys.argv) > 4 else "auto"
        separate_audio(in_wav, out_d, quality=q, device_setting=dev)
        sys.exit(0)
