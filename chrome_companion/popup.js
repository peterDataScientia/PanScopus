"use strict";
const start=document.getElementById("start");
const status=document.getElementById("status");

start.addEventListener("click",async()=>{
  start.disabled=true;
  status.textContent="Reading the PanScopus query…";
  try {
    const [tab]=(await chrome.tabs.query({active:true,currentWindow:true}));
    if(!tab?.id || !/^https:\/\/(?:[a-z0-9-]+\.streamlit\.app|share\.streamlit\.io)\//i.test(tab.url||""))
      throw new Error("Open PanScopus Streamlit Cloud first.");
    const result=await chrome.scripting.executeScript({
      target:{tabId:tab.id},
      func:()=>{
        const labels=[
          'textarea[aria-label="Scopus advanced query"]',
          'textarea[aria-label="Advanced Scopus query"]',
          '[data-testid="stTextArea"] textarea'
        ];
        const input=labels.map(s=>document.querySelector(s)).find(Boolean);
        const title=document.title||"";
        const heading=[...document.querySelectorAll("h1,h2")]
          .some(e=>e.textContent?.trim()==="PanScopus");
        if(!(/panscopus/i.test(title)||heading))
          return {error:"This tab is not PanScopus."};
        return {query:String(input?.value||"").trim()};
      }
    });
    const data=result?.[0]?.result;
    if(data?.error)throw new Error(data.error);
    if(!data?.query)throw new Error("Enter a Scopus advanced query in PanScopus first.");
    const reply=await chrome.runtime.sendMessage({
      type:"PANSCOPUS_START",appTabId:tab.id,query:data.query
    });
    if(!reply?.ok)throw new Error(reply?.error||"Runner did not open");
    status.textContent="Companion runner opened in another tab.";
  }catch(error){
    status.textContent="Cannot start: "+String(error.message||error);
  }finally{start.disabled=false;}
});
