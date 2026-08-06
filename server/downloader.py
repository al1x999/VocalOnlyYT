import os
import sys
import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TEMP_AUDIO_DIR = BASE_DIR / "temp" / "audio"
TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)


def get_executable(name: str) -> str:
    """Finds an executable in local server/bin, System PATH, or standard install paths."""
    exe_name = f"{name}.exe" if os.name == "nt" else name
    
    # 0. Local server/bin directory
    local_bin = BASE_DIR / "server" / "bin" / exe_name
    if local_bin.exists():
        return str(local_bin.resolve())

    # 1. System PATH
    found = shutil.which(exe_name) or shutil.which(name)
    if found:
        return str(Path(found).resolve())

    # 2. Known install locations on system
    if os.name == "nt":
        common_paths = [
            Path(r"D:\Software\Python\Python3.11.6\Scripts") / exe_name,
            Path(r"D:\Software\ffmpeg-8.1.1-full_build\bin") / exe_name,
            Path(sys.executable).parent / "Scripts" / exe_name,
            Path(sys.executable).parent / exe_name,
        ]
        for p in common_paths:
            if p.exists():
                return str(p.resolve())
                
    return exe_name


def clean_url(url: str, video_id: str = None) -> str:
    """Normalizes URL into clean YouTube link to prevent tracking param errors."""
    if video_id and len(video_id) == 11 and not video_id.startswith("vid_"):
        return f"https://www.youtube.com/watch?v={video_id}"
    return url


def download_audio_only(url: str, video_id: str, out_wav_path: Path) -> bool:
    """
    Downloads ONLY audio from YouTube using yt-dlp reference logic,
    outputting directly as a 44.1kHz stereo WAV file.
    """
    target_url = clean_url(url, video_id)
    ytdlp_bin = get_executable("yt-dlp")
    ffmpeg_bin = get_executable("ffmpeg")

    temp_raw = out_wav_path.parent / f"raw_{out_wav_path.stem}.%(ext)s"

    cmd = [
        ytdlp_bin,
        "-f", "bestaudio/best",
        "-x",
        "--audio-format", "wav",
        "--audio-quality", "0",
        "--no-playlist",
        "--no-check-certificates",
        "-o", str(temp_raw),
    ]

    if ffmpeg_bin and ffmpeg_bin != "ffmpeg":
        cmd.extend(["--ffmpeg-location", str(Path(ffmpeg_bin).parent)])

    cmd.extend(["--", target_url])

    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        raw_files = list(out_wav_path.parent.glob(f"raw_{out_wav_path.stem}.*"))

        # Fallback attempt with mweb/android player client if initial CLI attempt failed
        if not raw_files:
            fallback_cmd = [
                ytdlp_bin,
                "--extractor-args", "youtube:player_client=mweb,android,web",
                "-f", "bestaudio/best",
                "-x",
                "--audio-format", "wav",
                "--no-playlist",
                "--no-check-certificates",
                "-o", str(temp_raw),
            ]
            if ffmpeg_bin and ffmpeg_bin != "ffmpeg":
                fallback_cmd.extend(["--ffmpeg-location", str(Path(ffmpeg_bin).parent)])
            fallback_cmd.extend(["--", target_url])
            subprocess.run(fallback_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            raw_files = list(out_wav_path.parent.glob(f"raw_{out_wav_path.stem}.*"))

        # Fallback attempt via yt_dlp Python API
        if not raw_files:
            try:
                import yt_dlp
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': str(temp_raw),
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'wav',
                        'preferredquality': '0',
                    }],
                    'quiet': True,
                    'nocheckcertificate': True,
                }
                if ffmpeg_bin and ffmpeg_bin != "ffmpeg":
                    ydl_opts['ffmpeg_location'] = str(Path(ffmpeg_bin).parent)
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([target_url])
                raw_files = list(out_wav_path.parent.glob(f"raw_{out_wav_path.stem}.*"))
            except Exception as ydl_err:
                print(f"[yt_dlp API Error] {ydl_err}", flush=True)

        # Fallback attempt via pytubefix ANDROID_MUSIC engine
        if not raw_files:
            try:
                from pytubefix import YouTube
                yt = YouTube(target_url, client='ANDROID_MUSIC')
                stream = yt.streams.filter(only_audio=True).first()
                if stream:
                    down_name = f"pytube_{out_wav_path.stem}.m4a"
                    raw_dl = stream.download(output_path=str(out_wav_path.parent), filename=down_name)
                    cvt_cmd = [
                        ffmpeg_bin or "ffmpeg",
                        "-y",
                        "-i", str(raw_dl),
                        "-ar", "44100",
                        "-ac", "2",
                        str(out_wav_path)
                    ]
                    subprocess.run(cvt_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    try:
                        os.remove(raw_dl)
                    except Exception:
                        pass
                    if out_wav_path.exists():
                        return True
            except Exception as py_err:
                print(f"[pytubefix Error] {py_err}", flush=True)

        if raw_files:
            raw_file = raw_files[0]
            # Convert / normalize to 44.1kHz stereo WAV
            cvt_cmd = [
                ffmpeg_bin or "ffmpeg",
                "-y",
                "-i", str(raw_file),
                "-ar", "44100",
                "-ac", "2",
                str(out_wav_path)
            ]
            subprocess.run(cvt_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                os.remove(raw_file)
            except Exception:
                pass
            return out_wav_path.exists()

    except Exception as e:
        print(f"[Downloader Error] {e}", flush=True)

    return False
