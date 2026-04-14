/* ══════════════════════════════════════════════════
   LANGUAGE CONFIG  (4 languages with flag + TTS code)
══════════════════════════════════════════════════ */
const LANG_CONFIG = {
    'en': { name: 'English',     voice: 'en-US', flag: '🇺🇸' },
    'hi': { name: 'Hindi',       voice: 'hi-IN', flag: '🇮🇳' },
    'bn': { name: 'Bangla',      voice: 'bn-IN', flag: '🇧🇩' },
    'or': { name: 'Odia',        voice: 'or-IN', flag: '🇮🇳' },
};

/* ══════════════════════════════════════════════════
   APPLICATION STATE
══════════════════════════════════════════════════ */
let lastKnownText   = "";
let autoSpeakEnabled = false;
let currentLang      = "none";
let lastSpokenWord   = "";
let wordCountTotal   = 0;
let translationTimer = null;
let cameraActive     = false;

/* ══════════════════════════════════════════════════
   INIT
══════════════════════════════════════════════════ */
function initApp() {
    loadTheme();
    loadAutoSpeak();
    loadQuickLang();
    startSessionTimer();

    const output = document.getElementById("output");
    if (output) lastKnownText = output.innerText || "";
}

/* ══════════════════════════════════════════════════
   THEME
══════════════════════════════════════════════════ */
function loadTheme() {
    const theme = localStorage.getItem("theme") ||
        (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");

    document.body.classList.toggle("dark-mode", theme === "dark");
    updateThemeIcon(theme === "dark");

    // sync settings page
    const sel = document.getElementById("themeSelect");
    if (sel) sel.value = theme;

    const langSel = document.getElementById("languageSelect");
    if (langSel) langSel.value = localStorage.getItem("speakLanguage") || "en";
}

function updateThemeIcon(isDark) {
    const icon = document.getElementById("themeIcon");
    if (icon) icon.textContent = isDark ? "light_mode" : "dark_mode";
}

function toggleTheme() {
    const isDark = document.body.classList.toggle("dark-mode");
    localStorage.setItem("theme", isDark ? "dark" : "light");
    updateThemeIcon(isDark);
    showToast(isDark ? "🌙 Dark mode on" : "☀️ Light mode on", "info");
}

function saveSettings() {
    const themeSelect = document.getElementById("themeSelect");
    const langSelect  = document.getElementById("languageSelect");
    if (themeSelect) localStorage.setItem("theme", themeSelect.value);
    if (langSelect)  localStorage.setItem("speakLanguage", langSelect.value);
    loadTheme();
    showToast("✅ Settings saved!", "success");
}

/* ══════════════════════════════════════════════════
   SESSION TIMER
══════════════════════════════════════════════════ */
let sessionStart = null;
function startSessionTimer() {
    sessionStart = Date.now();
    setInterval(() => {
        const el = document.getElementById("sessionTimer");
        if (!el) return;
        const s = Math.floor((Date.now() - sessionStart) / 1000);
        el.textContent = `${String(Math.floor(s / 60)).padStart(2,"0")}:${String(s % 60).padStart(2,"0")}`;
    }, 1000);
}

/* ══════════════════════════════════════════════════
   QUICK LANGUAGE SWITCHER
══════════════════════════════════════════════════ */
function loadQuickLang() {
    const sel = document.getElementById("quickLangSelect");
    if (!sel) return;
    currentLang = localStorage.getItem("quickLang") || "none";
    sel.value = currentLang;
    updateTranslationPanel();
}

function onQuickLangChange() {
    const sel = document.getElementById("quickLangSelect");
    if (!sel) return;
    currentLang = sel.value;
    localStorage.setItem("quickLang", currentLang);
    updateTranslationPanel();

    if (currentLang !== "none") {
        const cfg = LANG_CONFIG[currentLang];
        showToast(`${cfg ? cfg.flag + " " + cfg.name : currentLang} translation enabled`, "info");
        // Translate current text immediately
        const out = document.getElementById("output");
        if (out && out.innerText.trim()) scheduleTranslation(out.innerText);
    } else {
        showToast("Translation disabled", "info");
    }
}

function updateTranslationPanel() {
    const panel = document.getElementById("translationPanel");
    const label = document.getElementById("translationLangLabel");
    if (!panel) return;

    if (currentLang && currentLang !== "none") {
        panel.style.display = "flex";
        panel.style.flexDirection = "column";
        const cfg = LANG_CONFIG[currentLang];
        if (label && cfg) label.textContent = cfg.flag + " " + cfg.name;
    } else {
        panel.style.display = "none";
    }
}

/* ══════════════════════════════════════════════════
   CAMERA CONTROLS
══════════════════════════════════════════════════ */
function startCam() {
    const cam         = document.getElementById("camera");
    const loader      = document.getElementById("cameraLoader");
    const placeholder = document.getElementById("cameraPlaceholder");
    const liveBadge   = document.getElementById("liveBadge");
    const scanLine    = document.getElementById("scanLine");

    if (!cam) return;
    if (loader)      loader.style.display = "flex";
    if (placeholder) placeholder.style.display = "none";
    cam.style.display = "none";

    cam.onload = function () {
        if (loader)    loader.style.display = "none";
        cam.style.display = "block";
        cam.onload = null;
        if (liveBadge) liveBadge.classList.add("active");
        if (scanLine)  scanLine.classList.add("active");
        cameraActive = true;
        showToast("🎥 Camera active — start signing!", "success");
    };
    cam.src = "/video";
}

function stopCam() {
    fetch("/stop_camera");
    const cam         = document.getElementById("camera");
    const loader      = document.getElementById("cameraLoader");
    const placeholder = document.getElementById("cameraPlaceholder");
    const liveBadge   = document.getElementById("liveBadge");
    const scanLine    = document.getElementById("scanLine");
    const cameraBox   = document.getElementById("cameraBox");

    if (cam) { cam.src = ""; cam.style.display = "none"; }
    if (loader) loader.style.display = "none";
    if (placeholder) placeholder.style.display = "flex";
    if (liveBadge) liveBadge.classList.remove("active");
    if (scanLine)  scanLine.classList.remove("active");
    if (cameraBox) cameraBox.classList.remove("active");
    cameraActive = false;
    updateConfidenceUI(0, false);
    showToast("⏹ Camera stopped", "warning");
}

/* ══════════════════════════════════════════════════
   TEXT POLLING & AUTO-UPDATE
══════════════════════════════════════════════════ */
function autoUpdateText() {
    fetch("/get_text")
        .then(r => r.json())
        .then(data => {
            const output = document.getElementById("output");
            if (!output) return;
            const newText = data.text || "";

            if (newText === lastKnownText) return;

            if (!newText.startsWith(lastKnownText) || lastKnownText === "") {
                // Full reset
                output.innerHTML = newText.trim()
                    ? `<span class="fade-in-word">${newText}</span>`
                    : "";
            } else {
                // Append only the new portion
                const diff = newText.substring(lastKnownText.length);
                if (diff.trim()) {
                    output.insertAdjacentHTML("beforeend",
                        `<span class="fade-in-word">${diff}</span>`);

                    // Get last new word
                    const newWord = diff.trim().split(/\s+/).filter(Boolean).pop();
                    if (newWord) {
                        updateWordSpotlight(newWord);
                        spawnParticles();

                        if (autoSpeakEnabled && newWord !== lastSpokenWord) {
                            speakWordInline(newWord);
                            lastSpokenWord = newWord;
                        }
                    }
                }
            }
            lastKnownText = newText;
            output.scrollTop = output.scrollHeight;

            // Update word count
            const words = newText.trim() ? newText.trim().split(/\s+/) : [];
            wordCountTotal = words.length;
            updateWordCountDisplay();

            // Live translation
            if (currentLang !== "none" && newText.trim()) {
                scheduleTranslation(newText);
            }
        })
        .catch(() => {});
}

function updateWordCountDisplay() {
    const badge = document.getElementById("wordCountBadge");
    const stat  = document.getElementById("wordCountStat");
    const label = `${wordCountTotal} word${wordCountTotal !== 1 ? "s" : ""}`;
    if (badge) badge.textContent = label;
    if (stat)  stat.textContent  = wordCountTotal;
}

/* ══════════════════════════════════════════════════
   WORD SPOTLIGHT
══════════════════════════════════════════════════ */
function updateWordSpotlight(word) {
    const el = document.getElementById("wordSpotlight");
    if (!el) return;
    el.innerHTML = `<span class="spotlight-word pop-in">${word}</span>`;
}

/* ══════════════════════════════════════════════════
   CONFIDENCE POLLING
══════════════════════════════════════════════════ */
function pollConfidence() {
    if (!cameraActive) return;
    fetch("/confidence")
        .then(r => r.json())
        .then(d => updateConfidenceUI(d.confidence || 0, true))
        .catch(() => {});
}

function updateConfidenceUI(value, active) {
    const fill  = document.getElementById("confidenceFill");
    const valEl = document.getElementById("confidenceValue");
    const badge = document.getElementById("confBadgePill");
    const stat  = document.getElementById("confStatValue");

    if (!active || value === 0) {
        if (fill)  { fill.style.width = "0%"; fill.style.background = ""; }
        if (valEl) valEl.textContent = "—";
        if (badge) badge.textContent = "—";
        if (stat)  stat.textContent  = "—";
        return;
    }

    const pct = Math.min(100, Math.max(0, value));
    if (fill) {
        fill.style.width = pct + "%";
        if      (pct >= 80) fill.style.background = "linear-gradient(90deg,#00b09b,#96c93d)";
        else if (pct >= 50) fill.style.background = "linear-gradient(90deg,#f7971e,#ffd200)";
        else                fill.style.background = "linear-gradient(90deg,#f43f5e,#fb7185)";
    }
    const label = pct.toFixed(1) + "%";
    if (valEl) valEl.textContent = label;
    if (badge) badge.textContent = pct.toFixed(0) + "%";
    if (stat)  stat.textContent  = label;
}

/* ══════════════════════════════════════════════════
   LIVE TRANSLATION (MyMemory free API — no key needed)
══════════════════════════════════════════════════ */
function scheduleTranslation(text) {
    clearTimeout(translationTimer);
    translationTimer = setTimeout(() => triggerTranslation(text), 1200);
}

async function triggerTranslation(text) {
    if (!text || !text.trim() || currentLang === "none") return;
    const outEl = document.getElementById("translatedOutput");
    if (!outEl) return;

    outEl.innerHTML = '<span class="translating-text"><span class="material-icons spin-icon">sync</span> Translating...</span>';

    try {
        const url = `https://api.mymemory.translated.net/get?q=${encodeURIComponent(text)}&langpair=en|${currentLang}`;
        const res  = await fetch(url);
        const data = await res.json();
        const translated = data?.responseData?.translatedText;

        if (translated && !translated.toLowerCase().includes("mymemory")) {
            outEl.innerHTML = `<span class="fade-in-word">${translated}</span>`;
        } else {
            outEl.innerHTML = '<span class="error-text">Translation unavailable — try a different language.</span>';
        }
    } catch {
        outEl.innerHTML = '<span class="error-text">⚠️ Translation failed. Check internet connection.</span>';
    }
}

async function speakTranslation() {
    const outEl = document.getElementById("translatedOutput");
    if (!outEl) return;
    const text = outEl.innerText.trim();

    // Guard against placeholder / loading states
    const skipWords = ["Translating", "Translation will", "Translation unavailable",
                       "Translation failed", "⚠️"];
    if (!text || skipWords.some(p => text.startsWith(p))) {
        showToast("No translated text to speak yet", "warning");
        return;
    }

    const cfg = LANG_CONFIG[currentLang] || { voice: "en-US", name: "English", flag: "🗣️" };
    showToast(`🔊 Speaking ${cfg.flag} ${cfg.name}...`, "info");

    // ── Step 1: Always send to backend (pyttsx3) — most reliable cross-language ──
    fetch("/speak_text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text })
    }).catch(() => {});

    // ── Step 2: Try browser Web Speech API with voice matching ──────────────────
    try {
        // Voices load asynchronously; wait up to 1 s for them
        let voices = window.speechSynthesis.getVoices();
        if (voices.length === 0) {
            await new Promise(resolve => {
                const handler = () => resolve();
                window.speechSynthesis.addEventListener("voiceschanged", handler, { once: true });
                setTimeout(resolve, 1000);   // timeout fallback
            });
            voices = window.speechSynthesis.getVoices();
        }

        const langPrefix = cfg.voice.split("-")[0];  // e.g. "bn" from "bn-IN"

        // 3-tier matching: exact BCP-47 → language prefix → any available
        const matchedVoice =
            voices.find(v => v.lang.toLowerCase() === cfg.voice.toLowerCase()) ||
            voices.find(v => v.lang.toLowerCase().startsWith(langPrefix + "-")) ||
            voices.find(v => v.lang.toLowerCase().startsWith(langPrefix));

        const utt = new SpeechSynthesisUtterance(text);
        utt.lang = cfg.voice;
        utt.rate = parseFloat(localStorage.getItem("ttsRate") || "1");
        if (matchedVoice) utt.voice = matchedVoice;

        utt.onerror = (e) => {
            // Only warn if backend also likely failed; otherwise stay quiet
            console.warn("Browser TTS error:", e.error);
        };

        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(utt);
    } catch (e) {
        console.warn("Web Speech API unavailable:", e);
        // Backend TTS is already triggered above — no visible error needed
    }
}

async function copyTranslation() {
    const outEl = document.getElementById("translatedOutput");
    const text  = outEl ? outEl.innerText.trim() : "";
    if (!text || text.startsWith("Translation")) { showToast("Nothing to copy", "warning"); return; }
    navigator.clipboard.writeText(text).then(() => showToast("✓ Translation copied!", "success")).catch(() => showToast("Copy failed", "error"));
}

/* ══════════════════════════════════════════════════
   SPEAK TEXT (full text with optional translation)
   Strategy: Backend pyttsx3 is ALWAYS called first,
   synchronously (before any await), so the user-gesture
   context is never lost. Translation runs async after.
══════════════════════════════════════════════════ */
async function readText() {
    const output = document.getElementById("output");
    if (!output || !output.innerText.trim()) { showToast("Nothing to speak", "warning"); return; }

    const text = output.innerText.trim();
    const targetLang = (currentLang !== "none") ? currentLang :
                       (localStorage.getItem("speakLanguage") || "en");
    const needsTranslation = targetLang && targetLang !== "en" && targetLang !== "none";

    if (!needsTranslation) {
        // ── English: speak immediately, no waiting ──────────────────────────
        _backendSpeak(text);
        showToast("🔊 Speaking...", "success");
        return;
    }

    // ── Non-English: speak original first, then replace with translated ────
    showToast("🔊 Speaking + Translating...", "info");
    _backendSpeak(text);   // speak English NOW while translation loads

    try {
        const url  = `https://api.mymemory.translated.net/get?q=${encodeURIComponent(text)}&langpair=en|${targetLang}`;
        const res  = await fetch(url);
        const data = await res.json();
        const translated = data?.responseData?.translatedText;

        if (translated && !translated.toLowerCase().includes("mymemory")) {
            // Speak the translated version (backend handles unicode correctly)
            _backendSpeak(translated);
            const cfg = LANG_CONFIG[targetLang];
            showToast(`🔊 Also speaking ${cfg ? cfg.flag + " " + cfg.name : targetLang}`, "success");
        }
    } catch { /* translation failed — original English already spoken */ }
}

/** Fire-and-forget call to backend pyttsx3 TTS.
 *  Calling this synchronously (before any await) preserves
 *  the user-gesture context and avoids Chrome autoplay blocks. */
function _backendSpeak(text) {
    fetch("/speak_text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text })
    }).catch(() => {});
}


function speakWordInline(word) {
    const cfg = LANG_CONFIG[currentLang] || { voice: "en-US" };
    const utt = new SpeechSynthesisUtterance(word);
    utt.lang = "en-US";
    utt.rate = 1.1;
    window.speechSynthesis.speak(utt);
}

/* ══════════════════════════════════════════════════
   COPY TO CLIPBOARD
══════════════════════════════════════════════════ */
function copyToClipboard() {
    const output = document.getElementById("output");
    if (!output || !output.innerText.trim()) { showToast("Nothing to copy", "warning"); return; }
    navigator.clipboard.writeText(output.innerText)
        .then(() => showToast("✓ Copied to clipboard!", "success"))
        .catch(() => showToast("Copy failed", "error"));
}

/* ══════════════════════════════════════════════════
   DOWNLOAD TEXT
══════════════════════════════════════════════════ */
function downloadText() {
    const output = document.getElementById("output");
    const text   = output ? output.innerText.trim() : "";
    if (!text) { showToast("Nothing to download", "warning"); return; }
    const blob = new Blob([text], { type: "text/plain" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url;
    a.download = `sign_language_${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    showToast("📥 Downloaded!", "success");
}

/* ══════════════════════════════════════════════════
   SHARE VIA WHATSAPP
══════════════════════════════════════════════════ */
function shareWhatsApp() {
    const output = document.getElementById("output");
    const text   = output ? output.innerText.trim() : "";
    if (!text) { showToast("Nothing to share", "warning"); return; }
    window.open(`https://wa.me/?text=${encodeURIComponent("Sign Language AI detected: " + text)}`, "_blank");
}

/* ══════════════════════════════════════════════════
   AUTO-SPEAK TOGGLE
══════════════════════════════════════════════════ */
function loadAutoSpeak() {
    autoSpeakEnabled = localStorage.getItem("autoSpeak") === "true";
    updateAutoSpeakBtn();
}

function toggleAutoSpeak() {
    autoSpeakEnabled = !autoSpeakEnabled;
    localStorage.setItem("autoSpeak", autoSpeakEnabled);
    updateAutoSpeakBtn();
    showToast(autoSpeakEnabled ? "🔊 Auto-Speak enabled" : "🔇 Auto-Speak disabled",
              autoSpeakEnabled ? "success" : "info");
}

function updateAutoSpeakBtn() {
    const btn = document.getElementById("autoSpeakBtn");
    if (!btn) return;
    if (autoSpeakEnabled) {
        btn.classList.add("active-toggle");
        btn.innerHTML = '<span class="material-icons">hearing</span> Auto ON';
    } else {
        btn.classList.remove("active-toggle");
        btn.innerHTML = '<span class="material-icons">hearing_disabled</span> Auto OFF';
    }
}

/* ══════════════════════════════════════════════════
   CLEAR CONVERSATION
══════════════════════════════════════════════════ */
function newConversation() {
    fetch("/clear_text");
    const output = document.getElementById("output");
    if (output) output.innerHTML = "";
    lastKnownText  = "";
    lastSpokenWord = "";
    wordCountTotal = 0;
    updateWordCountDisplay();
    clearTimeout(translationTimer);

    const spotlight   = document.getElementById("wordSpotlight");
    const translated  = document.getElementById("translatedOutput");
    if (spotlight)  spotlight.innerHTML  = '<span class="spotlight-placeholder">Waiting for gesture...</span>';
    if (translated) translated.innerHTML = '<span class="waiting-text">Translation will appear here...</span>';

    updateConfidenceUI(0, false);
    showToast("🗑 Conversation cleared", "warning");
}

/* ══════════════════════════════════════════════════
   TOAST SYSTEM
══════════════════════════════════════════════════ */
function showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    if (!container) return;

    const ICONS = { success: "check_circle", warning: "warning", error: "error", info: "info" };
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <span class="material-icons toast-icon">${ICONS[type] || "info"}</span>
        <span class="toast-message">${message}</span>`;

    container.appendChild(toast);
    requestAnimationFrame(() => requestAnimationFrame(() => toast.classList.add("show")));

    setTimeout(() => {
        toast.classList.remove("show");
        setTimeout(() => toast.remove(), 450);
    }, 3200);
}

/* ══════════════════════════════════════════════════
   PARTICLE BURST (fires when new word is detected)
══════════════════════════════════════════════════ */
function spawnParticles() {
    const container = document.getElementById("particleContainer");
    const cameraBox = document.getElementById("cameraBox");
    if (!container || !cameraBox) return;

    const rect   = cameraBox.getBoundingClientRect();
    const cx     = rect.left + rect.width  / 2;
    const cy     = rect.top  + rect.height / 2;
    const colors = ["#667eea","#764ba2","#4facfe","#00f2fe","#43e97b","#38f9d7","#fa709a","#ffd200"];
    const COUNT  = 14;

    for (let i = 0; i < COUNT; i++) {
        const p     = document.createElement("div");
        p.className = "particle";
        const angle = (i / COUNT) * 360;
        const dist  = 70 + Math.random() * 80;
        const dx    = Math.cos(angle * Math.PI / 180) * dist;
        const dy    = Math.sin(angle * Math.PI / 180) * dist;

        p.style.cssText = `
            left: ${cx}px; top: ${cy}px;
            background: ${colors[Math.floor(Math.random() * colors.length)]};
            animation-delay: ${(Math.random() * 0.15).toFixed(2)}s;
            width: ${6 + Math.random() * 6}px;
            height: ${6 + Math.random() * 6}px;
        `;
        p.style.setProperty("--dx", `${dx}px`);
        p.style.setProperty("--dy", `${dy}px`);
        container.appendChild(p);
        setTimeout(() => p.remove(), 1000);
    }
}

/* ══════════════════════════════════════════════════
   MAIN POLLING LOOP  (every 500ms)
══════════════════════════════════════════════════ */
setInterval(() => {
    // Poll hand status
    fetch("/hand_status")
        .then(r => r.json())
        .then(data => {
            const camBox    = document.getElementById("cameraBox");
            const handText  = document.getElementById("handStatusText");
            const handIcon  = document.getElementById("handIcon");
            const handChip  = document.getElementById("handStatusChip");

            const active = !!data.hand;
            if (camBox)   camBox.classList.toggle("active", active);
            if (handText) handText.textContent = active ? "Active" : "Idle";
            if (handIcon) handIcon.textContent = active ? "back_hand" : "do_not_touch";
            if (handChip) handChip.classList.toggle("hand-active", active);
        })
        .catch(() => {});

    autoUpdateText();
    pollConfidence();
}, 500);

/* ══════════════════════════════════════════════════
   BOOT
══════════════════════════════════════════════════ */
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initApp);
} else {
    initApp();
}