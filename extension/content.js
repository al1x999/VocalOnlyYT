/**
 * YouTube Vocal Remover - Content Script
 * Auto-detects current YouTube video, processes vocals on demand via Ctrl+Shift+R or button click,
 * and plays sample-accurate synchronized vocal audio replacing original YouTube audio.
 */

(function () {
  'use strict';

  const SERVER_URL = 'http://127.0.0.1:8000';

  let isEnabled = false;
  let isSettingsOpen = false;
  let currentVideoId = null;
  let activeVideoElement = null;
  let pollInterval = null;
  let syncAnimationId = null;

  // Settings
  let qualitySetting = 'fast'; // fast (mdx_extra), balanced (htdemucs), high (htdemucs_ft)
  let deviceSetting = 'auto'; // auto, cuda, cpu
  let shortcutSetting = 'Ctrl+Shift+R'; // Default shortcut

  let vocalsAudio = null;

  let backendStatus = {
    status: 'idle',
    progress: 0,
    error: null,
  };

  // Helper: Check extension context validity
  function isExtensionValid() {
    try {
      return typeof chrome !== 'undefined' && chrome.runtime && !!chrome.runtime.id;
    } catch (e) {
      return false;
    }
  }

  // Load persistent settings from Chrome storage
  function loadSettings() {
    if (isExtensionValid() && chrome.storage && chrome.storage.local) {
      try {
        chrome.storage.local.get(['qualitySetting', 'deviceSetting', 'shortcutSetting'], (res) => {
          if (res) {
            if (res.qualitySetting) qualitySetting = res.qualitySetting;
            if (res.deviceSetting) deviceSetting = res.deviceSetting;
            if (res.shortcutSetting) shortcutSetting = res.shortcutSetting;
            updateUI();
          }
        });
      } catch (e) {}
    }
  }

  // Save settings helper
  function saveSettings() {
    if (isExtensionValid() && chrome.storage && chrome.storage.local) {
      try {
        chrome.storage.local.set({ qualitySetting, deviceSetting, shortcutSetting });
      } catch (e) {}
    }
  }

  // Helper: Extract 11-char YouTube Video ID
  function extractVideoId() {
    const href = window.location.href;
    const match = href.match(/(?:v=|\/shorts\/|\/embed\/|\/v\/|^https:\/\/youtu\.be\/)([a-zA-Z0-9_-]{11})/);
    if (match) return match[1];
    try {
      const url = new URL(href);
      if (url.searchParams.has('v')) return url.searchParams.get('v');
    } catch (e) {}
    return null;
  }

  // Inject Minimal UI Widget
  function injectWidget() {
    if (document.getElementById('yt-vocal-remover-widget')) return;

    const widget = document.createElement('div');
    widget.id = 'yt-vocal-remover-widget';
    widget.innerHTML = `
      <div class="yt-vocal-header">
        <div class="yt-vocal-title-group">
          <svg class="yt-vocal-icon" viewBox="0 0 24 24">
            <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/>
            <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
            <line x1="12" y1="19" x2="12" y2="22"/>
          </svg>
          <h4 class="yt-vocal-title">Vocal Remover</h4>
        </div>
        <div class="yt-vocal-header-actions">
          <span class="yt-vocal-status-badge" id="yt-vocal-badge">Ready</span>
          <button class="yt-vocal-gear-btn" id="yt-vocal-gear" title="Settings">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="3"/>
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
            </svg>
          </button>
        </div>
      </div>

      <button class="yt-vocal-btn" id="yt-vocal-btn">
        <span>🎵 Remove Instrumental (${shortcutSetting})</span>
      </button>

      <div class="yt-vocal-progress-bar" id="yt-vocal-progress-bar">
        <div class="yt-vocal-progress-fill" id="yt-vocal-progress-fill"></div>
      </div>
      <div class="yt-vocal-status-text" id="yt-vocal-status-text">Press ${shortcutSetting} to isolate vocals</div>

      <div class="yt-vocal-settings-panel" id="yt-vocal-settings">
        <div class="yt-vocal-setting-row">
          <div class="yt-vocal-setting-label">AI Model Engine</div>
          <select class="yt-vocal-select" id="yt-vocal-quality-select">
            <option value="fast" ${qualitySetting === 'fast' ? 'selected' : ''}>Fast (MDX-Net / mdx_extra)</option>
            <option value="balanced" ${qualitySetting === 'balanced' ? 'selected' : ''}>Balanced (htdemucs)</option>
            <option value="high" ${qualitySetting === 'high' ? 'selected' : ''}>High Quality (htdemucs_ft)</option>
          </select>
        </div>

        <div class="yt-vocal-setting-row">
          <div class="yt-vocal-setting-label">
            <span>Process Shortcut</span>
            <span class="yt-vocal-shortcut-badge" id="yt-vocal-shortcut-badge">${shortcutSetting}</span>
          </div>
          <input type="text" class="yt-vocal-input" id="yt-vocal-shortcut-input" value="${shortcutSetting}" placeholder="Click & press shortcut (e.g. P or Alt+V)">
        </div>

        <div class="yt-vocal-setting-row">
          <div class="yt-vocal-setting-label">Hardware Acceleration</div>
          <select class="yt-vocal-select" id="yt-vocal-device-select">
            <option value="auto" ${deviceSetting === 'auto' ? 'selected' : ''}>Auto (GPU Preferred)</option>
            <option value="cuda" ${deviceSetting === 'cuda' ? 'selected' : ''}>Force GPU (CUDA)</option>
            <option value="cpu" ${deviceSetting === 'cpu' ? 'selected' : ''}>Force CPU Mode</option>
          </select>
        </div>
      </div>
    `;

    document.body.appendChild(widget);
    attachUIEventListeners();
  }

  // Attach Event Listeners
  function attachUIEventListeners() {
    const btn = document.getElementById('yt-vocal-btn');
    const gearBtn = document.getElementById('yt-vocal-gear');
    const settingsPanel = document.getElementById('yt-vocal-settings');
    const qualitySelect = document.getElementById('yt-vocal-quality-select');
    const deviceSelect = document.getElementById('yt-vocal-device-select');
    const shortcutInput = document.getElementById('yt-vocal-shortcut-input');

    btn?.addEventListener('click', toggleProcessing);

    gearBtn?.addEventListener('click', () => {
      isSettingsOpen = !isSettingsOpen;
      settingsPanel?.classList.toggle('open', isSettingsOpen);
    });

    qualitySelect?.addEventListener('change', (e) => {
      qualitySetting = e.target.value;
      saveSettings();
    });

    deviceSelect?.addEventListener('change', (e) => {
      deviceSetting = e.target.value;
      saveSettings();
    });

    shortcutInput?.addEventListener('keydown', (e) => {
      e.preventDefault();
      e.stopPropagation();

      const keys = [];
      if (e.ctrlKey) keys.push('Ctrl');
      if (e.altKey) keys.push('Alt');
      if (e.shiftKey) keys.push('Shift');

      const keyName = e.key.toUpperCase();
      if (!['CONTROL', 'ALT', 'SHIFT', 'META'].includes(keyName)) {
        keys.push(keyName);
        const newShortcut = keys.join('+');
        shortcutSetting = newShortcut;
        shortcutInput.value = newShortcut;
        const badge = document.getElementById('yt-vocal-shortcut-badge');
        if (badge) badge.textContent = newShortcut;
        saveSettings();
        updateUI();
      }
    });
  }

  // Keyboard Shortcut Listener
  function attachKeyboardShortcut() {
    window.addEventListener('keydown', (e) => {
      const tag = document.activeElement ? document.activeElement.tagName.toLowerCase() : '';
      if (tag === 'input' || tag === 'textarea' || document.activeElement.isContentEditable) return;

      const keys = [];
      if (e.ctrlKey) keys.push('Ctrl');
      if (e.altKey) keys.push('Alt');
      if (e.shiftKey) keys.push('Shift');

      const keyName = e.key.toUpperCase();
      if (!['CONTROL', 'ALT', 'SHIFT', 'META'].includes(keyName)) {
        keys.push(keyName);
      }

      const pressedShortcut = keys.join('+');

      if (pressedShortcut.toLowerCase() === shortcutSetting.toLowerCase() || (shortcutSetting === 'Ctrl+Shift+R' && e.ctrlKey && e.shiftKey && keyName === 'R')) {
        e.preventDefault();
        toggleProcessing();
      }
    });
  }

  // Toggle Vocal Removal Processing
  function toggleProcessing() {
    const newVid = extractVideoId();
    if (!newVid) return;

    if (!isEnabled || newVid !== currentVideoId || backendStatus.status === 'idle' || backendStatus.status === 'error') {
      isEnabled = true;
      currentVideoId = newVid;
      startProcessing();
    } else {
      isEnabled = false;
      stopProcessing();
    }
  }

  // Start Vocal Processing Pipeline
  function startProcessing() {
    findVideoElement();
    if (!activeVideoElement) {
      isEnabled = false;
      updateUI();
      return;
    }

    initAudioEngine();
    updateUI();

    backendStatus = { status: 'downloading', progress: 10, error: null };
    updateUI();

    fetch(`${SERVER_URL}/process`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: window.location.href,
        video_id: currentVideoId,
        quality: qualitySetting,
        device: deviceSetting,
      }),
    })
      .then((res) => res.json())
      .then((data) => {
        startPolling();
        startSyncLoop();
      })
      .catch((err) => {
        backendStatus = { status: 'error', progress: 0, error: 'Server offline (Run start_server.bat)' };
        updateUI();
      });
  }

  // Stop Vocal Processing
  function stopProcessing() {
    stopPolling();
    stopSyncLoop();

    if (vocalsAudio) {
      try {
        vocalsAudio.pause();
        vocalsAudio.currentTime = 0;
        vocalsAudio.removeAttribute('src');
        vocalsAudio.load();
      } catch (e) {}
    }

    if (activeVideoElement) {
      activeVideoElement.muted = false;
    }

    backendStatus = { status: 'idle', progress: 0, error: null };
    updateUI();
  }

  // Poll GET /status/{video_id}
  function startPolling() {
    stopPolling();
    pollInterval = setInterval(() => {
      if (!currentVideoId || !isEnabled) return;

      fetch(`${SERVER_URL}/status/${currentVideoId}`)
        .then((res) => res.json())
        .then((data) => {
          if (data) {
            backendStatus = data;
            updateUI();
          }
        })
        .catch(() => {});
    }, 1200);
  }

  function stopPolling() {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  }

  // HTML5 Audio Engine Setup
  function initAudioEngine() {
    if (!vocalsAudio) {
      vocalsAudio = new Audio();
      vocalsAudio.preload = 'auto';
    }
  }

  // Fallback interaction listener for browser autoplay restrictions
  function unlockAutoplayOnUserGesture() {
    if (vocalsAudio && vocalsAudio.paused && backendStatus.status === 'ready' && activeVideoElement && !activeVideoElement.paused) {
      vocalsAudio.play().then(() => {
        if (activeVideoElement) activeVideoElement.muted = true;
      }).catch(() => {});
    }
  }
  window.addEventListener('click', unlockAutoplayOnUserGesture, { capture: true });
  window.addEventListener('keydown', unlockAutoplayOnUserGesture, { capture: true });

  // Sample-Accurate Audio Sync Loop
  function startSyncLoop() {
    stopSyncLoop();

    function syncStep() {
      if (!isEnabled || !activeVideoElement) return;

      const video = activeVideoElement;

      if (backendStatus.status === 'ready') {
        if (!vocalsAudio) initAudioEngine();

        // Set Audio Source
        const targetSrc = `${SERVER_URL}/audio/${currentVideoId}/vocals`;
        if (vocalsAudio.src !== targetSrc) {
          vocalsAudio.src = targetSrc;
          vocalsAudio.load();
          if (video.currentTime) {
            try {
              vocalsAudio.currentTime = video.currentTime;
            } catch (e) {}
          }
        }

        // Sync Playback Speed
        if (vocalsAudio.playbackRate !== video.playbackRate) {
          vocalsAudio.playbackRate = video.playbackRate;
        }

        const isVideoPlaying = !video.paused && !video.ended && !video.seeking;

        if (isVideoPlaying) {
          // Pause/Play Sync
          if (vocalsAudio.paused) {
            if (vocalsAudio.readyState >= 2) {
              const playPromise = vocalsAudio.play();
              if (playPromise !== undefined) {
                playPromise
                  .then(() => {
                    // Mute YouTube native video only after vocal audio successfully plays
                    if (!video.muted) {
                      video.muted = true;
                    }
                  })
                  .catch((err) => {
                    console.warn('[Vocal Remover] Autoplay prevented vocal playback:', err);
                    // Keep native video unmuted so user hears sound until interaction
                    if (video.muted) {
                      video.muted = false;
                    }
                  });
              }
            }
          } else {
            // Vocals are actively playing
            if (!video.muted) {
              video.muted = true;
            }
          }

          // Sample-Accurate Time Sync Check (resync if drift > 0.15s and not seeking)
          if (!vocalsAudio.seeking && vocalsAudio.readyState >= 2) {
            const drift = Math.abs(vocalsAudio.currentTime - video.currentTime);
            if (drift > 0.15) {
              vocalsAudio.currentTime = video.currentTime;
            }
          }
        } else {
          // Video is paused, ended, or seeking
          if (!vocalsAudio.paused) {
            vocalsAudio.pause();
          }
          if (video.seeking && vocalsAudio.readyState >= 1 && !vocalsAudio.seeking) {
            vocalsAudio.currentTime = video.currentTime;
          }
        }
      } else {
        // While processing, keep original video unmuted so sound isn't lost
        if (video.muted && isEnabled) {
          video.muted = false;
        }
        if (vocalsAudio && !vocalsAudio.paused) {
          vocalsAudio.pause();
        }
      }

      syncAnimationId = requestAnimationFrame(syncStep);
    }

    syncAnimationId = requestAnimationFrame(syncStep);
  }

  function stopSyncLoop() {
    if (syncAnimationId) {
      cancelAnimationFrame(syncAnimationId);
      syncAnimationId = null;
    }
  }

  // Update UI State
  function updateUI() {
    const badge = document.getElementById('yt-vocal-badge');
    const btn = document.getElementById('yt-vocal-btn');
    const progressBar = document.getElementById('yt-vocal-progress-bar');
    const progressFill = document.getElementById('yt-vocal-progress-fill');
    const statusText = document.getElementById('yt-vocal-status-text');

    if (!badge || !btn || !statusText) return;

    if (!isEnabled) {
      badge.textContent = 'Ready';
      badge.style.color = '#94a3b8';
      badge.style.background = 'rgba(148, 163, 184, 0.15)';
      btn.innerHTML = `<span>🎵 Remove Instrumental (${shortcutSetting})</span>`;
      if (progressBar) progressBar.style.display = 'none';
      statusText.textContent = `Press ${shortcutSetting} to isolate vocals`;
      return;
    }

    if (backendStatus.status === 'downloading') {
      badge.textContent = 'Downloading';
      badge.style.color = '#eab308';
      badge.style.background = 'rgba(234, 179, 8, 0.15)';
      btn.innerHTML = '<span>⏳ Downloading Audio...</span>';
      if (progressBar) progressBar.style.display = 'block';
      if (progressFill) progressFill.style.width = '25%';
      statusText.textContent = 'Extracting audio from YouTube...';
    } else if (backendStatus.status === 'separating') {
      badge.textContent = 'AI Separating';
      badge.style.color = '#a855f7';
      badge.style.background = 'rgba(168, 85, 247, 0.15)';
      btn.innerHTML = '<span>⚡ Isolating Vocals...</span>';
      if (progressBar) progressBar.style.display = 'block';
      if (progressFill) progressFill.style.width = '65%';
      statusText.textContent = 'Removing instrumental with AI...';
    } else if (backendStatus.status === 'ready') {
      badge.textContent = 'Vocal Only';
      badge.style.color = '#22c55e';
      badge.style.background = 'rgba(34, 197, 94, 0.15)';
      btn.innerHTML = '<span>✅ Vocals Active (Click to Stop)</span>';
      if (progressBar) progressBar.style.display = 'block';
      if (progressFill) progressFill.style.width = '100%';
      statusText.textContent = 'Instrumental removed! Playing vocals in sync';
    } else if (backendStatus.status === 'error') {
      badge.textContent = 'Error';
      badge.style.color = '#ef4444';
      badge.style.background = 'rgba(239, 68, 68, 0.15)';
      btn.innerHTML = '<span>🔄 Retry Removal</span>';
      if (progressBar) progressBar.style.display = 'none';
      statusText.textContent = backendStatus.error || 'Server connection error';
    }
  }

  // Find native HTML5 <video> element
  function findVideoElement() {
    const video = document.querySelector('video.html5-main-video') || document.querySelector('video');
    if (video) {
      activeVideoElement = video;
    }
  }

  // Handle Page Change (YouTube SPA Navigation)
  function handlePageChange() {
    const newVid = extractVideoId();
    if (newVid && newVid !== currentVideoId) {
      currentVideoId = newVid;
      stopProcessing();
      findVideoElement();
      injectWidget();
    }
  }

  // Initialize
  function init() {
    loadSettings();
    injectWidget();
    attachKeyboardShortcut();
    findVideoElement();

    const observer = new MutationObserver(() => {
      if (location.href !== lastUrl) {
        lastUrl = location.href;
        handlePageChange();
      } else {
        if (!activeVideoElement) findVideoElement();
      }
    });

    let lastUrl = location.href;
    observer.observe(document.body, { childList: true, subtree: true });

    window.addEventListener('yt-navigate-finish', handlePageChange);
    window.addEventListener('yt-page-data-updated', handlePageChange);
    window.addEventListener('popstate', handlePageChange);
  }

  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    init();
  } else {
    document.addEventListener('DOMContentLoaded', init);
  }
})();
