"use strict";
const ADVANCED_URL="https://www.scopus.com/pages/search/publications?type=advanced";
const el=id=>document.getElementById(id);
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const norm=t=>String(t||"").replace(/\s+/g,"").toUpperCase();
const log=(msg,warn=false)=>{
  const line=document.createElement("div");
  line.textContent="["+new Date().toLocaleTimeString()+"] "+msg;
  line.style.color=warn?"#a03e18":"inherit";
  el("progress").append(line);
  line.scrollIntoView({block:"nearest"});
};
let job=null, folder=null, tabId=null, busy=false;

function database(){
  return new Promise((resolve,reject)=>{
    const open=indexedDB.open("PanScopus_Companion",1);
    open.onupgradeneeded=()=>open.result.createObjectStore("prefs");
    open.onsuccess=()=>resolve(open.result);
    open.onerror=()=>reject(open.error);
  });
}
async function preference(key,value){
  const db=await database();
  return new Promise((resolve,reject)=>{
    const tr=db.transaction("prefs",value===undefined?"readonly":"readwrite");
    const store=tr.objectStore("prefs");
    const req=value===undefined?store.get(key):store.put(value,key);
    req.onsuccess=()=>resolve(req.result);
    req.onerror=()=>reject(req.error);
    tr.oncomplete=()=>db.close();
  });
}
async function folderAllowed(){
  return !!folder && (await folder.queryPermission({mode:"read"}))==="granted";
}
function buttons(){
  el("folder").textContent=folder?.name||"Not selected";
  el("start").disabled=!job||!folder||busy;
}
async function page(action,arg=null){
  const results=await chrome.scripting.executeScript({
    target:{tabId},func:scopusDOM,args:[action,arg]
  });
  return results[0]?.result;
}
function scopusDOM(op,arg){
  const vis=e=>{
    if(!e)return false;
    const r=e.getBoundingClientRect(),s=getComputedStyle(e);
    return r.width>0&&r.height>0&&s.visibility!=="hidden"&&s.display!=="none";
  };
  const list=sel=>[...document.querySelectorAll(sel)].filter(vis);
  const label=e=>(e?.innerText||e?.getAttribute?.("aria-label")||"").trim();
  const click=e=>{if(!e)return false;e.scrollIntoView({block:"center"});e.click();return true;};
  const body=document.body?.innerText||"";
  const root=()=>list(".monaco-editor")[0];
  const editorText=()=>{
    const r=root();if(!r)return "";
    const e=r.querySelector(".native-edit-context");
    if(typeof e?.editContext?.text==="string")return e.editContext.text;
    return [...r.querySelectorAll(".view-line")].map(x=>x.textContent||"").join("");
  };
  const modal=()=>{
    const pat=/\bExport\s+[\d,]+\s+documents?\s+to\s+CSV\b/i;
    const m=list('[role="dialog"],dialog,[aria-modal="true"]')
      .find(e=>pat.test(e.innerText||"")&&/select all information/i.test(e.innerText||""));
    if(m)return m;
    const heading=list("h1,h2,h3,h4,span,div")
      .filter(e=>pat.test(label(e))&&label(e).length<90)
      .sort((a,b)=>label(a).length-label(b).length)[0];
    for(let p=heading?.parentElement;p&&p!==document.body;p=p.parentElement){
      if(pat.test(p.innerText||"")&&/select all information/i.test(p.innerText||""))return p;
    }
    return null;
  };
  const modalCount=()=>{
    const match=(modal()?.innerText||"").match(/\bExport\s+([\d,]+)\s+documents?\s+to\s+CSV\b/i);
    return match?Number(match[1].replace(/,/g,"")):null;
  };
  if(op==="state"){
    const c=body.match(/\b([\d,]+)\s+documents?\s+found\b/i);
    return {
      title:document.title,url:location.href,
      blocked:/attention required|cloudflare/i.test(document.title)||
        /sorry, you have been blocked/i.test(body),
      editor:!!root(),searchId:/[?&]searchid=/i.test(location.search),
      queryVisible:/advanced query/i.test(body),
      count:c?Number(c[1].replace(/,/g,"")):null
    };
  }
  if(op==="focusEditor"){
    const r=root();if(!r)return {ok:false};
    const e=r.querySelector('.native-edit-context,textarea.inputarea,[role="textbox"]')||
      r.querySelector(".view-line")||r;
    e.focus();e.click();
    return {ok:r.contains(document.activeElement)};
  }
  if(op==="editorText")return editorText();
  if(op==="pressSearch"){
    const r=root();if(!r)return {ok:false};
    const rect=r.getBoundingClientRect();
    const choices=list("button").filter(e=>label(e)==="Search"&&!e.disabled);
    choices.sort((a,b)=>{
      const score=e=>{const p=e.getBoundingClientRect();return Math.abs(p.y-rect.bottom)+Math.abs(p.x-rect.left)/4;};
      return score(a)-score(b);
    });
    return {ok:click(choices[0])};
  }
  if(op==="selectAll"){
    const e=document.querySelector("#selectAllCheck")||
      document.querySelector('label[for="selectAllCheck"]')||
      list('[role="checkbox"]').find(e=>/all/i.test(e.getAttribute("aria-label")||""));
    if(!e)return {ok:false};
    const target=e.matches("label")?document.getElementById(e.htmlFor):e;
    const checked=target?.matches('input[type="checkbox"]')?target.checked:
      target?.getAttribute("aria-checked")==="true";
    if(!checked)click(e);return {ok:true};
  }
  if(op==="openCsv"){
    if(modalCount()!==null)return "dialog";
    const csv=list('button,a,[role="menuitem"],[role="option"],span,div')
      .filter(e=>label(e)==="CSV")
      .sort((a,b)=>a.getBoundingClientRect().width*a.getBoundingClientRect().height-
        b.getBoundingClientRect().width*b.getBoundingClientRect().height)[0];
    if(csv){click(csv);return "csv";}
    const e=document.querySelector("#exportBtn,#export_Menu")||
      list("button,a,[role=button]").find(e=>label(e)==="Export");
    if(e){click(e);return "menu";}
    return "missing";
  }
  if(op==="dialogCount")return modalCount();
  if(op==="rangeOption"){
    const m=modal();if(!m)return {ok:false};
    const title=[...m.querySelectorAll("*")].find(e=>label(e)==="What information do you want to export?");
    const top=title?.getBoundingClientRect().top??Infinity;
    const options=[...m.querySelectorAll('label,[role="radio"],button,span,div')]
      .filter(vis).filter(e=>label(e)==="Documents")
      .filter(e=>e.getBoundingClientRect().top<top)
      .sort((a,b)=>a.getBoundingClientRect().width*a.getBoundingClientRect().height-
        b.getBoundingClientRect().width*b.getBoundingClientRect().height);
    const choice=options[0];
    return {ok:click(choice?.closest('label,[role="radio"],button')||choice)};
  }
  if(op==="focusTo"){
    const m=modal();if(!m)return {ok:false};
    const inputs=[...m.querySelectorAll("input")].filter(vis)
      .filter(e=>!["hidden","checkbox","radio"].includes((e.type||"").toLowerCase()));
    const desc=e=>[e.id,e.name,e.placeholder,e.getAttribute("aria-label")].join(" ").toLowerCase();
    let target=inputs.find(e=>/\bto\b|range.?end/.test(desc(e)));
    if(!target){
      const title=[...m.querySelectorAll("*")].find(e=>label(e)==="What information do you want to export?");
      const before=inputs.filter(e=>e.getBoundingClientRect().top<(title?.getBoundingClientRect().top??Infinity));
      before.sort((a,b)=>a.getBoundingClientRect().left-b.getBoundingClientRect().left);
      target=before[before.length-1];
    }
    if(!target)return {ok:false};
    target.focus();target.click();
    return {ok:document.activeElement===target};
  }
  if(op==="selectMetadata"){
    const m=modal();if(!m)return {ok:false};
    const checks=[...m.querySelectorAll('input[type="checkbox"],[role="checkbox"]')];
    const checked=checks.filter(e=>e.matches("input")?e.checked:
      e.getAttribute("aria-checked")==="true"||e.getAttribute("data-state")==="checked").length;
    const options=[...m.querySelectorAll('a,button,label,[role="button"],span,div')]
      .filter(vis).filter(e=>label(e)==="Select all information")
      .sort((a,b)=>a.getBoundingClientRect().width*a.getBoundingClientRect().height-
        b.getBoundingClientRect().width*b.getBoundingClientRect().height);
    if(!options.length)return {ok:false};
    if(checked<Math.max(5,checks.length-1))click(options[0].closest("a,button,label,[role=button]")||options[0]);
    return {ok:true};
  }
  if(op==="metadataStatus"){
    const m=modal();if(!m)return null;
    const checks=[...m.querySelectorAll('input[type="checkbox"],[role="checkbox"]')];
    return {
      total:checks.length,
      checked:checks.filter(e=>e.matches("input")?e.checked:
        e.getAttribute("aria-checked")==="true"||e.getAttribute("data-state")==="checked").length,
      count:modalCount()
    };
  }
  if(op==="submit"){
    const m=modal();
    if(!m||modalCount()!==arg)return {ok:false};
    const choices=[...m.querySelectorAll("button")].filter(vis)
      .filter(e=>label(e)==="Export"&&!e.disabled&&e.getAttribute("aria-disabled")!=="true")
      .sort((a,b)=>b.getBoundingClientRect().top-a.getBoundingClientRect().top);
    return {ok:click(choices[0])};
  }
  return null;
}
async function until(check,ms,description){
  const end=Date.now()+ms;let last=null;
  while(Date.now()<end){
    try{const result=await check();if(result)return result;}
    catch(e){last=e;}
    await sleep(650);
  }
  throw new Error(description+" timed out"+(last?": "+last.message:""));
}
async function state(){
  const s=await page("state");
  if(s?.blocked)throw new Error("Scopus access challenge detected in this browser; Companion cannot bypass it.");
  return s;
}
async function typeNative(value){
  const target={tabId};
  try{await chrome.debugger.attach(target,"1.3");}
  catch(e){throw new Error("Unable to type through Chrome. Close DevTools on Scopus and check Companion permissions: "+e.message);}
  const cmd=(name,args)=>chrome.debugger.sendCommand(target,name,args);
  try{
    await cmd("Input.dispatchKeyEvent",{type:"rawKeyDown",key:"Control",code:"ControlLeft",windowsVirtualKeyCode:17,modifiers:2});
    await cmd("Input.dispatchKeyEvent",{type:"rawKeyDown",key:"a",code:"KeyA",windowsVirtualKeyCode:65,modifiers:2});
    await cmd("Input.dispatchKeyEvent",{type:"keyUp",key:"a",code:"KeyA",windowsVirtualKeyCode:65,modifiers:2});
    await cmd("Input.dispatchKeyEvent",{type:"keyUp",key:"Control",code:"ControlLeft",windowsVirtualKeyCode:17,modifiers:0});
    await cmd("Input.insertText",{text:String(value)});
  }finally{
    try{await chrome.debugger.detach(target);}catch(_){}
  }
}
async function performSearch(){
  log("Opening authorized Scopus browser tab…");
  const tabs=await chrome.tabs.query({url:["https://www.scopus.com/*"]});
  const existing=tabs.find(t=>!/Cloudflare|Attention Required/i.test(t.title||""))||tabs[0];
  if(existing){tabId=existing.id;await chrome.tabs.update(tabId,{url:ADVANCED_URL,active:true});}
  else{tabId=(await chrome.tabs.create({url:ADVANCED_URL,active:true})).id;}
  await until(async()=>(await state())?.editor,65000,"Scopus Advanced Search editor");
  const focused=await page("focusEditor");
  if(!focused?.ok)throw new Error("Monaco editor cannot be focused");
  await typeNative(job.query);
  await until(async()=>norm(await page("editorText"))===norm(job.query),12000,"Exact query verification");
  log("Exact advanced query entered and verified.");
  if(!(await page("pressSearch"))?.ok)throw new Error("Scopus Search button not found");
  log("Search submitted; waiting for matching documents…");
  const results=await until(async()=>{
    const r=await state();
    return r?.searchId&&r?.queryVisible&&Number.isInteger(r.count)?r:null;
  },110000,"Scopus results");
  if(results.count<=0||results.count>2000)
    throw new Error("Search document count is outside export range: "+results.count);
  log("Scopus search verified: "+results.count+" documents.");
  return results.count;
}
async function prepareCsv(total){
  log("Opening CSV export, selecting all documents…");
  if(!(await page("selectAll"))?.ok)throw new Error("Select all documents unavailable");
  await until(async()=>{
    const result=await page("openCsv");
    return result==="dialog"||result==="csv";
  },20000,"CSV selection menu");
  let count=await until(async()=>{
    const n=await page("dialogCount");return Number.isInteger(n)?n:null;
  },25000,"CSV export dialog");
  log("CSV dialog: "+count+" documents");
  if(count!==total){
    if(!(await page("rangeOption"))?.ok)throw new Error("Full document range selector missing");
    await until(async()=>(await page("focusTo"))?.ok,10000,"CSV To field");
    await typeNative(String(total));
    await until(async()=>(await page("dialogCount"))===total,15000,"CSV full range");
    count=await page("dialogCount");
  }
  if(count!==total)throw new Error("Refusing partial CSV export: "+count+"/"+total);
  if(!(await page("selectMetadata"))?.ok)throw new Error("Select all CSV metadata missing");
  const meta=await until(async()=>{
    const m=await page("metadataStatus");
    return m?.count===total&&m.checked>=Math.max(5,m.total-1)?m:null;
  },10000,"CSV metadata confirmation");
  log("Document range and metadata verified: "+count+" docs, "+meta.checked+"/"+meta.total+" fields.");
}
function watchCsv(tab,ms=180000){
  let downloadId=null,done=false,resolve,reject;
  const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});
  const stop=()=>{clearTimeout(timer);chrome.downloads.onCreated.removeListener(onCreated);chrome.downloads.onChanged.removeListener(onChanged);};
  const finish=(err,item)=>{if(done)return;done=true;stop();err?reject(err):resolve(item);};
  const timer=setTimeout(()=>finish(new Error("CSV download did not finish within 3 minutes")),ms);
  function onCreated(item){
    if(item.tabId===tab&&/scopus|elsevier/i.test(String(item.url||"")+" "+String(item.finalUrl||"")))
      downloadId=item.id;
  }
  async function onChanged(delta){
    if(downloadId!==delta.id||delta.state?.current!=="complete")return;
    try{
      const item=(await chrome.downloads.search({id:downloadId}))[0];
      if(!item||!/\.csv$/i.test(item.filename||""))finish(new Error("Downloaded file was not CSV"));
      else finish(null,item);
    }catch(e){finish(e);}
  }
  chrome.downloads.onCreated.addListener(onCreated);
  chrome.downloads.onChanged.addListener(onChanged);
  return {promise,cancel:stop};
}
function countCSV(csv){
  let quote=false,nonempty=false,n=0;
  for(let i=0;i<csv.length;i++){
    const c=csv[i];
    if(c==='"'){
      if(quote&&csv[i+1]==='"'){i++;continue;}
      quote=!quote;
    }else if(!quote&&c==="\n"){
      if(nonempty)n++;
      nonempty=false;
    }else if(c!=="\r")nonempty=true;
  }
  if(quote)throw new Error("CSV quote structure incomplete");
  if(nonempty)n++;
  return Math.max(0,n-1);
}
async function transferCsv(item,total){
  if(!await folderAllowed())throw new Error("Chrome download folder access is not authorized.");
  const name=String(item.filename||"").split(/[\\/]/).pop();
  const file=await (await folder.getFileHandle(name)).getFile();
  if(file.size>20000000)throw new Error("Downloaded file too large for automatic import (20 MB limit).");
  const csv=await file.text(), rows=countCSV(csv);
  if(rows!==total)throw new Error("Downloaded CSV row count "+rows+" differs from Scopus "+total+". Import prevented.");
  log("Downloaded CSV verified: "+rows+"/"+total+" records.");
  const panTab=await chrome.tabs.get(job.appTabId);
  if(panTab.url!==job.appUrl)throw new Error("PanScopus tab changed; upload was blocked.");
  const response=await chrome.tabs.sendMessage(job.appTabId,{
    type:"PANSCOPUS_IMPORT_CSV",appUrl:job.appUrl,name,text:csv
  });
  if(!response?.ok)throw new Error(response?.error||"PanScopus uploader rejected the file.");
  await chrome.tabs.update(job.appTabId,{active:true});
  log("CSV delivered to PanScopus Cloud importer. Verify its displayed count.");
}
async function run(){
  if(busy)return;busy=true;el("start").disabled=true;el("retry").hidden=true;
  el("progress").textContent="";
  try{
    if(!job)throw new Error("No PanScopus job. Start from the Streamlit app.");
    if(!await folderAllowed())throw new Error("Choose and authorize your Chrome downloads folder.");
    const total=await performSearch();
    await prepareCsv(total);
    const watcher=watchCsv(tabId);
    try{
      if(!(await page("submit",total))?.ok)throw new Error("Final CSV Export could not be clicked safely.");
      log("Waiting for CSV download to finish…");
      const downloaded=await watcher.promise;
      log("CSV download completed.");
      await transferCsv(downloaded,total);
      log("PanScopus Companion finished successfully.");
    }catch(e){watcher.cancel();throw e;}
  }catch(e){
    log("Stopped: "+String(e.message||e),true);
    log("Access restrictions will not be bypassed; no repeated login or export loop.",true);
    el("retry").hidden=false;
  }finally{busy=false;buttons();}
}
async function init(){
  job=(await chrome.storage.session.get("panscopusJob")).panscopusJob||null;
  if(!job){el("query").textContent="No job was started in PanScopus.";return;}
  el("query").textContent=job.query;
  try{folder=await preference("downloadDirectory");}catch(e){log("Saved download folder unavailable.",true);}
  if(folder&&!await folderAllowed())log("Saved folder permission expired; select again.",true);
  buttons();
}
el("choose").addEventListener("click",async()=>{
  try{
    folder=await window.showDirectoryPicker({id:"panscopus-exports",mode:"read",startIn:"downloads"});
    if(!await folderAllowed()){
      if(await folder.requestPermission({mode:"read"})!=="granted")
        throw new Error("Folder read permission not granted.");
    }
    await preference("downloadDirectory",folder);
    buttons();log("Chrome download folder selected.");
  }catch(e){log("Folder setup: "+String(e.message||e),true);}
});
el("start").addEventListener("click",run);
el("retry").addEventListener("click",run);
init().catch(e=>log("Initialization error: "+String(e.message||e),true));
