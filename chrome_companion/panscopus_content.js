"use strict";
(() => {
  const marker = "#panscopus-companion";
  const hostname = location.hostname;
  if (!hostname.endsWith(".streamlit.app")) return;
  let working = false;

  function ensureButton() {
    const point = document.querySelector(marker);
    if (!point || document.getElementById("panscopus-companion-button")) return;
    const host = document.createElement("div");
    host.id = "panscopus-companion-controls";
    host.style.cssText = "margin:12px 0;padding:12px;border:1px solid #b0b8c6;border-radius:8px;";
    const btn = document.createElement("button");
    btn.id = "panscopus-companion-button";
    btn.type = "button";
    btn.textContent = "Run Scopus Search + CSV via Chrome Companion";
    btn.style.cssText = "padding:12px 18px;background:#1769aa;color:white;border:0;border-radius:7px;cursor:pointer;font-weight:600;width:100%;";
    const note = document.createElement("div");
    note.id = "panscopus-companion-note";
    note.style.cssText = "font-size:13px;margin-top:8px;";
    note.textContent = "Uses the authorized Chrome session, without Scopus API or server-side headless Chromium.";
    host.append(btn, note);
    point.appendChild(host);
    btn.addEventListener("click", async () => {
      if (working) return;
      const input = document.querySelector('textarea[aria-label="Scopus advanced query"]')
        || document.querySelector(".stTextArea textarea");
      const query = (input?.value || "").trim();
      if (!query) { note.textContent = "Enter the query above before running."; return; }
      working = true;
      btn.disabled = true;
      note.textContent = "Opening the Companion runner…";
      try {
        const response = await chrome.runtime.sendMessage({type:"PANSCOPUS_START", query});
        if (!response?.ok) throw new Error(response?.error || "Cannot open companion");
        note.textContent = "Companion runner opened in a new tab. Keep this PanScopus tab available.";
      } catch (err) {
        note.textContent = "Companion error: " + String(err.message || err);
      } finally {
        working = false;
        btn.disabled = false;
      }
    });
  }
  ensureButton();
  const observer = new MutationObserver(ensureButton);
  observer.observe(document.documentElement, {childList:true,subtree:true});

  chrome.runtime.onMessage.addListener((msg, sender, respond) => {
    if (msg?.type !== "PANSCOPUS_IMPORT_CSV") return;
    try {
      if (!document.querySelector(marker)) throw new Error("PanScopus Companion section missing");
      if (msg.appUrl !== location.href) throw new Error("PanScopus tab URL changed");
      const input = document.querySelector('input[type="file"]');
      if (!input) throw new Error("Open the CSV Import section in PanScopus first");
      const name = String(msg.name || "scopus.csv");
      if (!/\.csv$/i.test(name)) throw new Error("Expected a CSV download");
      const csv = String(msg.text || "");
      if (!csv || csv.length > 32000000) throw new Error("CSV missing or too large");
      const data = new DataTransfer();
      data.items.add(new File([csv], name, {type:"text/csv"}));
      input.files = data.files;
      input.dispatchEvent(new Event("change", {bubbles:true}));
      respond({ok:true});
    } catch (err) {
      respond({ok:false,error:String(err.message || err)});
    }
  });
})();
