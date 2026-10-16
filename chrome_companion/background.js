"use strict";

const APP_URL_PATTERN = /^https:\/\/(?:[a-z0-9-]+\.streamlit\.app|share\.streamlit\.io)(?::443)?\//i;
const ADVANCED_URL = "https://www.scopus.com/pages/search/publications?type=advanced";

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (!msg || msg.type !== "PANSCOPUS_START") return;
  (async () => {
    const appTab = sender.tab || (Number.isInteger(msg.appTabId)
      ? await chrome.tabs.get(msg.appTabId) : null);
    if (!appTab || !APP_URL_PATTERN.test(appTab.url || "")) {
      throw new Error("Open PanScopus on its Streamlit Cloud tab first.");
    }
    if (!msg.query || !String(msg.query).trim().startsWith("TITLE-ABS-KEY(")) {
      // The workbench supports other advanced syntax too; only forbid an empty query.
      if (!String(msg.query || "").trim()) throw new Error("Enter an advanced Scopus query first.");
    }
    const job = {
      appTabId: appTab.id,
      appFrameId: Number.isInteger(msg.appFrameId) ? msg.appFrameId :
        (Number.isInteger(sender.frameId) ? sender.frameId : 0),
      appUrl: appTab.url,
      query: String(msg.query).trim(),
      created: Date.now(),
      approved: true
    };
    await chrome.storage.session.set({panscopusJob: job});
    await chrome.tabs.create({
      url: chrome.runtime.getURL("runner.html"),
      active: true
    });
    sendResponse({ok:true});
  })().catch(e => sendResponse({ok:false, error:String(e.message || e)}));
  return true;
});
