/**
 * AANYA — Next-Gen AI Voice Assistant Controller
 * Integrates Web Speech Recognition, Web Audio Synthesizer, SpeechSynthesis TTS,
 * Canvas Fluid Orb, and FastAPI backend endpoints.
 */

(() => {
  'use strict';

  // ── State & Config ──────────────────────────────────────────────────────────
  const state = {
    sessionId: localStorage.getItem('aanya_session_id') || 'default',
    theme: localStorage.getItem('aanya_theme') || 'theme-pastel',
    voiceEnabled: localStorage.getItem('aanya_tts_enabled') !== 'false',
    soundFxEnabled: localStorage.getItem('aanya_sound_fx') !== 'false',
    selectedVoiceURI: localStorage.getItem('aanya_voice_uri') || '',
    currentState: 'standby', // 'standby' | 'listening' | 'thinking' | 'speaking' | 'executing'
    tasks: [],
    isListening: false,
    pendingAttachments: []   // Array of { name, mime_type, data_b64, objectUrl? }
  };

  // ── DOM References ─────────────────────────────────────────────────────────
  const DOM = {
    body: document.body,
    stateBadge: document.getElementById('stateBadge'),
    stateText: document.getElementById('stateText'),
    captionText: document.getElementById('captionText'),
    audioWaveBars: document.getElementById('audioWaveBars'),
    orbCenterBtn: document.getElementById('orbCenterBtn'),
    dockMicBtn: document.getElementById('dockMicBtn'),
    queryInput: document.getElementById('queryInput'),
    chatForm: document.getElementById('chatForm'),
    chatStream: document.getElementById('chatStream'),
    voiceSpeakToggle: document.getElementById('voiceSpeakToggle'),
    themeToggleBtn: document.getElementById('themeToggleBtn'),
    tasksToggleBtn: document.getElementById('tasksToggleBtn'),
    taskCountBadge: document.getElementById('taskCountBadge'),
    tasksDrawer: document.getElementById('tasksDrawer'),
    drawerTaskBadge: document.getElementById('drawerTaskBadge'),
    closeTasksBtn: document.getElementById('closeTasksBtn'),
    addTaskForm: document.getElementById('addTaskForm'),
    newTaskInput: document.getElementById('newTaskInput'),
    tasksList: document.getElementById('tasksList'),
    emptyTasksNotice: document.getElementById('emptyTasksNotice'),
    settingsToggleBtn: document.getElementById('settingsToggleBtn'),
    settingsModal: document.getElementById('settingsModal'),
    closeSettingsBtn: document.getElementById('closeSettingsBtn'),
    saveSettingsBtn: document.getElementById('saveSettingsBtn'),
    sessionIdInput: document.getElementById('sessionIdInput'),
    themeSelect: document.getElementById('themeSelect'),
    voiceSelect: document.getElementById('voiceSelect'),
    soundFxToggle: document.getElementById('soundFxToggle'),
    // File upload
    attachBtn: document.getElementById('attachBtn'),
    fileInput: document.getElementById('fileInput'),
    attachmentPreview: document.getElementById('attachmentPreview'),
    dropZoneOverlay: document.getElementById('dropZoneOverlay'),
    // Adaptive Memory DOM References
    memoryToggleBtn: document.getElementById('memoryToggleBtn'),
    memoryCountBadge: document.getElementById('memoryCountBadge'),
    memoryDrawer: document.getElementById('memoryDrawer'),
    closeMemoryBtn: document.getElementById('closeMemoryBtn'),
    teachForm: document.getElementById('teachForm'),
    teachInput: document.getElementById('teachInput'),
    memInteractions: document.getElementById('memInteractions'),
    memThumbsUp: document.getElementById('memThumbsUp'),
    memCorrections: document.getElementById('memCorrections'),
    memUserName: document.getElementById('memUserName'),
    memPreferencesList: document.getElementById('memPreferencesList'),
    emptyPreferencesNotice: document.getElementById('emptyPreferencesNotice'),
    memRulesList: document.getElementById('memRulesList'),
    emptyRulesNotice: document.getElementById('emptyRulesNotice'),
    memFactsList: document.getElementById('memFactsList'),
    emptyFactsNotice: document.getElementById('emptyFactsNotice'),
    memInterestsTags: document.getElementById('memInterestsTags'),
    emptyInterestsNotice: document.getElementById('emptyInterestsNotice'),
    clearMemoryBtn: document.getElementById('clearMemoryBtn')
  };

  // ── Initialize Orb Visualizer ──────────────────────────────────────────────
  let orb = null;
  try {
    if (window.VoiceOrbVisualizer) {
      orb = new window.VoiceOrbVisualizer('orbCanvas');
    }
  } catch (err) {
    console.warn('Orb visualizer initialization failed:', err);
  }

  // ── Web Audio API Synthesizer (Sci-Fi Chimes) ──────────────────────────────
  let audioCtx = null;
  function getAudioContext() {
    if (!audioCtx) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext) {
        audioCtx = new AudioContext();
      }
    }
    if (audioCtx && audioCtx.state === 'suspended') {
      audioCtx.resume();
    }
    return audioCtx;
  }

  // Alexa / Bixby style wake tone: dual ascending sine chime
  function playWakeChime() {
    if (!state.soundFxEnabled) return;
    try {
      const ctx = getAudioContext();
      if (!ctx) return;
      const now = ctx.currentTime;

      // Note 1: D5 (587.33 Hz)
      const osc1 = ctx.createOscillator();
      const gain1 = ctx.createGain();
      osc1.type = 'sine';
      osc1.frequency.setValueAtTime(587.33, now);
      gain1.gain.setValueAtTime(0.08, now);
      gain1.gain.exponentialRampToValueAtTime(0.0001, now + 0.35);
      osc1.connect(gain1);
      gain1.connect(ctx.destination);
      osc1.start(now);
      osc1.stop(now + 0.35);

      // Note 2: A5 (880 Hz)
      const osc2 = ctx.createOscillator();
      const gain2 = ctx.createGain();
      osc2.type = 'sine';
      osc2.frequency.setValueAtTime(880, now + 0.1);
      gain2.gain.setValueAtTime(0.07, now + 0.1);
      gain2.gain.exponentialRampToValueAtTime(0.0001, now + 0.5);
      osc2.connect(gain2);
      gain2.connect(ctx.destination);
      osc2.start(now + 0.1);
      osc2.stop(now + 0.5);
    } catch (e) {
      console.warn('Audio chime failed:', e);
    }
  }

  // Soft completion chime
  function playDoneChime() {
    if (!state.soundFxEnabled) return;
    try {
      const ctx = getAudioContext();
      if (!ctx) return;
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(783.99, now); // G5
      gain.gain.setValueAtTime(0.05, now);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.28);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now);
      osc.stop(now + 0.28);
    } catch (e) {
      console.warn('Audio chime failed:', e);
    }
  }

  // ── Visual State Controller ────────────────────────────────────────────────
  function setState(newState, caption = '') {
    state.currentState = newState;

    // Update body classes for styling hooks
    DOM.body.classList.remove('state-standby', 'state-listening', 'state-thinking', 'state-speaking', 'state-executing');
    DOM.body.classList.add(`state-${newState}`);

    // Update state badge
    if (DOM.stateBadge) {
      DOM.stateBadge.className = `state-pill state-${newState}`;
    }
    if (DOM.stateText) {
      const labels = {
        standby: 'Standby',
        listening: 'Listening...',
        thinking: 'Thinking...',
        speaking: 'Speaking...',
        executing: 'Processing...'
      };
      DOM.stateText.textContent = labels[newState] || newState;
    }

    // Update caption
    if (DOM.captionText) {
      if (caption) {
        DOM.captionText.textContent = caption;
      } else {
        const defaultCaptions = {
          standby: 'Tap the orb or speak to Aanya',
          listening: 'Listening to your voice...',
          thinking: 'Consulting Gemini intelligence...',
          speaking: 'Responding...',
          executing: 'Executing command...'
        };
        DOM.captionText.textContent = defaultCaptions[newState] || '';
      }
    }

    // Sync Orb canvas
    if (orb) {
      orb.setState(newState);
      if (newState === 'speaking') {
        orb.setAmplitude(0.75);
      } else if (newState === 'listening') {
        orb.setAmplitude(0.6);
      } else {
        orb.setAmplitude(0);
      }
    }

    // Sync Mic dock button active indicator
    if (DOM.dockMicBtn) {
      if (newState === 'listening') {
        DOM.dockMicBtn.classList.add('active');
      } else {
        DOM.dockMicBtn.classList.remove('active');
      }
    }
  }

  // ── Web Speech Recognition (Mic Input) ─────────────────────────────────────
  let recognition = null;
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
      state.isListening = true;
      playWakeChime();
      setState('listening', 'Listening to you...');
    };

    recognition.onresult = (event) => {
      let interimTranscript = '';
      let finalTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          finalTranscript += event.results[i][0].transcript;
        } else {
          interimTranscript += event.results[i][0].transcript;
        }
      }

      if (interimTranscript && DOM.captionText) {
        DOM.captionText.textContent = `"${interimTranscript}"`;
        if (orb) orb.setAmplitude(0.85);
      }

      if (finalTranscript) {
        DOM.queryInput.value = finalTranscript;
        handleUserQuery(finalTranscript);
      }
    };

    recognition.onerror = (event) => {
      console.warn('Speech recognition error:', event.error);
      state.isListening = false;
      if (event.error === 'not-allowed') {
        setState('standby', 'Microphone access was denied in browser permissions.');
      } else if (event.error === 'no-speech') {
        setState('standby', 'No voice detected. Tap to try again.');
      } else {
        setState('standby', `Voice input paused (${event.error}).`);
      }
    };

    recognition.onend = () => {
      state.isListening = false;
      if (state.currentState === 'listening') {
        setState('standby');
      }
    };
  }

  function toggleListening() {
    if (!SpeechRecognition) {
      appendAssistantMessage("Speech recognition is not supported in this browser. You can type your request in the box below.");
      return;
    }

    if (state.isListening) {
      try {
        recognition.stop();
      } catch (e) { }
      state.isListening = false;
      setState('standby');
    } else {
      try {
        stopSpeaking();
        unlockSpeechSynthesis();
        recognition.start();
      } catch (e) {
        console.warn('Could not start recognition:', e);
      }
    }
  }

  // ── Speech Synthesis (TTS) ─────────────────────────────────────────────────
  let availableVoices = [];

  // ── British English voice priority (Aanya accent) ─────────────────────────
  // Prioritize refined, natural British female voices for Aanya
  const PREFERRED_VOICES = [
    'Serena',
    'Kate',
    'Google UK English Female',
    'Microsoft Sonia Online (Natural) - English (United Kingdom)',
    'Microsoft Hazel Online (Natural) - English (United Kingdom)',
    'Microsoft Libby Online (Natural) - English (United Kingdom)',
    'Daniel',
    'Oliver',
    'Microsoft Ryan Online (Natural) - English (United Kingdom)',
    'Google UK English Male',
    'en-GB',
  ];

  function pickBestVoice() {
    // If user manually chose a voice in Settings, always honour it
    if (state.selectedVoiceURI) {
      const custom = availableVoices.find((v) => v.voiceURI === state.selectedVoiceURI);
      if (custom) return custom;
    }
    // Walk priority list: match by name prefix OR lang code token
    for (const name of PREFERRED_VOICES) {
      const match = availableVoices.find((v) =>
        v.name.toLowerCase().includes(name.toLowerCase()) ||
        (name === 'en-GB' && v.lang.toLowerCase() === 'en-gb')
      );
      if (match) return match;
    }
    // Graceful fallback: any local British voice
    const localGB = availableVoices.find((v) => v.lang.toLowerCase().startsWith('en-gb') && v.localService);
    if (localGB) return localGB;
    // Any British voice
    const anyGB = availableVoices.find((v) => v.lang.toLowerCase().startsWith('en-gb'));
    if (anyGB) return anyGB;
    // Last resort: any English voice
    return availableVoices.find((v) => v.lang.toLowerCase().startsWith('en')) || null;
  }

  function loadVoices() {
    if (!window.speechSynthesis) return;
    availableVoices = window.speechSynthesis.getVoices();
    if (DOM.voiceSelect) {
      DOM.voiceSelect.innerHTML = '<option value="">🇬🇧 Auto — Best British Voice</option>';
      // Show British voices first, then other English voices
      const sortedVoices = [...availableVoices].sort((a, b) => {
        const aGB = a.lang.toLowerCase().startsWith('en-gb') ? -1 : 0;
        const bGB = b.lang.toLowerCase().startsWith('en-gb') ? -1 : 0;
        return aGB - bGB;
      });
      sortedVoices.forEach((voice) => {
        if (voice.lang.toLowerCase().startsWith('en')) {
          const opt = document.createElement('option');
          opt.value = voice.voiceURI;
          const flag = voice.lang.toLowerCase().startsWith('en-gb') ? '🇬🇧 ' : (voice.lang.toLowerCase().startsWith('en-us') ? '🇺🇸 ' : '🌐 ');
          const local = voice.localService ? ' ★' : '';
          opt.textContent = `${flag}${voice.name} (${voice.lang})${local}`;
          if (voice.voiceURI === state.selectedVoiceURI) {
            opt.selected = true;
          }
          DOM.voiceSelect.appendChild(opt);
        }
      });
    }
  }

  if (window.speechSynthesis) {
    loadVoices();
    window.speechSynthesis.onvoiceschanged = loadVoices;
  }

  // Pre-unlock speech synthesis on user interaction
  function unlockSpeechSynthesis() {
    if (window.speechSynthesis && window.speechSynthesis.paused) {
      try { window.speechSynthesis.resume(); } catch (e) { }
    }
  }

  // Tracks the currently playing audio
  let _currentAudio = null;
  let _ttsAbortCtrl = null;

  // ── TTS Sentence Queue ────────────────────────────────────────────────────
  // Seamless concurrent audio playback: as tokens stream in, complete clauses
  // and sentences speak instantly with zero lag and no awkward pauses.
  const _ttsQueue = [];
  let _ttsPlaying = false;
  let _streamInProgress = false;

  /**
   * Helper: extract ready sentences or long clauses from a buffer
   * without fragile regex lookbehinds.
   */
  function extractReadySentences(buffer) {
    const toSpeak = [];
    let text = buffer;

    while (text.length > 0) {
      // Punctuation (. ! ? ;) followed by whitespace or newline
      const match = text.match(/^([\s\S]*?[.?!;]+)(?:\s+|\n+)([\s\S]*)$/);
      if (match) {
        const sentence = match[1].trim();
        if (sentence) toSpeak.push(sentence);
        text = match[2];
        continue;
      }

      // Early break for long sentences (> 100 chars) at a comma, semicolon, or dash
      if (text.length > 100) {
        const clauseMatch = text.match(/^([\s\S]*?[,:;—])\s+([\s\S]*)$/);
        if (clauseMatch && clauseMatch[1].trim().length > 30) {
          toSpeak.push(clauseMatch[1].trim());
          text = clauseMatch[2];
          continue;
        }
      }

      break;
    }

    return { toSpeak, remainder: text };
  }

  /**
   * Add a text chunk to the TTS playback queue and start draining if idle.
   */
  function enqueueTTS(text) {
    if (!state.voiceEnabled || !text || !text.trim()) return;
    _ttsQueue.push(text.trim());
    if (!_ttsPlaying) {
      _drainTTSQueue();
    }
  }

  async function _drainTTSQueue() {
    if (_ttsPlaying || _ttsQueue.length === 0) return;
    _ttsPlaying = true;
    setState('speaking', 'Responding...');

    while (_ttsPlaying) {
      if (_ttsQueue.length > 0) {
        const chunk = _ttsQueue.shift();
        await _playSingleChunk(chunk);
      } else if (_streamInProgress) {
        // Stream still receiving tokens — brief wait for next sentence chunk
        await new Promise((r) => setTimeout(r, 100));
      } else {
        // Queue empty and stream done
        break;
      }
    }

    _ttsPlaying = false;
    // Return to standby when speech completes
    if (!_streamInProgress && state.currentState === 'speaking') {
      playDoneChime();
      setState('standby');
    }
  }

  /**
   * Play a single sentence chunk via Web Speech API (instant, 0ms latency),
   * falling back to server gTTS if needed.
   */
  function _playSingleChunk(text) {
    if (!text || !text.trim()) return Promise.resolve();

    return new Promise((resolve) => {
      // 1. Primary path: Instant Native Web Speech (0ms latency, native British voice)
      if (window.speechSynthesis) {
        try {
          const utt = new SpeechSynthesisUtterance(text);
          utt.lang = 'en-GB';
          utt.rate = 1.02;
          utt.pitch = 1.0;
          const best = pickBestVoice();
          if (best) utt.voice = best;

          let done = false;
          const finish = () => {
            if (!done) {
              done = true;
              clearTimeout(watchdog);
              resolve();
            }
          };

          utt.onend = finish;
          utt.onerror = finish;

          // Safety watchdog to prevent browser speech synthesis from hanging
          const watchdog = setTimeout(finish, Math.max(3000, text.length * 90));
          window.speechSynthesis.speak(utt);
          return;
        } catch (e) {
          console.warn('[TTS] SpeechSynthesis failed, trying fallback:', e);
        }
      }

      // 2. Server gTTS fallback (for environments without Web Speech)
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 8000);

      fetch('/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
        signal: ctrl.signal,
      })
        .then((res) => {
          clearTimeout(timer);
          if (!res.ok) throw new Error(`TTS status ${res.status}`);
          return res.blob();
        })
        .then((blob) => {
          const url = URL.createObjectURL(blob);
          const audio = new Audio(url);
          _currentAudio = audio;
          const cleanup = () => {
            URL.revokeObjectURL(url);
            _currentAudio = null;
            resolve();
          };
          audio.onended = cleanup;
          audio.onerror = cleanup;
          audio.play().catch(cleanup);
        })
        .catch(() => {
          clearTimeout(timer);
          resolve();
        });
    });
  }

  function stopSpeaking() {
    if (_ttsAbortCtrl) { _ttsAbortCtrl.abort(); _ttsAbortCtrl = null; }
    _ttsQueue.length = 0;
    _ttsPlaying = false;
    if (_currentAudio) {
      try { _currentAudio.pause(); _currentAudio.src = ''; } catch (e) { }
      _currentAudio = null;
    }
    if (window.speechSynthesis) {
      try { window.speechSynthesis.cancel(); } catch (e) { }
    }
  }

  // ── Primary TTS: full-text path (used by non-streaming fallback) ──────────
  async function speakResponse(text) {
    if (!state.voiceEnabled || !text || !text.trim()) return;
    stopSpeaking();
    setState('speaking', `"${text.slice(0, 70)}${text.length > 70 ? '...' : ''}"`);
    const sentences = text.match(/[^.!?]+[.!?]+(\s|$)|[^.!?]+$/g) || [text];
    for (const s of sentences) {
      if (s.trim()) enqueueTTS(s.trim());
    }
  }

  // ── File Upload Helpers ────────────────────────────────────────────────────

  /** Map a MIME type to a clean Bootstrap Icon. */
  function mimeIcon(mime) {
    if (mime.startsWith('image/')) return '<i class="bi bi-image"></i>';
    if (mime.startsWith('video/')) return '<i class="bi bi-camera-video"></i>';
    if (mime.startsWith('audio/')) return '<i class="bi bi-file-earmark-music"></i>';
    if (mime === 'application/pdf') return '<i class="bi bi-file-earmark-pdf"></i>';
    if (mime.startsWith('text/')) return '<i class="bi bi-file-earmark-text"></i>';
    return '<i class="bi bi-file-earmark"></i>';
  }

  /** Read a File object and resolve with a base64 data string (no prefix). */
  function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        // result is "data:<mime>;base64,<data>" — we only want the data part
        const b64 = reader.result.split(',')[1];
        resolve(b64);
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  /** Re-render the chip strip based on state.pendingAttachments. */
  function renderAttachmentPreview() {
    if (!DOM.attachmentPreview) return;
    DOM.attachmentPreview.innerHTML = '';
    const count = state.pendingAttachments.length;

    if (count === 0) {
      DOM.attachmentPreview.classList.remove('visible');
      DOM.attachBtn?.classList.remove('has-files');
      return;
    }

    DOM.attachmentPreview.classList.add('visible');
    DOM.attachBtn?.classList.add('has-files');
    DOM.attachBtn?.setAttribute('data-count', count);

    state.pendingAttachments.forEach((att, idx) => {
      const chip = document.createElement('span');
      chip.className = 'attach-chip';
      chip.innerHTML = `
        <span class="chip-icon" aria-hidden="true">${mimeIcon(att.mime_type)}</span>
        <span class="chip-name" title="${escapeHTML(att.name)}">${escapeHTML(att.name.slice(0, 22))}${att.name.length > 22 ? '…' : ''}</span>
        <button type="button" class="chip-remove" aria-label="Remove ${escapeHTML(att.name)}" data-idx="${idx}"><i class="bi bi-x"></i></button>
      `;
      chip.querySelector('.chip-remove').addEventListener('click', () => {
        state.pendingAttachments.splice(idx, 1);
        renderAttachmentPreview();
      });
      DOM.attachmentPreview.appendChild(chip);
    });
  }

  /** Process File objects from input or drag-drop into state.pendingAttachments. */
  async function processFiles(files) {
    const MAX_FILES = 10;
    const MAX_MB = 20;

    for (const file of Array.from(files).slice(0, MAX_FILES)) {
      if (file.size > MAX_MB * 1024 * 1024) {
        appendAssistantMessage(`⚠️ "${file.name}" exceeds the ${MAX_MB} MB limit and was skipped.`);
        continue;
      }
      try {
        const b64 = await fileToBase64(file);
        state.pendingAttachments.push({
          name: file.name,
          mime_type: file.type || 'application/octet-stream',
          data_b64: b64,
          // For image previews in the user card
          objectUrl: file.type.startsWith('image/') ? URL.createObjectURL(file) : null,
        });
      } catch (e) {
        console.warn('Could not read file:', file.name, e);
      }
    }
    renderAttachmentPreview();
  }

  // ── Chat Feed Messaging ────────────────────────────────────────────────────
  function appendUserMessage(text, attachments = []) {
    const card = document.createElement('article');
    card.className = 'chat-card user-card';

    // Build attachment thumbnails for images, file pills for others
    let attHTML = '';
    if (attachments.length > 0) {
      const thumbs = attachments
        .filter(a => a.objectUrl)
        .map(a => `<img class="card-attachment-thumb" src="${a.objectUrl}" alt="${escapeHTML(a.name)}" loading="lazy">`)
        .join('');
      const files = attachments
        .filter(a => !a.objectUrl)
        .map(a => `<span class="card-attachment-file">${mimeIcon(a.mime_type)} ${escapeHTML(a.name)}</span>`)
        .join('');
      if (thumbs || files) {
        attHTML = `<div class="card-attachments">${thumbs}${files}</div>`;
      }
    }

    card.innerHTML = `
      <div class="card-body">
        <header class="card-header">
          <span class="card-author">You</span>
          <time class="card-timestamp">${formatTime()}</time>
        </header>
        <div class="card-content">
          ${attHTML}
          <p>${escapeHTML(text)}</p>
        </div>
      </div>
      <div class="card-avatar" aria-hidden="true"><i class="bi bi-person-fill"></i></div>
    `;
    DOM.chatStream.appendChild(card);
    card.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }

  function appendAssistantMessage(reply, action = null, actionData = null) {
    const card = document.createElement('article');
    card.className = 'chat-card assistant-card';

    let actionHTML = '';
    if (action === 'open-url' && actionData) {
      actionHTML = `
        <a href="${actionData}" target="_blank" rel="noopener noreferrer" class="card-action-badge">
          <i class="bi bi-box-arrow-up-right"></i> <span>Open:</span> <strong>${actionData}</strong>
        </a>
      `;
    }

    let learnedHTML = '';
    if (action === 'learned' && Array.isArray(actionData) && actionData.length > 0) {
      learnedHTML = `
        <div class="learned-pills" aria-label="Learned insights">
          ${actionData.map(item => `<span class="learned-pill"><i class="bi bi-lightbulb"></i> Learned: ${escapeHTML(item)}</span>`).join('')}
        </div>
      `;
    }

    card.innerHTML = `
      <div class="card-avatar" aria-hidden="true"><i class="bi bi-stars"></i></div>
      <div class="card-body">
        <header class="card-header">
          <span class="card-author">Aanya</span>
          <time class="card-timestamp">${formatTime()}</time>
        </header>
        <div class="card-content">
          <p>${escapeHTML(reply)}</p>
          ${actionHTML}
          ${learnedHTML}
          <div class="card-feedback-bar">
            <button type="button" class="feedback-btn btn-up" title="Helpful answer"><i class="bi bi-hand-thumbs-up"></i> Helpful</button>
            <button type="button" class="feedback-btn btn-down" title="Teach Aanya how to improve"><i class="bi bi-hand-thumbs-down"></i> Improve</button>
          </div>
          <div class="correction-box" style="display:none;">
            <input type="text" class="correction-input" placeholder="What should Aanya have said / what's correct?">
            <button type="button" class="correction-submit-btn">Teach</button>
          </div>
          <div class="feedback-toast" style="display:none;"></div>
        </div>
      </div>
    `;

    // Hook up feedback handlers
    const btnUp = card.querySelector('.btn-up');
    const btnDown = card.querySelector('.btn-down');
    const corrBox = card.querySelector('.correction-box');
    const corrInput = card.querySelector('.correction-input');
    const corrSubmit = card.querySelector('.correction-submit-btn');
    const toast = card.querySelector('.feedback-toast');

    btnUp?.addEventListener('click', async () => {
      btnUp.classList.add('active-up');
      btnDown.disabled = true;
      btnUp.disabled = true;
      toast.style.display = 'block';
      toast.textContent = 'Recording positive feedback...';
      try {
        await submitFeedback(true, reply, '');
        toast.textContent = '✓ Thanks! Aanya learned this was helpful.';
        loadMemory();
      } catch (e) {
        toast.textContent = 'Feedback saved locally.';
      }
    });

    btnDown?.addEventListener('click', () => {
      corrBox.style.display = 'flex';
      corrInput.focus();
    });

    corrSubmit?.addEventListener('click', async () => {
      const correction = corrInput.value.trim();
      if (!correction) return;
      corrBox.style.display = 'none';
      btnDown.classList.add('active-down');
      btnUp.disabled = true;
      btnDown.disabled = true;
      toast.style.display = 'block';
      toast.textContent = 'Teaching Aanya...';
      try {
        await submitFeedback(false, reply, correction);
        toast.textContent = `✓ Learned: "${correction.slice(0, 40)}${correction.length > 40 ? '...' : ''}"`;
        loadMemory();
        playDoneChime();
      } catch (e) {
        toast.textContent = 'Correction recorded.';
      }
    });

    DOM.chatStream.appendChild(card);
    card.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }

  // ── API Communication ──────────────────────────────────────────────────────
  let _chatAbortCtrl = null;

  /**
   * Primary handler — uses SSE streaming for real-time token display.
   * Falls back to the non-streaming /chat endpoint if EventSource is unavailable.
   */
  // Sites and rich alias rules that Aanya can open — mirrors the server-side SITE_RULES.
  const AANYA_SITE_RULES = [
    {
      name: 'GitHub',
      aliases: ['github', 'git hub', 'git-hub', 'gethub'],
      url: 'https://github.com/Yuvika108',
    },
    {
      name: 'WhatsApp',
      aliases: ['whatsapp', 'whats app', "what's app", 'what app', 'whatsapp web', 'whats app web'],
      url: 'https://web.whatsapp.com/',
    },
    {
      name: 'YouTube',
      aliases: ['youtube', 'you tube'],
      url: 'https://www.youtube.com',
    },
    {
      name: 'Wikipedia',
      aliases: ['wikipedia', 'wiki'],
      url: 'https://www.wikipedia.org',
    },
    {
      name: 'Google',
      aliases: ['google'],
      url: 'https://www.google.com',
    },
    {
      name: 'Spotify',
      aliases: ['spotify'],
      url: 'https://open.spotify.com',
    },
    {
      name: 'LeetCode',
      aliases: ['leetcode', 'leet code'],
      url: 'https://leetcode.com/u/Yuv1ka/',
    },
  ];

  function getSiteOpenUrl(rawText) {
    const q = rawText.toLowerCase().trim();
    if (q.startsWith('what is ') || q.startsWith('who is ') || q.startsWith('how to ') || q.startsWith('why is ') || q.startsWith('tell me about ')) {
      return null;
    }
    for (const rule of AANYA_SITE_RULES) {
      if (rule.aliases.some(alias => q.includes(alias))) {
        return rule.url;
      }
    }
    return null;
  }

  let _lastSynchronouslyOpenedUrl = null;

  const CURATED_SPOTIFY_SUGGESTIONS = [
    'Bohemian Rhapsody Queen',
    'Blinding Lights The Weeknd',
    'Shape of You Ed Sheeran',
    'Starboy The Weeknd',
    'Flowers Miley Cyrus',
    'As It Was Harry Styles',
    'Believer Imagine Dragons',
    'Levitating Dua Lipa',
    'Viva La Vida Coldplay',
    'Stay Justin Bieber',
    'Kesariya Arijit Singh'
  ];

  function getSpotifySongUrl(rawText) {
    const q = rawText.toLowerCase().trim();

    // Exclude non-music actions that use the word 'play'
    const nonMusic = ['youtube', 'video', 'chess', 'cricket', 'game', 'football', 'tennis'];
    if (nonMusic.some(w => q.includes(w))) return null;

    // 1. Suggest song / music patterns
    if (/(?:can you\s+)?(?:suggest|recommend)(?:\s+me)?\s+(?:a|any|some)?\s*(?:good\s+)?(?:song|music|track)/i.test(q) ||
      /what\s+song\s+should\s+i\s+listen\s+to/i.test(q) ||
      /give\s+me\s+a\s+(?:good\s+)?song/i.test(q) ||
      /what\s+should\s+i\s+play/i.test(q)) {
      const picked = CURATED_SPOTIFY_SUGGESTIONS[Math.floor(Math.random() * CURATED_SPOTIFY_SUGGESTIONS.length)];
      return `https://open.spotify.com/search/${encodeURIComponent(picked)}`;
    }

    // 2. User suggests a specific song: "i suggest <song>", "how about playing <song>", "what about <song>"
    const userSuggest = q.match(/\b(?:i suggest|how about playing|what about playing|how about|what about)\s+(.+)/i);
    if (userSuggest) {
      let clean = userSuggest[1].replace(/\b(?:on|from|in)\s+spotify\b/gi, '')
        .replace(/\b(?:please|for me)\b/gi, '')
        .trim()
        .replace(/^[.,?!'"]+|[.,?!'"]+$/g, '');
      if (clean && !/^(?:a\s+|any\s+|some\s+)?(?:good\s+)?(?:song|music|track)$/i.test(clean)) {
        return `https://open.spotify.com/search/${encodeURIComponent(clean)}`;
      }
    }

    // 3. Direct play commands: "play <song>", "listen to <song>", "put on <song>"
    const playMatch = q.match(/\b(?:play|listen to|put on)\s+(.+)/i);
    if (playMatch) {
      let clean = playMatch[1].replace(/\b(?:on|from|in)\s+spotify\b/gi, '')
        .replace(/\b(?:please|for me)\b/gi, '')
        .trim()
        .replace(/^[.,?!'"]+|[.,?!'"]+$/g, '');
      if (!clean || /^(?:music|some music|a song|songs|spotify|something)$/i.test(clean)) {
        return 'https://open.spotify.com';
      }
      return `https://open.spotify.com/search/${encodeURIComponent(clean)}`;
    }

    // 4. Explicit spotify command: "spotify <song>"
    const spotifyMatch = q.match(/\bspotify\s+(.+)/i);
    if (spotifyMatch) {
      let clean = spotifyMatch[1].replace(/\b(?:please|for me)\b/gi, '').trim().replace(/^[.,?!'"]+|[.,?!'"]+$/g, '');
      if (clean) {
        return `https://open.spotify.com/search/${encodeURIComponent(clean)}`;
      }
    }

    return null;
  }

  async function handleUserQuery(query) {
    const text = query.trim();
    const attachments = [...state.pendingAttachments]; // snapshot before clearing

    if (!text && attachments.length === 0) return;

    // ── URL & Spotify opener: must fire window.open() HERE, in the direct user-gesture
    //    context, before any async operations — otherwise browsers block it.
    if (text && attachments.length === 0) {
      _lastSynchronouslyOpenedUrl = null;
      const spotifyUrl = getSpotifySongUrl(text);
      if (spotifyUrl) {
        _lastSynchronouslyOpenedUrl = spotifyUrl;
        window.open(spotifyUrl, '_blank', 'noopener,noreferrer');
      } else {
        const siteUrl = getSiteOpenUrl(text);
        if (siteUrl) {
          _lastSynchronouslyOpenedUrl = siteUrl;
          window.open(siteUrl, '_blank', 'noopener,noreferrer');
        }
      }
    }

    // Cancel any in-flight request
    if (_chatAbortCtrl) { _chatAbortCtrl.abort(); }
    _chatAbortCtrl = new AbortController();

    // Clear the input + pending attachments immediately
    DOM.queryInput.value = '';
    state.pendingAttachments = [];
    renderAttachmentPreview();

    appendUserMessage(text || '(attached file)', attachments);
    setState('thinking', attachments.length > 0 ? 'Analysing your files…' : 'Processing query...');

    // Prepare request payload
    const payload = {
      message: text,
      session_id: state.sessionId,
      attachments: attachments.map(({ name, mime_type, data_b64 }) => ({
        filename: name,
        name: name,
        mime_type: mime_type,
        data: data_b64,
        data_b64: data_b64,
      })),
    };

    // ── Try SSE streaming first ──────────────────────────────────────────────
    try {
      await chatViaStream(payload, attachments.length > 0);
    } catch (streamErr) {
      // SSE failed (e.g. network, parse error) — fall back to regular /chat
      console.warn('[Stream] Falling back to /chat:', streamErr.message);
      await chatViaFetch(payload);
    }
  }

  /**
   * SSE streaming path — creates a streaming assistant card and
   * appends text tokens as they arrive from /chat/stream.
   */
  async function chatViaStream(payload, hasAttachments) {
    return new Promise((resolve, reject) => {
      const ctrl = _chatAbortCtrl;
      _streamInProgress = true;
      unlockSpeechSynthesis();

      // Create a live streaming card (shows a blinking cursor while streaming)
      const card = document.createElement('article');
      card.className = 'chat-card assistant-card streaming';
      const timestamp = formatTime();
      card.innerHTML = `
        <div class="card-avatar" aria-hidden="true"><i class="bi bi-stars"></i></div>
        <div class="card-body">
          <header class="card-header">
            <span class="card-author">Aanya</span>
            <time class="card-timestamp">${timestamp}</time>
          </header>
          <div class="card-content">
            <p id="streaming-text-${Date.now()}"></p>
          </div>
        </div>
      `;
      DOM.chatStream.appendChild(card);
      card.scrollIntoView({ behavior: 'smooth', block: 'end' });
      const streamingP = card.querySelector('p');

      let fullReply = '';
      let finalAction = null;
      let finalData = null;
      let settled = false;
      let ttsBuffer = '';  // accumulates tokens until sentence boundaries

      const TIMEOUT_MS = 45000;
      const timer = setTimeout(() => {
        ctrl && ctrl.abort();
        _streamInProgress = false;
        if (!settled) { settled = true; reject(new Error('Stream timeout')); }
      }, TIMEOUT_MS);

      setState('thinking', hasAttachments ? 'Analysing your files…' : 'Thinking...');

      fetch('/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: ctrl?.signal,
      })
        .then(res => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          return res.body.getReader();
        })
        .then(async reader => {
          const decoder = new TextDecoder();
          let buffer = '';

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            // Parse SSE lines
            let nl;
            while ((nl = buffer.indexOf('\n\n')) !== -1) {
              const raw = buffer.slice(0, nl).trim();
              buffer = buffer.slice(nl + 2);
              if (!raw.startsWith('data:')) continue;
              const jsonStr = raw.slice(5).trim();
              if (!jsonStr) continue;

              let packet;
              try { packet = JSON.parse(jsonStr); } catch { continue; }

              if (packet.type === 'token') {
                const newText = (packet.text ?? packet.token ?? '');
                if (!newText) continue;

                if (fullReply === '') {
                  stopSpeaking(); // clear any prior audio
                  setState('speaking', 'Responding...');
                }
                fullReply += newText;
                ttsBuffer += newText;
                streamingP.textContent = fullReply;
                card.scrollIntoView({ behavior: 'smooth', block: 'end' });

                // ── Fire voice as soon as complete clauses/sentences form ─────
                const { toSpeak, remainder } = extractReadySentences(ttsBuffer);
                if (toSpeak.length > 0) {
                  ttsBuffer = remainder;
                  for (const sentence of toSpeak) {
                    enqueueTTS(sentence);
                  }
                }

              } else if (packet.type === 'done') {
                finalAction = packet.action || null;
                finalData = packet.action_data || null;
                if (packet.reply && packet.reply.length >= fullReply.length) {
                  fullReply = packet.reply;
                  streamingP.textContent = fullReply;
                }
              } else if (packet.type === 'error') {
                throw new Error(packet.error || 'Stream error');
              }
            }
          }

          // Flush any remaining buffered text for speech
          if (ttsBuffer.trim()) {
            enqueueTTS(ttsBuffer.trim());
            ttsBuffer = '';
          }

          _streamInProgress = false;

          // Streaming complete — finalise the card
          clearTimeout(timer);
          card.classList.remove('streaming');

          if (!fullReply) fullReply = "I didn't receive a response.";

          // Inject feedback bar
          const contentDiv = card.querySelector('.card-content');
          attachFeedbackBar(contentDiv, fullReply);

          // If voice is disabled or TTS has already completed, return to standby immediately
          if (!state.voiceEnabled || !_ttsPlaying) {
            playDoneChime();
            setState('standby');
          }

          // Side-effects
          if (finalAction === 'open-url' && finalData && finalData !== _lastSynchronouslyOpenedUrl) window.open(finalData, '_blank');
          _lastSynchronouslyOpenedUrl = null;
          if (finalAction === 'show-memory') { DOM.memoryDrawer?.classList.add('open'); loadMemory(); }
          if (finalAction === 'learned' || Array.isArray(finalData)) loadMemory();
          if (payload.message?.toLowerCase().match(/task|remember/)) loadTasks();

          if (!settled) { settled = true; resolve(); }
        })
        .catch(err => {
          clearTimeout(timer);
          _streamInProgress = false;
          card.remove();
          if (!settled) { settled = true; reject(err); }
        });
    });
  }

  /**
   * Non-streaming fallback — plain JSON /chat endpoint.
   */
  async function chatViaFetch(payload) {
    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: _chatAbortCtrl?.signal,
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      const reply = data.reply || "I didn't receive a response.";
      appendAssistantMessage(reply, data.action, data.action_data);
      speakResponse(reply);
      if (data.action === 'open-url' && data.action_data && data.action_data !== _lastSynchronouslyOpenedUrl) window.open(data.action_data, '_blank');
      _lastSynchronouslyOpenedUrl = null;
      if (data.action === 'show-memory') { DOM.memoryDrawer?.classList.add('open'); loadMemory(); }
      if (data.action === 'learned' || Array.isArray(data.action_data)) loadMemory();
      if (payload.message?.toLowerCase().match(/task|remember/)) loadTasks();
    } catch (err) {
      if (err.name !== 'AbortError') console.error('Chat error:', err);
      appendAssistantMessage(
        err.name === 'AbortError'
          ? 'Request cancelled — please try again.'
          : `Sorry, I ran into an issue: ${err.message}`
      );
      setState('standby');
    }
  }

  /**
   * Inject the 👍/👎 feedback bar into an existing card content div.
   * Extracted into its own function so both the streaming and non-streaming
   * paths can reuse it.
   */
  function attachFeedbackBar(contentDiv, reply) {
    const bar = document.createElement('div');
    bar.className = 'card-feedback-bar';
    bar.innerHTML = `
      <button type="button" class="feedback-btn btn-up" title="Helpful answer"><i class="bi bi-hand-thumbs-up"></i> Helpful</button>
      <button type="button" class="feedback-btn btn-down" title="Teach Aanya how to improve"><i class="bi bi-hand-thumbs-down"></i> Improve</button>
    `;
    const corrBox = document.createElement('div');
    corrBox.className = 'correction-box';
    corrBox.style.display = 'none';
    corrBox.innerHTML = `
      <input type="text" class="correction-input" placeholder="What should Aanya have said / what's correct?">
      <button type="button" class="correction-submit-btn">Teach</button>
    `;
    const toast = document.createElement('div');
    toast.className = 'feedback-toast';
    toast.style.display = 'none';

    contentDiv.appendChild(bar);
    contentDiv.appendChild(corrBox);
    contentDiv.appendChild(toast);

    const btnUp = bar.querySelector('.btn-up');
    const btnDown = bar.querySelector('.btn-down');
    const corrInput = corrBox.querySelector('.correction-input');
    const corrSub = corrBox.querySelector('.correction-submit-btn');

    btnUp.addEventListener('click', async () => {
      btnUp.classList.add('active-up');
      btnDown.disabled = btnUp.disabled = true;
      toast.style.display = 'block';
      toast.textContent = 'Recording positive feedback...';
      try {
        await submitFeedback(true, reply, '');
        toast.textContent = '✓ Thanks! Aanya learned this was helpful.';
        loadMemory();
      } catch { toast.textContent = 'Feedback saved locally.'; }
    });
    btnDown.addEventListener('click', () => { corrBox.style.display = 'flex'; corrInput.focus(); });
    corrSub.addEventListener('click', async () => {
      const correction = corrInput.value.trim();
      if (!correction) return;
      corrBox.style.display = 'none';
      btnDown.classList.add('active-down');
      btnUp.disabled = btnDown.disabled = true;
      toast.style.display = 'block';
      toast.textContent = 'Teaching Aanya...';
      try {
        await submitFeedback(false, reply, correction);
        toast.textContent = `✓ Learned: "${correction.slice(0, 40)}${correction.length > 40 ? '...' : ''}"}`;
        loadMemory();
        playDoneChime();
      } catch { toast.textContent = 'Correction recorded.'; }
    });
  }

  // ── Task Management Drawer ─────────────────────────────────────────────────
  async function loadTasks() {
    try {
      const response = await fetch(`/tasks/${encodeURIComponent(state.sessionId)}`);
      if (!response.ok) return;
      const data = await response.json();
      state.tasks = data.tasks || [];
      renderTasks();
    } catch (err) {
      console.warn('Failed to load tasks:', err);
    }
  }

  async function addTask(taskText) {
    if (!taskText.trim()) return;
    try {
      const response = await fetch(`/tasks/${encodeURIComponent(state.sessionId)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task: taskText.trim(),
          session_id: state.sessionId
        })
      });
      if (response.ok) {
        const data = await response.json();
        state.tasks = data.tasks || [];
        renderTasks();
        DOM.newTaskInput.value = '';
        playDoneChime();
      }
    } catch (err) {
      console.error('Failed to add task:', err);
    }
  }

  async function deleteTask(index) {
    try {
      // API task_number is 1-indexed
      const response = await fetch(`/tasks/${encodeURIComponent(state.sessionId)}/${index + 1}`, {
        method: 'DELETE'
      });
      if (response.ok) {
        const data = await response.json();
        state.tasks = data.tasks || [];
        renderTasks();
      }
    } catch (err) {
      console.error('Failed to delete task:', err);
    }
  }

  function renderTasks() {
    const count = state.tasks.length;
    if (DOM.taskCountBadge) DOM.taskCountBadge.textContent = count;
    if (DOM.drawerTaskBadge) DOM.drawerTaskBadge.textContent = `${count} item${count === 1 ? '' : 's'}`;

    if (!DOM.tasksList) return;
    DOM.tasksList.innerHTML = '';

    if (count === 0) {
      DOM.emptyTasksNotice.classList.add('visible');
    } else {
      DOM.emptyTasksNotice.classList.remove('visible');
      state.tasks.forEach((task, idx) => {
        const li = document.createElement('li');
        li.className = 'task-item';
        li.innerHTML = `
          <span>${idx + 1}. ${escapeHTML(task)}</span>
          <button class="task-delete-btn" aria-label="Delete task ${idx + 1}" data-index="${idx}" title="Remove task">
            <i class="bi bi-trash"></i>
          </button>
        `;
        DOM.tasksList.appendChild(li);
      });

      // Bind delete buttons
      DOM.tasksList.querySelectorAll('.task-delete-btn').forEach((btn) => {
        btn.addEventListener('click', (e) => {
          const idx = parseInt(btn.getAttribute('data-index'), 10);
          deleteTask(idx);
        });
      });
    }
  }

  // ── Adaptive Memory & Self-Improvement Controller ──────────────────────────
  async function submitFeedback(positive, lastReply, correction = '') {
    try {
      const response = await fetch('/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: state.sessionId,
          positive: positive,
          last_reply: lastReply,
          correction: correction
        })
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      loadMemory();
      return data;
    } catch (err) {
      console.error('Failed to submit feedback:', err);
      throw err;
    }
  }

  async function loadMemory() {
    try {
      const response = await fetch(`/memory/${encodeURIComponent(state.sessionId)}`);
      if (!response.ok) return;
      const data = await response.json();
      renderMemory(data);
    } catch (err) {
      console.warn('Failed to load memory:', err);
    }
  }

  function renderMemory(data) {
    if (!data) return;

    // Metrics
    if (DOM.memInteractions) DOM.memInteractions.textContent = data.interaction_count || 0;
    if (DOM.memThumbsUp) DOM.memThumbsUp.textContent = data.thumbs_up || 0;
    if (DOM.memCorrections) DOM.memCorrections.textContent = data.thumbs_down || 0;

    // User Identity
    if (DOM.memUserName) {
      DOM.memUserName.textContent = data.name ? `Name: ${data.name}` : 'Name: Not learned yet (tell Aanya "My name is...")';
    }

    // Badge count = preferences + rules + learned_facts
    const totalKnowledge = (data.preferences?.length || 0) + (data.behavior_rules?.length || 0) + (data.learned_facts?.length || 0);
    if (DOM.memoryCountBadge) {
      DOM.memoryCountBadge.textContent = totalKnowledge;
    }

    // Preferences
    if (DOM.memPreferencesList) {
      DOM.memPreferencesList.innerHTML = '';
      const prefs = data.preferences || [];
      if (prefs.length === 0) {
        if (DOM.emptyPreferencesNotice) DOM.emptyPreferencesNotice.style.display = 'block';
      } else {
        if (DOM.emptyPreferencesNotice) DOM.emptyPreferencesNotice.style.display = 'none';
        prefs.forEach((p) => {
          const li = document.createElement('li');
          li.className = 'memory-item';
          li.innerHTML = `<span><i class="bi bi-heart"></i> ${escapeHTML(p)}</span>`;
          DOM.memPreferencesList.appendChild(li);
        });
      }
    }

    // Behavior Rules
    if (DOM.memRulesList) {
      DOM.memRulesList.innerHTML = '';
      const rules = data.behavior_rules || [];
      if (rules.length === 0) {
        if (DOM.emptyRulesNotice) DOM.emptyRulesNotice.style.display = 'block';
      } else {
        if (DOM.emptyRulesNotice) DOM.emptyRulesNotice.style.display = 'none';
        rules.forEach((r) => {
          const li = document.createElement('li');
          li.className = 'memory-item';
          li.innerHTML = `<span><i class="bi bi-shield-check"></i> ${escapeHTML(r)}</span>`;
          DOM.memRulesList.appendChild(li);
        });
      }
    }

    // Learned Facts & Corrections
    if (DOM.memFactsList) {
      DOM.memFactsList.innerHTML = '';
      const facts = data.learned_facts || [];
      if (facts.length === 0) {
        if (DOM.emptyFactsNotice) DOM.emptyFactsNotice.style.display = 'block';
      } else {
        if (DOM.emptyFactsNotice) DOM.emptyFactsNotice.style.display = 'none';
        facts.forEach((f) => {
          const li = document.createElement('li');
          li.className = 'memory-item';
          li.innerHTML = `<span><i class="bi bi-lightbulb"></i> ${escapeHTML(f)}</span>`;
          DOM.memFactsList.appendChild(li);
        });
      }
    }

    // Detected Interests
    if (DOM.memInterestsTags) {
      DOM.memInterestsTags.innerHTML = '';
      const interests = data.interests || [];
      if (interests.length === 0) {
        if (DOM.emptyInterestsNotice) DOM.emptyInterestsNotice.style.display = 'block';
      } else {
        if (DOM.emptyInterestsNotice) DOM.emptyInterestsNotice.style.display = 'none';
        interests.forEach((item) => {
          const span = document.createElement('span');
          span.className = 'interest-tag';
          span.textContent = item;
          DOM.memInterestsTags.appendChild(span);
        });
      }
    }
  }

  async function clearMemory() {
    const confirmed = confirm("Are you sure you want Aanya to forget all learned preferences, rules, and facts for this session?");
    if (!confirmed) return;

    try {
      const response = await fetch(`/memory/${encodeURIComponent(state.sessionId)}`, {
        method: 'DELETE'
      });
      if (response.ok) {
        loadMemory();
        playDoneChime();
        appendAssistantMessage("I've wiped my memory for this session. We're starting fresh!");
      }
    } catch (err) {
      console.error('Failed to clear memory:', err);
    }
  }

  // ── Themes & Settings ──────────────────────────────────────────────────────
  function applyTheme(themeName) {
    state.theme = themeName;
    DOM.body.classList.remove('theme-pastel', 'theme-blush', 'theme-sage', 'theme-midnight', 'theme-bixby', 'theme-cyber');
    DOM.body.classList.add(themeName);
    localStorage.setItem('aanya_theme', themeName);
    if (DOM.themeSelect) DOM.themeSelect.value = themeName;
  }

  function cycleTheme() {
    const themes = ['theme-pastel', 'theme-blush', 'theme-sage'];
    const currentTheme = themes.includes(state.theme) ? state.theme : 'theme-pastel';
    const nextIdx = (themes.indexOf(currentTheme) + 1) % themes.length;
    applyTheme(themes[nextIdx]);
  }

  // ── Event Handlers ─────────────────────────────────────────────────────────
  function setupEventListeners() {
    // Unlock Web Speech on initial user interaction
    window.addEventListener('click', unlockSpeechSynthesis, { once: true });
    window.addEventListener('keydown', unlockSpeechSynthesis, { once: true });

    // Orb Center Click -> Trigger Mic Listening
    DOM.orbCenterBtn?.addEventListener('click', () => toggleListening());
    DOM.dockMicBtn?.addEventListener('click', () => toggleListening());

    // Submit Query via Form
    DOM.chatForm?.addEventListener('submit', (e) => {
      e.preventDefault();
      unlockSpeechSynthesis();
      handleUserQuery(DOM.queryInput.value);
    });

    // Toggle Spoken Voice Output (TTS)
    DOM.voiceSpeakToggle?.addEventListener('click', () => {
      state.voiceEnabled = !state.voiceEnabled;
      localStorage.setItem('aanya_tts_enabled', state.voiceEnabled);
      DOM.voiceSpeakToggle.classList.toggle('active', state.voiceEnabled);
      if (!state.voiceEnabled) {
        stopSpeaking();
      }
    });

    // ── File Upload ──────────────────────────────────────────────────────────
    DOM.attachBtn?.addEventListener('click', () => {
      DOM.fileInput?.click();
    });
    DOM.fileInput?.addEventListener('change', async (e) => {
      if (e.target.files?.length) {
        await processFiles(e.target.files);
        // reset so the same file can be re-selected
        DOM.fileInput.value = '';
      }
    });

    // ── Drag and Drop ────────────────────────────────────────────────────────
    let _dragDepth = 0;
    document.addEventListener('dragenter', (e) => {
      e.preventDefault();
      _dragDepth++;
      if (_dragDepth === 1 && DOM.dropZoneOverlay) {
        DOM.dropZoneOverlay.classList.add('active');
        DOM.dropZoneOverlay.setAttribute('aria-hidden', 'false');
      }
    });
    document.addEventListener('dragleave', (e) => {
      e.preventDefault();
      _dragDepth--;
      if (_dragDepth <= 0) {
        _dragDepth = 0;
        DOM.dropZoneOverlay?.classList.remove('active');
        DOM.dropZoneOverlay?.setAttribute('aria-hidden', 'true');
      }
    });
    document.addEventListener('dragover', (e) => e.preventDefault());
    document.addEventListener('drop', async (e) => {
      e.preventDefault();
      _dragDepth = 0;
      DOM.dropZoneOverlay?.classList.remove('active');
      DOM.dropZoneOverlay?.setAttribute('aria-hidden', 'true');
      if (e.dataTransfer?.files?.length) {
        await processFiles(e.dataTransfer.files);
        // Auto-submit if there is already a query typed
        if (DOM.queryInput.value.trim()) {
          handleUserQuery(DOM.queryInput.value);
        }
      }
    });

    // Theme Toggle Quick Button
    DOM.themeToggleBtn?.addEventListener('click', cycleTheme);

    // Suggestion Chips Carousel
    document.querySelectorAll('.chip-btn').forEach((chip) => {
      chip.addEventListener('click', () => {
        const query = chip.getAttribute('data-query');
        if (query) {
          DOM.queryInput.value = query;
          handleUserQuery(query);
        }
      });
    });

    // Tasks Drawer Open / Close
    DOM.tasksToggleBtn?.addEventListener('click', () => {
      DOM.memoryDrawer?.classList.remove('open');
      DOM.memoryDrawer?.setAttribute('aria-hidden', 'true');
      DOM.tasksDrawer.classList.toggle('open');
      DOM.tasksDrawer.setAttribute('aria-hidden', !DOM.tasksDrawer.classList.contains('open'));
    });

    DOM.closeTasksBtn?.addEventListener('click', () => {
      DOM.tasksDrawer.classList.remove('open');
      DOM.tasksDrawer.setAttribute('aria-hidden', 'true');
    });

    // Adaptive Memory Drawer Open / Close
    DOM.memoryToggleBtn?.addEventListener('click', () => {
      DOM.tasksDrawer?.classList.remove('open');
      DOM.tasksDrawer?.setAttribute('aria-hidden', 'true');
      DOM.memoryDrawer.classList.toggle('open');
      const isOpen = DOM.memoryDrawer.classList.contains('open');
      DOM.memoryDrawer.setAttribute('aria-hidden', !isOpen);
      if (isOpen) loadMemory();
    });

    DOM.closeMemoryBtn?.addEventListener('click', () => {
      DOM.memoryDrawer.classList.remove('open');
      DOM.memoryDrawer.setAttribute('aria-hidden', 'true');
    });

    // Quick Teach Form in Memory Drawer
    DOM.teachForm?.addEventListener('submit', (e) => {
      e.preventDefault();
      const text = DOM.teachInput.value.trim();
      if (text) {
        DOM.teachInput.value = '';
        handleUserQuery(text);
      }
    });

    // Clear Memory Button
    DOM.clearMemoryBtn?.addEventListener('click', () => {
      clearMemory();
    });

    // Add Task in Drawer
    DOM.addTaskForm?.addEventListener('submit', (e) => {
      e.preventDefault();
      addTask(DOM.newTaskInput.value);
    });

    // Settings Modal Open / Close
    DOM.settingsToggleBtn?.addEventListener('click', () => {
      DOM.sessionIdInput.value = state.sessionId;
      DOM.themeSelect.value = state.theme;
      DOM.soundFxToggle.checked = state.soundFxEnabled;
      DOM.settingsModal.showModal();
    });

    DOM.closeSettingsBtn?.addEventListener('click', () => {
      DOM.settingsModal.close();
    });

    DOM.saveSettingsBtn?.addEventListener('click', () => {
      const newSession = DOM.sessionIdInput.value.trim() || 'default';
      const newTheme = DOM.themeSelect.value;
      state.sessionId = newSession;
      state.soundFxEnabled = DOM.soundFxToggle.checked;
      state.selectedVoiceURI = DOM.voiceSelect.value;

      localStorage.setItem('aanya_session_id', state.sessionId);
      localStorage.setItem('aanya_sound_fx', state.soundFxEnabled);
      localStorage.setItem('aanya_voice_uri', state.selectedVoiceURI);

      applyTheme(newTheme);
      loadTasks();
      loadMemory();
      DOM.settingsModal.close();
    });

    // Close modal on click outside
    DOM.settingsModal?.addEventListener('click', (e) => {
      const rect = DOM.settingsModal.getBoundingClientRect();
      const inDialog = (
        rect.top <= e.clientY &&
        e.clientY <= rect.top + rect.height &&
        rect.left <= e.clientX &&
        e.clientX <= rect.left + rect.width
      );
      if (!inDialog) {
        DOM.settingsModal.close();
      }
    });

    // Keyboard Shortcuts (Space or 'm' to speak when not focusing input)
    window.addEventListener('keydown', (e) => {
      if (document.activeElement === DOM.queryInput || document.activeElement === DOM.newTaskInput || document.activeElement === DOM.teachInput) {
        return;
      }
      if (e.key === 'm' || e.key === 'M') {
        e.preventDefault();
        toggleListening();
      }
    });
  }

  // ── Utilities ──────────────────────────────────────────────────────────────
  function escapeHTML(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function formatTime() {
    const now = new Date();
    return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  // ── Bootstrapping ──────────────────────────────────────────────────────────
  function init() {
    applyTheme(state.theme);
    if (DOM.voiceSpeakToggle) {
      DOM.voiceSpeakToggle.classList.toggle('active', state.voiceEnabled);
    }
    setupEventListeners();
    loadTasks();
    loadMemory();
    setState('standby');
  }

  // Start on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
