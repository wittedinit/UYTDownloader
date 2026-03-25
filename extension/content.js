// UYTDownloader Content Script — adds "Send to UYT" button on YouTube pages

(function () {
  "use strict";

  let buttonInjected = false;

  function getServerUrl() {
    return new Promise((resolve) => {
      chrome.storage.sync.get(["serverUrl"], (result) => {
        resolve(result.serverUrl || "http://localhost:3000");
      });
    });
  }

  function createButton() {
    if (buttonInjected || document.getElementById("uyt-send-btn")) return;

    const btn = document.createElement("button");
    btn.id = "uyt-send-btn";
    btn.title = "Send to UYTDownloader";
    btn.innerHTML = `
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
      </svg>
      <span>UYT</span>
    `;

    btn.addEventListener("click", async (e) => {
      e.preventDefault();
      e.stopPropagation();

      const url = window.location.href;
      const serverUrl = await getServerUrl();
      const apiBase = serverUrl.replace(/:3000/, ":8000");

      btn.classList.add("uyt-loading");
      btn.querySelector("span").textContent = "Sending...";

      try {
        const res = await fetch(`${apiBase}/api/probe`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url }),
        });

        if (res.ok) {
          btn.classList.remove("uyt-loading");
          btn.classList.add("uyt-success");
          btn.querySelector("span").textContent = "Sent!";
          // Open UYTDownloader
          window.open(`${serverUrl}?url=${encodeURIComponent(url)}`, "_blank");
          setTimeout(() => {
            btn.classList.remove("uyt-success");
            btn.querySelector("span").textContent = "UYT";
          }, 3000);
        } else {
          throw new Error("Failed");
        }
      } catch {
        btn.classList.remove("uyt-loading");
        btn.classList.add("uyt-error");
        btn.querySelector("span").textContent = "Error";
        setTimeout(() => {
          btn.classList.remove("uyt-error");
          btn.querySelector("span").textContent = "UYT";
        }, 3000);
      }
    });

    // Insert near YouTube's action buttons
    const insertPoint =
      document.querySelector("#top-level-buttons-computed") ||
      document.querySelector("#menu-container") ||
      document.querySelector("#actions");

    if (insertPoint) {
      insertPoint.appendChild(btn);
      buttonInjected = true;
    }
  }

  // YouTube is an SPA — watch for navigation
  const observer = new MutationObserver(() => {
    if (window.location.pathname === "/watch" || window.location.pathname.startsWith("/playlist") || window.location.pathname.startsWith("/@")) {
      buttonInjected = false;
      setTimeout(createButton, 1000);
    }
  });

  observer.observe(document.body, { childList: true, subtree: true });

  // Initial injection
  if (document.readyState === "complete") {
    setTimeout(createButton, 1500);
  } else {
    window.addEventListener("load", () => setTimeout(createButton, 1500));
  }
})();
