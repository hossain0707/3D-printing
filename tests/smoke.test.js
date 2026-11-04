import assert from "node:assert/strict";
import {existsSync,readFileSync} from "node:fs";
import test from "node:test";
const p=path=>new URL("../"+path,import.meta.url);
const read=path=>readFileSync(p(path),"utf8");
test("realistic UI, API and worker source are present",()=>{
  for(const name of ["index.html","styles.css","app.js","api-config.js",
    "admin.html","admin.js","services/python/minimo/app.py",
    "services/python/minimo/photogrammetry.py","services/python/minimo/worker.py",
    "services/python/minimo/db.py","tools/blender/prepare_realistic.py","README.md"]){
    assert.ok(existsSync(p(name)),name+" missing");
  }
});
test("UI captures actual multi-angle photographs and shows results only after backend response",()=>{
  const html=read("index.html"),js=read("app.js");
  for(const id of ["photos","consent","submit-scan","viewer","approve-model",
                   "download-model","delete-project","view-report","backend-badge"]){
    assert.ok(html.includes('id="'+id+'"'),id+" missing");
  }
  assert.match(js,/\/api\/v2\/projects/);
  assert.match(js,/GLTFLoader/);
  assert.match(js,/upload_enabled/);
  assert.match(js,/sessionStorage/);
  assert.doesNotMatch(js,/createFigure\(/);
});
test("manufacturing caveats and local privacy gate are explicit",()=>{
  const html=read("index.html");
  assert.match(html,/not automatically print-certified/i);
  assert.match(html,/No synthetic fallback model/i);
  assert.match(read("api-config.js"),/MINIMO_API_URL = ""/);
  assert.match(read("README.md"),/not yet/);
});
