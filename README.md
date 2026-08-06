# VocalOnlyYT - YouTube Vocal Remover Chrome Extension

A Chrome Extension and FastAPI backend that isolates human vocals from YouTube videos in real-time using AI audio source separation (Demucs / MDX-Net).

## Features
- **Real-Time Synchronized Vocal Playback**: Replaces native YouTube audio with sample-accurate synchronized isolated vocals.
- **AI Audio Separation**: Uses Demucs / MDX-Net models for state-of-the-art vocal extraction while preserving vocal clarity and reverb.
- **Keyboard Shortcut**: Press `Ctrl + Shift + R` (customizable) to instantly toggle vocal removal on any YouTube video.
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
└── start_server.bat       # One-click Windows startup script
```

## Quick Start

### 1. Start Backend Server
Run the startup script:
```cmd
start_server.bat
```
Or manually install dependencies and run:
```bash
pip install -r server/requirements.txt
python server/app.py
```
The server will start listening at `http://127.0.0.1:8000`.

### 2. Load Chrome Extension
1. Open Chrome and navigate to `chrome://extensions`.
2. Enable **Developer mode** in the top-right corner.
3. Click **Load unpacked** and select the `extension` folder.

### 3. Usage
1. Open any YouTube video.
2. Click the **Remove Instrumental** button on the bottom overlay widget or press `Ctrl + Shift + R`.
3. Wait for AI separation to complete.
4. Enjoy vocal-only audio synchronized with the video!

## License
MIT
