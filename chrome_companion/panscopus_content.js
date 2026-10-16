"use strict";
(() => {
  const host = location.hostname.toLowerCase();
  if (!(host.endsWith(".streamlit.app") || host === "share.streamlit.io")) return;

  const QUERY_SELECTORS = [
    'textarea[aria-label="Scopus advanced query"]',
    'textarea[aria-label="Advanced Scopus query"]',
    '[data-testid="stTextArea"] textarea'
  ];

  // HTML inserted with st.markdown(unsafe_allow_html=True) can be moved or
  // sanitized by Streamlit. Never rely on that marker being present.
  function currentQueryField() {
    const byLabel = QUERY_SELECTORS.slice(0, 2)
      .map(selector => document.querySelector(selector))
      .find(Boolean);
    if (byLabel) return byLabel;
    const fallback = document.querySelector(QUERY_SELECTORS[2]);
    return fallback && /panscopus/i.test(document.title || "")
      ? fallback : null;
  }
  function queryInfo() {
    return globalThis.panScopusReadQuery?.(document) ||
      {query:"",app:false,source:"query reader missing"};
  }
  function isPanScopus() {
    const data=queryInfo();
    return !!data.app && !!data.query;
  }

  let working = false;
  let nextFrame = 0;
  function ensureButton() {
    if (!isPanScopus()) return;
    const field = currentQueryField();
    const existing = document.getElementById("panscopus-companion-button");
    if (existing && existing.isConnected) return;

    // The Streamlit value may be mirrored only in the rendered st.code panel.
    // In that case insert the Run control next to the code panel itself.
    const code = document.querySelector('[data-testid="stCodeBlock"]') ||
      document.querySelector("pre");
    const anchor = field?.closest('[data-testid="stTextArea"], .stTextArea') ||
      field?.parentElement || code?.closest('[data-testid="stCodeBlock"]') ||
      code || document.querySelector("h1");
    if (!anchor) return;

    const box = document.createElement("div");
    box.id = "panscopus-companion-controls";
    box.style.cssText =
      "margin:12px 0;padding:12px;border:1px solid #aab9cd;" +
      "border-radius:8px;background:transparent;";

    const button = document.createElement("button");
    button.id = "panscopus-companion-button";
    button.type = "button";
    button.textContent = "Run Scopus Search + CSV via Chrome Companion";
    button.style.cssText =
      "padding:12px 18px;background:#1769aa;color:white;border:0;" +
      "border-radius:7px;cursor:pointer;font-weight:600;width:100%;";

    const status = document.createElement("div");
    status.id = "panscopus-companion-note";
    status.style.cssText = "font-size:13px;margin-top:8px;";
    status.textContent =
      "Runs in your authorized Chrome session without a Scopus API.";

    box.append(button, status);
    anchor.insertAdjacentElement("afterend", box);
    button.addEventListener("click", async () => {
      if (working) return;
      const extracted=queryInfo();
      const query=String(extracted.query || "").trim();
      if (!query) {
        status.textContent="Companion could not read the visible query (source: "+
          extracted.source+"). Try the extension toolbar.";
        return;
      }
      working = true;
      button.disabled = true;
      status.textContent = "Opening the Companion runner…";
      try {
        const reply = await chrome.runtime.sendMessage({
          type: "PANSCOPUS_START", query
        });
        if (!reply?.ok) throw new Error(reply?.error || "Companion unavailable");
        status.textContent = "Companion runner opened in another tab.";
      } catch (error) {
        status.textContent = "Companion error: " +
          String(error.message || error);
      } finally {
        working = false;
        button.disabled = false;
      }
    });
  }

  function scheduleEnsure() {
    if (nextFrame) return;
    nextFrame = requestAnimationFrame(() => {
      nextFrame = 0;
      ensureButton();
    });
  }
  scheduleEnsure();
  const observer = new MutationObserver(scheduleEnsure);
  observer.observe(document.documentElement, {
    childList: true, subtree: true
  });

  // The upload can be delivered even if Streamlit omitted the HTML marker.
  chrome.runtime.onMessage.addListener((msg, sender, respond) => {
    if (msg?.type !== "PANSCOPUS_IMPORT_CSV") return;
    try {
      if (!isPanScopus()) throw new Error("Not a PanScopus page");
      if (msg.appUrl !== location.href)
        throw new Error("PanScopus tab URL changed");
      const input = document.querySelector(
        '[data-testid="stFileUploader"] input[type="file"],' +
        'input[type="file"]'
      );
      if (!input) throw new Error("PanScopus CSV uploader not found");
      const name = String(msg.name || "scopus.csv");
      if (!/\.csv$/i.test(name)) throw new Error("Expected a CSV download");
      const csv = String(msg.text || "");
      if (!csv || csv.length > 32000000)
        throw new Error("CSV missing or too large");
      const transfer = new DataTransfer();
      transfer.items.add(new File([csv], name, {type: "text/csv"}));
      input.files = transfer.files;
      input.dispatchEvent(new Event("change", {bubbles: true}));
      respond({ok: true});
    } catch (error) {
      respond({ok: false, error: String(error.message || error)});
    }
  });
})();
