"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const path=require("node:path");
const source=fs.readFileSync(path.join(__dirname,"..","chrome_companion","query_reader.js"),"utf8");

const QUERY='TITLE-ABS-KEY(("green synthesis" OR "plant-mediated" OR phytogenic) AND nanoparticle* AND antibiotic* AND (synerg* OR potentiation OR combination) AND (MDR OR "multidrug resistant" OR MRSA OR ESBL))';

function mockDoc({textareas=[],codes=[],body="",title="PanScopus",headings=["PanScopus"]}={}) {
  return {
    title,
    body:{innerText:body},
    getElementById(){return null;},
    querySelector(){return null;},
    querySelectorAll(selector) {
      if(selector==="h1,h2")
        return headings.map(textContent=>({textContent}));
      if(selector==="textarea")
        return textareas.map(value=>({
          value,textContent:"",id:"",
          getAttribute(name) {return name==="aria-label"?"Scopus advanced query":"";},
          closest(){return null;}
        }));
      if(selector.includes("stCodeBlock")||selector.includes("pre"))
        return codes.map(textContent=>({textContent}));
      return [];
    }
  };
}
function evaluate(doc) {
  return vm.runInNewContext(source,{
    document:doc,
    CSS:{escape:s=>s}
  });
}
const typed=evaluate(mockDoc({textareas:[QUERY]}));
assert.equal(typed.query,QUERY);
assert.equal(typed.source,"textarea");
const fallback=evaluate(mockDoc({codes:[QUERY]}));
assert.equal(fallback.query,QUERY);
assert.equal(fallback.source,"code block");
const nested=evaluate(mockDoc({body:"PanScopus\nAdvanced query\n"+QUERY+"\nInstall Companion"}));
assert.equal(nested.query,QUERY);
assert.equal(nested.source,"visible query text");
const absent=evaluate(mockDoc({title:"Random Streamlit App",headings:[],codes:[QUERY]}));
assert.equal(absent.query,"");
const empty=evaluate(mockDoc({textareas:[""],codes:[]}));
assert.equal(empty.query,"");
console.log("Chrome Companion query reader: 5 offline cases passed");
