import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import test from "node:test";
const read = p=>readFileSync(new URL("../"+p,import.meta.url),"utf8");
test("all static entrypoints exist",()=>{
  for(const name of ["index.html","styles.css","app.js","vercel.json","README.md","docs/ARCHITECTURE.md","docs/PRINTING-QA.md","docs/GO-LIVE.md"]){
    assert.ok(existsSync(new URL("../"+name,import.meta.url)),name+" missing");
  }
});
test("customer upload, approval, regeneration and export controls present",()=>{
  const html=read("index.html");const js=read("app.js");
  for(const id of ["photo-input","studio-canvas","regenerate","approve","export","analysis-status"]){
    assert.ok(html.includes('id="'+id+'"'),id+" missing from markup");
  }
  for(const name of ["createFigure","objPackage","glbExport","analyzePhoto","markDirty","FaceLandmarker"]){
    assert.ok(js.includes(name),name+" missing from implementation");
  }
});
test("privacy and production caveats are disclosed",()=>{
  const html=read("index.html");const docs=read("docs/GO-LIVE.md");
  assert.match(html,/photo is not uploaded|not uploaded|not transmitted/i);
  assert.match(docs,/not a complete transaction service/i);
  assert.match(read("docs/PRINTING-QA.md"),/manufacturing repair/i);
});
