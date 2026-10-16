"use strict";
const start=document.getElementById("start");
const status=document.getElementById("status");

start.addEventListener("click",async()=>{
  start.disabled=true;
  status.textContent="Reading the PanScopus query from all Streamlit frames…";
  try {
    const [tab]=(await chrome.tabs.query({active:true,currentWindow:true}));
    if(!tab?.id || !/^https:\/\/(?:[a-z0-9-]+\.streamlit\.app|share\.streamlit\.io)\//i.test(tab.url||""))
      throw new Error("Open your PanScopus Streamlit Cloud tab first.");

    // Inject a deterministic reader in every permitted Streamlit frame.
    // Do not assume that the query input is a textarea in the main frame.
    const results=await chrome.scripting.executeScript({
      target:{tabId:tab.id,allFrames:true},
      files:["query_reader.js"]
    });
    const candidates=results.map(row=>row.result).filter(Boolean);
    const located=results.find(row=>row.result?.app&&row.result?.query);
    const found=located?.result;
    if(!found){
      const diagnostics=candidates.map(x=>
        "app="+!!x.app+" textarea="+(x.editors||0)+
        " code="+(x.codeBlocks||0)+" source="+String(x.source||"")
      ).join("; ");
      throw new Error(
        "PanScopus query could not be read from Streamlit "+
        "("+results.length+" frame(s); "+diagnostics+"). "+
        "The query is visible in the app, so this is a Companion detection error."
      );
    }
    const reply=await chrome.runtime.sendMessage({
      type:"PANSCOPUS_START",appTabId:tab.id,
      appFrameId:located.frameId,query:found.query
    });
    if(!reply?.ok)throw new Error(reply?.error||"Runner did not open");
    status.textContent="Found query in "+found.source+
      ". Companion runner opened in another tab.";
  }catch(error){
    status.textContent="Cannot start: "+String(error.message||error);
  }finally{start.disabled=false;}
});
