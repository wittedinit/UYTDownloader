// UYTDownloader Browser Extension — Popup Script

const serverUrlInput = document.getElementById("serverUrl");
const sendBtn = document.getElementById("sendBtn");
const openBtn = document.getElementById("openBtn");
const statusEl = document.getElementById("status");
const urlInfo = document.getElementById("urlInfo");
const urlPreview = document.getElementById("urlPreview");

let currentUrl = "";

// Load saved server URL
chrome.storage.sync.get(["serverUrl"], (result) => {
  serverUrlInput.value = result.serverUrl || "http://localhost:3000";
});

// Save server URL on change
serverUrlInput.addEventListener("change", () => {
  const url = serverUrlInput.value.replace(/\/+$/, "");
  serverUrlInput.value = url;
  chrome.storage.sync.set({ serverUrl: url });
});

// Get current tab URL
chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
  if (tabs[0] && tabs[0].url) {
    currentUrl = tabs[0].url;
    if (isYouTubeUrl(currentUrl)) {
      urlInfo.style.display = "block";
      urlPreview.textContent = currentUrl;
      sendBtn.disabled = false;
    } else {
      showStatus("Navigate to a YouTube page to send it", "info");
      sendBtn.disabled = true;
    }
  }
});

function isYouTubeUrl(url) {
  return /^https?:\/\/(www\.)?youtube\.com\/(watch|playlist|channel|@|c\/|shorts)/.test(url);
}

function showStatus(msg, type) {
  statusEl.textContent = msg;
  statusEl.className = "status " + type;
}

// Send to UYTDownloader
sendBtn.addEventListener("click", async () => {
  if (!currentUrl || !isYouTubeUrl(currentUrl)) return;

  const serverUrl = serverUrlInput.value.replace(/\/+$/, "");
  if (!serverUrl) {
    showStatus("Please enter your server URL", "error");
    return;
  }

  sendBtn.disabled = true;
  sendBtn.textContent = "Sending...";
  showStatus("Connecting to UYTDownloader...", "info");

  try {
    // First check server is reachable
    const healthRes = await fetch(`${serverUrl.replace(/:3000/, ":8000")}/health`, {
      method: "GET",
      signal: AbortSignal.timeout(5000),
    });
    if (!healthRes.ok) throw new Error("Server not reachable");

    // Submit probe request
    const apiBase = serverUrl.replace(/:3000/, ":8000");
    const probeRes = await fetch(`${apiBase}/api/probe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: currentUrl }),
    });

    if (!probeRes.ok) {
      const err = await probeRes.text();
      throw new Error(err || "Probe request failed");
    }

    const data = await probeRes.json();
    showStatus(`Sent! Probe started (ID: ${data.probe_id?.slice(0, 8)}...)`, "success");

    // Open UYTDownloader in a new tab with the URL pre-filled
    chrome.tabs.create({ url: `${serverUrl}?url=${encodeURIComponent(currentUrl)}` });
  } catch (e) {
    showStatus(e.message || "Failed to connect", "error");
  } finally {
    sendBtn.disabled = false;
    sendBtn.textContent = "Send to UYTDownloader";
  }
});

// Open UYTDownloader
openBtn.addEventListener("click", () => {
  const serverUrl = serverUrlInput.value.replace(/\/+$/, "");
  if (serverUrl) {
    chrome.tabs.create({ url: serverUrl });
  }
});
