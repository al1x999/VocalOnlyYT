# YouTube Instrument Remover - Chrome Extension & AI Backend

A Chrome Extension and FastAPI backend that isolates human vocals from YouTube videos on demand using PyTorch AI audio source separation (Demucs / MDX-Net).

## Features
- **Real-Time Synchronized Vocal Playback**: Replaces native YouTube audio with sample-accurate synchronized isolated vocals.
- **Low-End PC & GPU Optimization**: Uses PyTorch FP16 Mixed Precision Autocast, single-pass inference (`shifts=0`), and CPU thread capping to process audio quickly without eating 100% GPU/CPU.
- **Keyboard Shortcut**: Press `P` (customizable to any key or key combo) to toggle instrument removal.
- **Pre-Separated Audio Auto-Detect**: Page reloads won't trigger automatic processing, but if a video's vocal was previously separated, pressing `P` plays the cached vocal instantly.
- **Storage Cache Management**: Built-in 1-click **Clear Storage Cache** feature in the settings panel to free up disk space.
- **Hardware Acceleration**: Automatic GPU (CUDA) / MPS / CPU detection.
- **Minimalist UI Overlay**: Embedded YouTube widget with live processing badges and progress bar.

## Project Structure
```text
vocal-only-extension/
├── extension/
│   ├── manifest.json      # Chrome Extension Manifest V3
│   ├── content.js         # Content script for UI overlay & audio sync
│   └── content.css        # Modern glassmorphism UI styles
├── server/
│   ├── app.py             # FastAPI backend REST server
│   ├── separator.py       # Demucs/MDX-Net PyTorch audio separator
│   ├── downloader.py      # yt-dlp audio fetcher & converter
│   └── requirements.txt   # Python dependencies
├── install_autostart.bat  # 1-click background Windows Startup installer
└── start_server.bat       # One-click Windows startup script
```

## Quick Start

### 1. Start Backend Server
Run the background autostart installer once:
```cmd
install_autostart.bat
```
Or manually run:
```bash
python server/app.py
```
The server listens at `http://127.0.0.1:8000`.

### 2. Load Chrome Extension
1. Open Chrome and navigate to `chrome://extensions`.
2. Enable **Developer mode** in the top-right corner.
3. Click **Load unpacked** and select the `extension` folder.

### 3. Usage
1. Open any YouTube video.
2. Press `P` or click **Remove Instrumental**.
3. Enjoy vocal-only audio synchronized with the video!

## License
MIT
