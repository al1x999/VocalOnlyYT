import os
import sys
import subprocess
import time
import json
import shutil
import zipfile
import threading
import traceback
import datetime
import urllib.request
from pathlib import Path

# ==========================================
# BOOTSTRAP PYTHON DEPENDENCIES
# ==========================================
def install_and_import(package_name, import_name=None):
    if import_name is None:
        import_name = package_name
    try:
        __import__(import_name)
    except ImportError:
        print(f"\033[93m[*] Missing required Python package '{package_name}'. Installing via pip...\033[0m")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name, "--quiet"])
        try:
            __import__(import_name)
        except ImportError:
            print(f"\033[91m[!] Failed to install or import {package_name}. Please install manually.\033[0m")
            sys.exit(1)

install_and_import("requests")
install_and_import("mutagen")

import requests
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TPE2, TYER, APIC, TRCK, error

# Enable ANSI escape sequences on Windows
if os.name == 'nt':
    os.system('color')

# ==========================================
# CYBER-NOIR DESIGN SYSTEM
# ==========================================
class Colors:
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    WHITE = '\033[97m'
    GRAY = '\033[90m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_banner():
    banner = f"""{Colors.MAGENTA}
  _   _  ______  ____   _    _  _               
 | \ | ||  ____||  _ \ | |  | || |        /\    
 |  \| || |__   | |_) || |  | || |       /  \   
 | . ` ||  __|  |  _ < | |  | || |      / /\ \  
 | |\  || |____ | |_) || |__| || |____ / ____ \ 
 |_| \_||______||____/  \____/ |______/_/    \_{Colors.CYAN}

 All rights reserved © 2026 | Developed by AKASH | GitHub: https://github.com/DarkDreamWiz | Discord: dark_dreams_wiz{Colors.CYAN}
                                                
  ✦  M E D I A   D O W N L O A D E R  ·  v1.5  ✦{Colors.RESET}
    """
    print(banner)

def print_header(title):
    width = 70
    padding = (width - len(title) - 2) // 2
    left_pad = "═" * padding
    right_pad = "═" * (width - len(title) - 2 - padding)
    print(f"\n{Colors.CYAN}{left_pad} {Colors.WHITE}{Colors.BOLD}{title}{Colors.RESET}{Colors.CYAN} {right_pad}{Colors.RESET}\n")

def print_success(msg):
    print(f"{Colors.GREEN}✓ {msg}{Colors.RESET}")

def print_warning(msg):
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.RESET}")

def print_error(msg):
    print(f"{Colors.RED}✗ {msg}{Colors.RESET}")

def print_info(msg):
    print(f"{Colors.CYAN}ℹ {Colors.WHITE}{msg}{Colors.RESET}")

def print_bullet(msg):
    print(f"{Colors.MAGENTA}✦ {Colors.WHITE}{msg}{Colors.RESET}")


# ==========================================
# CONSTANTS & CONFIG
# ==========================================
APP_DIR = Path(os.path.abspath(os.path.dirname(__file__)))
TEMP_DIR = APP_DIR / ".temp"
CONFIG_FILE = APP_DIR / "nebula_config.json"
BIN_DIR = APP_DIR / "bin"

DEFAULT_CONFIG = {
    "download_dir": str(APP_DIR / "Downloads"),
    "default_resolution": "1080p",
    "theme": "Cyber-Noir"
}

config = DEFAULT_CONFIG.copy()

def load_config():
    global config
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                config.update(loaded)
        except Exception as e:
            print_error(f"Failed to load config: {e}")
    else:
        save_config()
    
    Path(config["download_dir"]).mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    BIN_DIR.mkdir(parents=True, exist_ok=True)

def save_config():
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print_error(f"Failed to save config: {e}")


# ==========================================
# SMART SYNC - DEPENDENCY ENGINE
# ==========================================
def get_executable_path(name):
    # Check local bin dir first
    local_exec = BIN_DIR / (name + (".exe" if os.name == 'nt' else ""))
    if local_exec.exists():
        return str(local_exec)
    
    # Check system PATH
    sys_exec = shutil.which(name)
    if sys_exec:
        return sys_exec
        
    return None

def download_file(url, dest_path, desc="Downloading"):
    try:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            downloaded = 0
            start_time = time.time()
            
            with open(dest_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Calculate speed and progress
                        elapsed = time.time() - start_time
                        speed = downloaded / elapsed if elapsed > 0 else 0
                        
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            # Simple progress bar
                            bar_len = 30
                            filled = int(bar_len * percent / 100)
                            bar = '█' * filled + '░' * (bar_len - filled)
                            
                            sys.stdout.write(f"\r{Colors.CYAN}ℹ {desc}:{Colors.RESET} [{Colors.MAGENTA}{bar}{Colors.RESET}] {percent:.1f}% ({downloaded/(1024*1024):.1f}MB / {total_size/(1024*1024):.1f}MB) | {speed/(1024*1024):.1f} MB/s")
                            sys.stdout.flush()
            print() # new line
        return True
    except Exception as e:
        print()
        print_error(f"Download failed: {e}")
        return False

def install_ytdlp():
    print_bullet("Fetching latest yt-dlp release...")
    try:
        # Get latest release from github API
        api_url = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
        response = requests.get(api_url).json()
        
        asset_name = "yt-dlp.exe" if os.name == 'nt' else "yt-dlp"
        download_url = next(asset["browser_download_url"] for asset in response["assets"] if asset["name"] == asset_name)
        
        dest_path = BIN_DIR / asset_name
        if download_file(download_url, dest_path, "yt-dlp"):
            if os.name != 'nt':
                os.chmod(dest_path, 0o755)
            print_success("yt-dlp installed successfully.")
            return True
        return False
    except Exception as e:
        print_error(f"Failed to install yt-dlp: {e}")
        return False

def install_ffmpeg():
    print_bullet("Fetching latest FFmpeg release...")
    if os.name == 'nt':
        # Download Windows build from gyan.dev
        url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        zip_path = TEMP_DIR / "ffmpeg.zip"
        
        if download_file(url, zip_path, "FFmpeg"):
            print_bullet("Extracting FFmpeg...")
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    # Find bin folder inside the zip
                    bin_files = [f for f in zip_ref.namelist() if f.endswith('.exe') and '/bin/' in f]
                    for file in bin_files:
                        filename = os.path.basename(file)
                        if filename in ["ffmpeg.exe", "ffprobe.exe"]:
                            source = zip_ref.open(file)
                            target = open(BIN_DIR / filename, "wb")
                            with source, target:
                                shutil.copyfileobj(source, target)
                
                os.remove(zip_path)
                print_success("FFmpeg installed successfully.")
                return True
            except Exception as e:
                print_error(f"Extraction failed: {e}")
                return False
    else:
        print_warning("Auto-install for FFmpeg on Linux/Mac is not supported.")
        print_info("Please install via package manager (e.g., 'sudo apt install ffmpeg' or 'brew install ffmpeg')")
        return False

def check_dependencies():
    print_header("DEPENDENCY STATUS")
    
    ytdlp_path = get_executable_path("yt-dlp")
    ffmpeg_path = get_executable_path("ffmpeg")
    ffprobe_path = get_executable_path("ffprobe")
    
    deps = [
        ("yt-dlp", ytdlp_path, "Core download engine for media extraction"),
        ("ffmpeg", ffmpeg_path, "Video/Audio merging and conversion"),
        ("ffprobe", ffprobe_path, "Media analysis and metadata extraction")
    ]
    
    all_found = True
    missing_deps = []
    
    for name, path, desc in deps:
        if path:
            print(f"{Colors.GREEN}✓ FOUND{Colors.RESET}      {Colors.WHITE}{name:<10}{Colors.RESET} {Colors.GRAY}{desc}{Colors.RESET}")
        else:
            print(f"{Colors.RED}✗ MISSING{Colors.RESET}    {Colors.WHITE}{name:<10}{Colors.RESET} {Colors.GRAY}{desc}{Colors.RESET}")
            all_found = False
            missing_deps.append(name)
            
    if not all_found:
        print()
        print_warning("Missing core dependencies. Smart Sync initializing...")
        
        if "yt-dlp" in missing_deps:
            install_ytdlp()
            
        if "ffmpeg" in missing_deps or "ffprobe" in missing_deps:
            install_ffmpeg()
            
        # Recheck
        ytdlp_path = get_executable_path("yt-dlp")
        ffmpeg_path = get_executable_path("ffmpeg")
        
        if not ytdlp_path or not ffmpeg_path:
            print_error("Critical dependencies missing. Features will be limited.")
            time.sleep(2)
        else:
            print_success("All dependencies resolved.")
            time.sleep(1)
            
    # Inject BIN_DIR to PATH for this session
    os.environ["PATH"] = str(BIN_DIR) + os.pathsep + os.environ.get("PATH", "")

def get_ytdlp_base_cmd():
    ytdlp = get_executable_path("yt-dlp")
    ffmpeg = get_executable_path("ffmpeg")
    
    if not ytdlp:
        raise Exception("yt-dlp not found")
        
    cmd = [ytdlp]
    if ffmpeg:
        ffmpeg_dir = os.path.dirname(ffmpeg)
        cmd.extend(["--ffmpeg-location", ffmpeg_dir])
        
    return cmd


# ==========================================
# MEDIA DOWNLOAD CORE
# ==========================================
def parse_resolution(res_str):
    mapping = {
        "4K (2160p)": "bestvideo[height<=2160]+bestaudio/best",
        "2K (1440p)": "bestvideo[height<=1440]+bestaudio/best",
        "1080p": "bestvideo[height<=1080]+bestaudio/best",
        "720p": "bestvideo[height<=720]+bestaudio/best",
        "Data-Saver (480p)": "bestvideo[height<=480]+bestaudio/best",
        "Best Available": "bestvideo+bestaudio/best"
    }
    return mapping.get(res_str, "bestvideo+bestaudio/best")

def run_download(cmd):
    try:
        # We use subprocess.Popen to show output in real-time
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            encoding='utf-8',
            errors='replace'
        )
        
        for line in process.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            
        process.wait()
        
        if process.returncode == 0:
            print_success("Download Routine Completed.")
            return True
        else:
            print_error(f"Process exited with code {process.returncode}")
            return False
            
    except Exception as e:
        print_error(f"Execution Error: {e}")
        return False

def download_video():
    print_header("VIDEO DOWNLOADER")
    url = input(f"{Colors.MAGENTA}✦ {Colors.WHITE}Enter Media URL: {Colors.RESET}").strip()
    if not url: return

    resolutions = [
        "4K (2160p)", "2K (1440p)", "1080p", "720p", "Data-Saver (480p)", "Best Available"
    ]
    
    print("\nSelect Resolution:")
    for i, res in enumerate(resolutions, 1):
        print(f"  {Colors.CYAN}{i}.{Colors.RESET} {res}")
        
    try:
        choice = int(input(f"\n{Colors.MAGENTA}✦ {Colors.WHITE}Choice [Default: 3 for 1080p]: {Colors.RESET}") or "3")
        if not (1 <= choice <= len(resolutions)): choice = 3
    except ValueError:
        choice = 3
        
    selected_res = resolutions[choice - 1]
    format_str = parse_resolution(selected_res)
    
    output_template = str(Path(config["download_dir"]) / "%(title)s.%(ext)s")
    
    cmd = get_ytdlp_base_cmd() + [
        "-f", format_str,
        "-o", output_template,
        "--merge-output-format", "mkv",
        "--embed-metadata",
        "--embed-thumbnail",
        url
    ]
    
    print(f"\n{Colors.CYAN}Initializing Protocol: {Colors.WHITE}Video Extraction ({selected_res}){Colors.RESET}\n")
    run_download(cmd)
    input(f"\n{Colors.GRAY}Press Enter to return to main menu...{Colors.RESET}")

def download_audio():
    print_header("AUDIO DOWNLOADER")
    url = input(f"{Colors.MAGENTA}✦ {Colors.WHITE}Enter Media URL: {Colors.RESET}").strip()
    if not url: return

    output_template = str(Path(config["download_dir"]) / "%(title)s.%(ext)s")
    
    cmd = get_ytdlp_base_cmd() + [
        "-f", "bestaudio/best",
        "-x", "--audio-format", "mp3",
        "--audio-quality", "320K",
        "-o", output_template,
        "--embed-metadata",
        "--embed-thumbnail",
        url
    ]
    
    print(f"\n{Colors.CYAN}Initializing Protocol: {Colors.WHITE}Highest Quality Audio Extraction (320kbps MP3){Colors.RESET}\n")
    run_download(cmd)
    input(f"\n{Colors.GRAY}Press Enter to return to main menu...{Colors.RESET}")

def extract_thumbnail():
    print_header("THUMBNAIL EXTRACTION")
    url = input(f"{Colors.MAGENTA}✦ {Colors.WHITE}Enter Media URL: {Colors.RESET}").strip()
    if not url: return
    
    output_template = str(Path(config["download_dir"]) / "%(title)s.%(ext)s")
    
    cmd = get_ytdlp_base_cmd() + [
        "--skip-download",
        "--write-thumbnail",
        "-o", output_template,
        url
    ]
    
    print(f"\n{Colors.CYAN}Initializing Protocol: {Colors.WHITE}High-Res Image Extraction{Colors.RESET}\n")
    run_download(cmd)
    input(f"\n{Colors.GRAY}Press Enter to return to main menu...{Colors.RESET}")

def batch_download():
    print_header("BATCH OPERATIONS")
    print_info("Batch mode reads multiple URLs from a text file.")
    
    file_path = input(f"{Colors.MAGENTA}✦ {Colors.WHITE}Enter path to .txt file: {Colors.RESET}").strip()
    # Handle quotes and backslashes
    file_path = file_path.strip('"').strip("'")
    
    if not os.path.exists(file_path):
        print_error("File not found.")
        time.sleep(2)
        return
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except Exception as e:
        print_error(f"Could not read file: {e}")
        time.sleep(2)
        return
        
    if not urls:
        print_warning("No valid URLs found in file.")
        time.sleep(2)
        return
        
    print(f"Found {len(urls)} target(s).")
    modetype = input(f"{Colors.MAGENTA}✦ {Colors.WHITE}Select Mode (1: Video, 2: Audio) [1]: {Colors.RESET}").strip() or "1"
    
    output_template = str(Path(config["download_dir"]) / "%(title)s.%(ext)s")
    cmd = get_ytdlp_base_cmd() + ["-o", output_template, "-a", file_path]
    
    if modetype == "2":
        cmd.extend([
            "-f", "bestaudio/best",
            "-x", "--audio-format", "mp3", 
            "--audio-quality", "320K",
            "--embed-metadata",
            "--embed-thumbnail"
        ])
    else:
        cmd.extend([
            "-f", parse_resolution("1080p"),
            "--merge-output-format", "mkv",
            "--embed-metadata",
            "--embed-thumbnail"
        ])
        
    print(f"\n{Colors.CYAN}Initializing Protocol: {Colors.WHITE}Batch Extraction{Colors.RESET}\n")
    run_download(cmd)
    input(f"\n{Colors.GRAY}Press Enter to return to main menu...{Colors.RESET}")

def playlist_download():
    print_header("PLAYLIST EXTRACTION")
    url = input(f"{Colors.MAGENTA}✦ {Colors.WHITE}Enter Playlist/Channel URL: {Colors.RESET}").strip()
    if not url: return
    
    print_info("Fetching playlist info (this might take a moment)...")
    
    modetype = input(f"{Colors.MAGENTA}✦ {Colors.WHITE}Select Mode (1: Video, 2: Audio) [1]: {Colors.RESET}").strip() or "1"
    
    # Use %(playlist_index)s prefix for ordered files
    output_template = str(Path(config["download_dir"]) / "%(playlist_title)s" / "%(playlist_index)s - %(title)s.%(ext)s")
    
    cmd = get_ytdlp_base_cmd() + ["-o", output_template, "--yes-playlist", url]
    
    if modetype == "2":
        cmd.extend([
            "-f", "bestaudio/best",
            "-x", "--audio-format", "mp3", 
            "--audio-quality", "320K",
            "--embed-metadata",
            "--embed-thumbnail"
        ])
    else:
        cmd.extend([
            "-f", parse_resolution("1080p"),
            "--merge-output-format", "mkv",
            "--embed-metadata",
            "--embed-thumbnail"
        ])
        
    print(f"\n{Colors.CYAN}Initializing Protocol: {Colors.WHITE}Playlist Extraction{Colors.RESET}\n")
    run_download(cmd)
    input(f"\n{Colors.GRAY}Press Enter to return to main menu...{Colors.RESET}")

def subtitle_download():
    print_header("SUBTITLE EXTRACTION")
    url = input(f"{Colors.MAGENTA}✦ {Colors.WHITE}Enter Media URL: {Colors.RESET}").strip()
    if not url: return

    output_template = str(Path(config["download_dir"]) / "%(title)s.%(ext)s")
    
    print("\nOptions:")
    print(f"  {Colors.CYAN}1.{Colors.RESET} Download subtitles only (VTT/SRT)")
    print(f"  {Colors.CYAN}2.{Colors.RESET} Download video AND embed subtitles")
    
    try:
        choice = int(input(f"\n{Colors.MAGENTA}✦ {Colors.WHITE}Choice [1]: {Colors.RESET}") or "1")
    except ValueError:
        choice = 1
        
    cmd = get_ytdlp_base_cmd() + ["-o", output_template, url]
    
    if choice == 1:
        cmd.extend(["--skip-download", "--write-subs", "--write-auto-subs", "--sub-langs", "en,all"])
        print(f"\n{Colors.CYAN}Initializing Protocol: {Colors.WHITE}Subtitle Download{Colors.RESET}\n")
    else:
        cmd.extend([
            "-f", parse_resolution("1080p"),
            "--merge-output-format", "mkv",
            "--write-subs", "--sub-langs", "en,all",
            "--embed-subs"
        ])
        print(f"\n{Colors.CYAN}Initializing Protocol: {Colors.WHITE}Video + Subtitle Extraction{Colors.RESET}\n")
        
    run_download(cmd)
    input(f"\n{Colors.GRAY}Press Enter to return to main menu...{Colors.RESET}")

# ==========================================
# METADATA TAGGER
# ==========================================
def metadata_tagger():
    print_header("Smart Metadata / ID3 Tagger")
    file_path = input(f"{Colors.MAGENTA}✦ {Colors.WHITE}Enter path to audio file (MP3): {Colors.RESET}").strip()
    file_path = file_path.strip('"').strip("'")
    
    if not os.path.exists(file_path):
        print_error("File not found.")
        time.sleep(2)
        return
        
    if not file_path.lower().endswith('.mp3'):
        print_error("Currently only MP3 files are supported for advanced tagging.")
        time.sleep(2)
        return
        
    try:
        audio = MP3(file_path, ID3=ID3)
        if audio.tags is None:
            audio.add_tags()
            
        print_info(f"Loaded: {os.path.basename(file_path)}")
        
        # Display current tags
        title = audio.tags.getall("TIT2")[0].text[0] if audio.tags.getall("TIT2") else ""
        artist = audio.tags.getall("TPE1")[0].text[0] if audio.tags.getall("TPE1") else ""
        album = audio.tags.getall("TALB")[0].text[0] if audio.tags.getall("TALB") else ""
        year = audio.tags.getall("TYER")[0].text[0] if audio.tags.getall("TYER") else ""
        
        print("\nCurrent Metadata:")
        print(f"  Title:  {Colors.CYAN}{title}{Colors.RESET}")
        print(f"  Artist: {Colors.CYAN}{artist}{Colors.RESET}")
        print(f"  Album:  {Colors.CYAN}{album}{Colors.RESET}")
        print(f"  Year:   {Colors.CYAN}{year}{Colors.RESET}")
        print("-" * 40)
        print("Enter new values (leave blank to keep current):")
        
        new_title = input(f"  Title [{title}]: ").strip()
        new_artist = input(f"  Artist [{artist}]: ").strip()
        new_album = input(f"  Album [{album}]: ").strip()
        new_year = input(f"  Year [{year}]: ").strip()
        
        # Cover Art
        new_cover = input("  Cover Art Path (JPG/PNG) [leave blank to skip]: ").strip()
        new_cover = new_cover.strip('"').strip("'")
        
        # Update
        updated = False
        if new_title:
            audio.tags.add(TIT2(encoding=3, text=new_title))
            updated = True
        if new_artist:
            audio.tags.add(TPE1(encoding=3, text=new_artist))
            updated = True
        if new_album:
            audio.tags.add(TALB(encoding=3, text=new_album))
            updated = True
        if new_year:
            audio.tags.add(TYER(encoding=3, text=new_year))
            updated = True
            
        if new_cover and os.path.exists(new_cover):
            with open(new_cover, 'rb') as img_f:
                img_data = img_f.read()
            mime = "image/png" if new_cover.lower().endswith(".png") else "image/jpeg"
            audio.tags.add(APIC(
                encoding=3,
                mime=mime,
                type=3, # 3 is for the cover(front) image
                desc=u'Cover',
                data=img_data
            ))
            updated = True
            
        if updated:
            audio.save()
            print_success("Metadata saved successfully.")
        else:
            print_info("No changes made.")
            
    except Exception as e:
        print_error(f"Failed to read/write tags: {e}")
        
    input(f"\n{Colors.GRAY}Press Enter to return to main menu...{Colors.RESET}")

# ==========================================
# SETTINGS MENU
# ==========================================
def settings_menu():
    global config
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print_banner()
        print_header("SETTINGS")
        
        print(f"  {Colors.CYAN}1.{Colors.RESET} Default Download Directory {Colors.GRAY}[{config['download_dir']}]{Colors.RESET}")
        print(f"  {Colors.CYAN}2.{Colors.RESET} Default Resolution {Colors.GRAY}[{config['default_resolution']}]{Colors.RESET}")
        print(f"  {Colors.CYAN}3.{Colors.RESET} Open Download Directory")
        print(f"  {Colors.CYAN}0.{Colors.RESET} Back to Main Menu")
        
        choice = input(f"\n{Colors.MAGENTA}✦ {Colors.WHITE}Choice: {Colors.RESET}").strip()
        
        if choice == '1':
            new_dir = input(f"Enter new path (current: {config['download_dir']}): ").strip()
            if new_dir:
                config['download_dir'] = new_dir
                save_config()
                Path(config["download_dir"]).mkdir(parents=True, exist_ok=True)
                print_success("Directory updated.")
                time.sleep(1)
        elif choice == '2':
            print("Resolutions: 4K (2160p), 2K (1440p), 1080p, 720p, Data-Saver (480p), Best Available")
            new_res = input(f"Enter exact resolution name (current: {config['default_resolution']}): ").strip()
            if new_res:
                config['default_resolution'] = new_res
                save_config()
                print_success("Resolution updated.")
                time.sleep(1)
        elif choice == '3':
            dl_dir = config['download_dir']
            if os.name == 'nt':
                os.startfile(dl_dir)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', dl_dir])
            else:
                subprocess.Popen(['xdg-open', dl_dir])
        elif choice == '0':
            break

# ==========================================
# MAIN MENU & LOOP
# ==========================================
def show_main_menu():
    print(f"  {Colors.CYAN}1.{Colors.RESET} 📥 Download Video")
    print(f"  {Colors.CYAN}2.{Colors.RESET} 🎵 Download Audio")
    print(f"  {Colors.CYAN}3.{Colors.RESET} 🖼️  Extract Thumbnail")
    print(f"  {Colors.CYAN}4.{Colors.RESET} 📋 Batch Download (from .txt)")
    print(f"  {Colors.CYAN}5.{Colors.RESET} 📺 Playlist/Channel Download")
    print(f"  {Colors.CYAN}6.{Colors.RESET} 💬 Subtitle Download")
    print(f"  {Colors.CYAN}7.{Colors.RESET} 🏷️  Metadata Tagger")
    print()
    print(f"  {Colors.CYAN}8.{Colors.RESET} 🔄 Force Update Dependencies")
    print(f"  {Colors.CYAN}9.{Colors.RESET} ⚙️  Settings")
    print(f"  {Colors.CYAN}0.{Colors.RESET} 🚪 Exit")
    print()

def main():
    load_config()
    
    os.system('cls' if os.name == 'nt' else 'clear')
    print_banner()
    check_dependencies()
    time.sleep(1.5)
    
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print_banner()
        print_info(f"Working Directory: {Colors.WHITE}{APP_DIR}{Colors.RESET}")
        print_info(f"Downloads Route:   {Colors.WHITE}{config['download_dir']}{Colors.RESET}")
        print()
        
        show_main_menu()
        
        choice = input(f"{Colors.MAGENTA}✦ {Colors.WHITE}Awaiting Command: {Colors.RESET}").strip()
        
        if choice == '1':
            download_video()
        elif choice == '2':
            download_audio()
        elif choice == '3':
            extract_thumbnail()
        elif choice == '4':
            batch_download()
        elif choice == '5':
            playlist_download()
        elif choice == '6':
            subtitle_download()
        elif choice == '7':
            metadata_tagger()
        elif choice == '8':
            print_header("DEPENDENCY UPDATE")
            install_ytdlp()
            install_ffmpeg()
            input(f"\n{Colors.GRAY}Press Enter to return to main menu...{Colors.RESET}")
        elif choice == '9':
            settings_menu()
        elif choice == '0':
            print(f"\n{Colors.MAGENTA}Shutting down protocols. Goodbye.{Colors.RESET}")
            sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Operation cancelled by user.{Colors.RESET}")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n{Colors.RED}FATAL ERROR: {traceback.format_exc()}{Colors.RESET}")
        input("Press Enter to exit...")
