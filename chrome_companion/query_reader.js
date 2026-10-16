"use strict";
/*
 * Streamlit can render input text inside a textarea, a code block, or a
 * different frame (e.g. a share.streamlit.io embed). This reader runs entirely
 * in the PanScopus tab. It never reads cookies, password inputs or Secrets.
 */
(function () {
  function balancedQuery(text) {
    const raw=String(text||"");
    const found=/\b(?:TITLE-ABS-KEY|TITLE|ABS|KEY|AUTH|DOI|SRCTITLE|INDEXTERMS|AFFIL|PUBYEAR)\s*\(/i.exec(raw);
    if(!found)return "";
    const start=found.index;
    const open=raw.indexOf("(",start);
    let level=0,quoted=false;
    for(let i=open;i<raw.length;i++){
      const ch=raw[i];
      if(ch==='"' && raw[i-1]!=="\\") quoted=!quoted;
      if(quoted)continue;
      if(ch==="(")level++;
      if(ch===")"){
        level--;
        if(level===0)return raw.slice(start,i+1).trim();
      }
    }
    return "";
  }

  function read(doc) {
    const title=String(doc.title||"");
    const headings=[...doc.querySelectorAll("h1,h2")];
    const nameVisible=headings.some(h=>/\bPanScopus\b/i.test(h.textContent||""));
    const app=/(?:pan.?scopus)/i.test(title)||nameVisible;
    const editors=[...doc.querySelectorAll("textarea")];
    const labelOf=e=>[
      e.getAttribute("aria-label")||"",
      e.getAttribute("placeholder")||"",
      doc.getElementById(e.getAttribute("aria-labelledby")||"")?.textContent||"",
      e.id?doc.querySelector('label[for="'+CSS.escape(e.id)+'"]')?.textContent||"":"",
      e.closest('[data-testid="stTextArea"]')?.textContent?.slice(0,140)||""
    ].join(" ").toLowerCase();
    const ranked=editors.map(e=>{
      const v=String(e.value||e.textContent||"").trim();
      const label=labelOf(e);
      let weight=0;
      if(/scopus.*(advanced|query)|(advanced|query).*scopus/i.test(label))weight+=100;
      if(/\badvanced query\b/.test(label))weight+=40;
      if(/^[\s]*(?:TITLE-ABS-KEY|TITLE|ABS|KEY|AUTH|DOI|SRCTITLE|INDEXTERMS|AFFIL|PUBYEAR)\s*\(/i.test(v))weight+=60;
      if(v.length>5)weight+=10;
      return {value:v,weight};
    }).filter(x=>x.value);
    ranked.sort((a,b)=>b.weight-a.weight);
    const preferred=ranked.find(x=>x.weight>=60);
    if(preferred&&app)return {query:preferred.value,source:"textarea",app:true,editors:editors.length};

    // Always prefer the query displayed by the PanScopus "Browser-only fallback"
    // st.code() block over any activity log or developer instructions.
    const blocks=[...doc.querySelectorAll(
      '[data-testid="stCodeBlock"] code,[data-testid="stCodeBlock"] pre,pre code,pre'
    )].map(e=>String(e.textContent||"").trim()).filter(Boolean);
    for(const block of blocks){
      const query=balancedQuery(block);
      if(query&&app)return {query,source:"code block",app:true,editors:editors.length};
    }

    // Some Streamlit releases change stCodeBlock wrappers. Read only a
    // syntactically balanced advanced query from visible page text.
    const body=String(doc.body?.innerText||"");
    const fromBody=balancedQuery(body);
    if(fromBody&&app)return {query:fromBody,source:"visible query text",app:true,editors:editors.length};
    return {query:"",source:"not detected",app,editors:editors.length,
      codeBlocks:blocks.length};
  }
  // The same file is loaded by the content script and can be executed from the
  // Chrome extension popup with chrome.scripting.executeScript({files:...}).
  globalThis.panScopusReadQuery=read;
  return read(document);
})();
