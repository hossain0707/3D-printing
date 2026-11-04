import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFExporter } from "three/addons/exporters/GLTFExporter.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import JSZip from "https://esm.sh/jszip@3.10.1";

const $ = (selector) => document.querySelector(selector);
const state = {
  style: "classic", hair: "short", pose: "wave", size: 80, inscription: "",
  skin: "#dca77c", hairColor: "#31221f", topColor: "#ed6c69", bottomColor: "#637da8",
  seed: 7, version: 1, approved: null, faceRatio: 1, eyeSpacing: 1,
  photoAnalyzed: false, detection: "none"
};
let displayedModel = null;
const stages = [];
const isReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const colorMaterial = (hex, roughness = .77) => new THREE.MeshStandardMaterial({ color: hex, roughness, metalness: .02 });
const makeSphere = (group, name, hex, pos, size, segments = 32) => {
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(1, segments, Math.floor(segments * .7)), colorMaterial(hex));
  mesh.name = name;
  mesh.position.set(...pos);
  mesh.scale.set(...size);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  group.add(mesh);
  return mesh;
};
const makeCylinder = (group, name, hex, r1, r2, height, pos) => {
  const mesh = new THREE.Mesh(new THREE.CylinderGeometry(r1, r2, height, 48), colorMaterial(hex));
  mesh.name = name;
  mesh.position.set(...pos);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  group.add(mesh);
  return mesh;
};
const darker = (hex, factor) => {
  const c = new THREE.Color(hex).multiplyScalar(factor);
  return "#" + c.getHexString();
};
function seeded(seed) { let a = seed + 101; return () => { a = (1664525 * a + 1013904223) >>> 0; return a / 4294967296; }; }
function createFigure(cfg) {
  const rand = seeded(cfg.seed);
  const figure = new THREE.Group();
  figure.name = "MINIMO-print-candidate";
  const skin = cfg.skin, hair = cfg.hairColor, shirt = cfg.topColor, pants = cfg.bottomColor;
  const faceWidth = Math.min(1.1, Math.max(.92, cfg.faceRatio));
  const dream = cfg.style === "dreamy", collector = cfg.style === "collector";
  const base = collector ? "#f7d7a5" : dream ? "#dec9ed" : "#f4e7d7";

  makeCylinder(figure, "display-base", base, 1.85, 1.95, .35, [0,.18,0]);
  makeCylinder(figure, "base-inset", darker(base,.94), 1.6, 1.7, .055, [0,.39,0]);
  // Rounded legs, shoes and body. All components are closed meshes.
  for (const side of [-1,1]) {
    makeSphere(figure, "trouser-leg", pants, [side*.49,.95,0], [.39,.72,.43]);
    makeSphere(figure, "shoe", collector ? "#fff3dc" : "#e9e0d5", [side*.49,.48,.28], [.47,.32,.64]);
  }
  makeSphere(figure, "torso-shirt", shirt, [0,2.38,0], [.94,1.18,.68]);
  makeSphere(figure, "collar", "#fff3e7", [0,3.28,.5], [.40,.17,.20]);
  const leftArm = cfg.pose === "hug" ? [-.84,2.55,.59] : [-1.04,2.34,.04];
  const rightArm = cfg.pose === "wave" ? [1.13,3.1,.02] : cfg.pose === "hug" ? [.84,2.55,.59] : [1.04,2.34,.04];
  const left = makeSphere(figure, "left-sleeve", shirt, leftArm, [.35,.72,.40]);
  left.rotation.z = cfg.pose === "hug" ? -.7 : -.2;
  const right = makeSphere(figure, "right-sleeve", shirt, rightArm, [.35,.72,.40]);
  right.rotation.z = cfg.pose === "wave" ? -.72 : cfg.pose === "hug" ? .7 : .2;
  makeSphere(figure, "left-hand", skin, cfg.pose === "hug" ? [-.43,2.4,.90] : [-1.12,1.81,.08], [.30,.31,.30]);
  makeSphere(figure, "right-hand", skin, cfg.pose === "wave" ? [1.66,3.48,.07] : cfg.pose === "hug" ? [.43,2.4,.90] : [1.12,1.81,.08], [.30,.31,.30]);
  if(cfg.pose==="hug") makeSphere(figure,"heart", "#e86b79",[0,2.5,1.05],[.33,.34,.19]);

  // Oversized distinctive chibi head, deliberately stylized rather than photorealistic.
  const face = makeSphere(figure, "face-head", skin, [0,4.65,.08], [1.44*faceWidth,1.48,1.20]);
  makeSphere(figure, "left-ear", skin, [-1.40*faceWidth,4.48,.06],[.26,.34,.20]);
  makeSphere(figure, "right-ear", skin, [1.40*faceWidth,4.48,.06],[.26,.34,.20]);
  const depth = 1.13;
  makeSphere(figure, "left-eye", "#252124",[-.51*cfg.eyeSpacing,4.78,depth],[.20,.25,.10],24);
  makeSphere(figure, "right-eye", "#252124",[.51*cfg.eyeSpacing,4.78,depth],[.20,.25,.10],24);
  makeSphere(figure, "left-eye-glint", "#fffaf6",[-.56*cfg.eyeSpacing,4.86,1.215],[.065,.075,.035],16);
  makeSphere(figure, "right-eye-glint", "#fffaf6",[.46*cfg.eyeSpacing,4.86,1.215],[.065,.075,.035],16);
  makeSphere(figure, "nose", darker(skin,.89),[0,4.48,1.26],[.085,.085,.063],16);
  makeSphere(figure, "smile", "#713a46",[0,4.18,1.205],[.19,dream?.065:.095,.06],24);
  makeSphere(figure, "left-blush", dream?"#e99bad":"#eea6a0",[-.84,4.36,1.00],[.25,.10,.06],20);
  makeSphere(figure, "right-blush", dream?"#e99bad":"#eea6a0",[.84,4.36,1.00],[.25,.10,.06],20);

  const backHeight = cfg.hair === "long" ? 1.93 : cfg.hair === "medium" ? 1.58 : 1.20;
  makeSphere(figure, "hair-back", hair, [0,4.97,-.52], [1.48*faceWidth,backHeight,.89]);
  makeSphere(figure, "hair-top", hair, [0,5.69,.0],[1.43*faceWidth,.83,1.16]);
  if (cfg.hair === "long" || cfg.hair === "medium") {
    for(const side of [-1,1]){
      makeSphere(figure,"side-lock",hair,[side*1.23,4.50,-.02],[.35,cfg.hair==="long"?1.62:1.07,.56]);
    }
  }
  if (cfg.hair === "bun") {
    makeSphere(figure,"bun",hair,[.78,6.22,-.10],[.54,.53,.49]);
  }
  for(let i=0;i<5;i++){
    const x = -1.03+i*.51, y = 5.58 - rand()*.20, z=1.00+rand()*.06;
    const strand=makeSphere(figure,"rounded-fringe",hair,[x,y,z],[.29,.39+rand()*.14,.20],20);
    strand.rotation.z=(2-i)*.14;
  }
  if(collector) {
    makeSphere(figure,"star-accent","#f8e6a3",[1.17,5.42,1.09],[.19,.18,.10],16);
  }
  // Name is stored in manifest rather than as tiny fragile printable text.
  figure.userData = { version:cfg.version, sizeMM:cfg.size, pose:cfg.pose, style:cfg.style };
  return figure;
}
function setupStage(selector, decorative) {
  const host=$(selector);
  if(!host)return null;
  const renderer=new THREE.WebGLRenderer({alpha:true,antialias:true,preserveDrawingBuffer:true,powerPreference:"low-power"});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));
  renderer.outputColorSpace=THREE.SRGBColorSpace;
  renderer.toneMapping=THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure=1.35;
  host.appendChild(renderer.domElement);
  const scene=new THREE.Scene();
  const camera=new THREE.PerspectiveCamera(35,1,.1,100);
  camera.position.set(9,7,15);
  camera.lookAt(0,3.4,0);
  scene.add(new THREE.HemisphereLight(0xffffff,0xa87970,3.3));
  const key=new THREE.DirectionalLight(0xffffff,3.3);key.position.set(-5,10,9);scene.add(key);
  const rim=new THREE.DirectionalLight(0xffffff,2.0);rim.position.set(7,5,-8);scene.add(rim);
  const controls=new OrbitControls(camera,renderer.domElement);
  controls.enablePan=false;controls.enableDamping=true;controls.minDistance=10;controls.maxDistance=30;
  controls.target.set(0,3.5,0); controls.autoRotate=decorative&&!isReducedMotion; controls.autoRotateSpeed=1.25;
  const current=createFigure(state);
  scene.add(current);
  const stage={host,renderer,scene,camera,controls,model:current};
  stages.push(stage);
  const resize=()=>{
    const w=Math.max(1,host.clientWidth),h=Math.max(1,host.clientHeight);
    renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();
  };
  new ResizeObserver(resize).observe(host);resize();
  return stage;
}
const studio=setupStage("#studio-canvas",false);
const hero=setupStage("#hero-canvas",true);
displayedModel=studio.model;
function disposeModel(model){
  if(!model)return;
  model.traverse(o=>{if(o.isMesh){o.geometry.dispose(); if(o.material)o.material.dispose();}});
}
function redraw(){
  for(const stage of stages){
    stage.scene.remove(stage.model);disposeModel(stage.model);
    stage.model=createFigure(state);stage.scene.add(stage.model);
  }
  displayedModel=studio.model;
  $("#version-label").textContent="VERSION "+String(state.version).padStart(2,"0");
  $("#estimate").textContent="₩"+({50:39000,80:59000,100:79000}[state.size]||59000).toLocaleString("ko-KR");
}
function animate(){
  requestAnimationFrame(animate);
  stages.forEach(stage=>{stage.controls.update();stage.renderer.render(stage.scene,stage.camera);});
}
animate();
function toast(message){
  const el=$("#toast");
  el.textContent=message;el.classList.add("show");
  clearTimeout(toast.timer);toast.timer=setTimeout(()=>el.classList.remove("show"),4000);
}
function markDirty(){
  remote.versionId = null; remote.approved = false; remote.serial++;
  state.version++;
  state.approved=null;
  $("#approval-info").hidden=true;
  $("#export").disabled=true;
  redraw();
}
document.querySelectorAll(".style-choice").forEach(button=>button.addEventListener("click",()=>{
  document.querySelectorAll(".style-choice").forEach(item=>item.classList.remove("selected"));
  button.classList.add("selected");state.style=button.dataset.style;markDirty();
}));
for(const [id,key] of [["#hair","hair"],["#pose","pose"],["#size","size"],["#inscription","inscription"],["#skin","skin"],["#hair-color","hairColor"],["#top-color","topColor"],["#bottom-color","bottomColor"]]){
  $(id).addEventListener(id==="#inscription"?"change":"input",(ev)=>{
    state[key]=key==="size"?Number(ev.target.value):ev.target.value;
    markDirty();
  });
}
$("#regenerate").addEventListener("click",()=>{
  if(remote.busy){toast("Python generation is processing; finish this job first.");return;}
  state.seed+=7+Math.floor(Math.random()*999);
  markDirty();toast("New look generated · review before approving");
  if(remote.base && latestPhotoFile) runPythonGeneration().catch(err=>toast(err.message));
});
$("#approve").addEventListener("click",async()=>{
  if(remote.busy){toast("Please finish the current generation first.");return;}
  if(remote.base && latestPhotoFile && !remote.versionId){
    toast("Generate and review your Python 3D model before approving.");return;
  }
  if(remote.base && remote.versionId){
    try{
      const endpoint="/api/v1/projects/"+remote.projectId+"/versions/"+remote.versionId+"/approve";
      await pythonFetch(endpoint,{method:"POST"});
      remote.approved=true;
    }catch(error){toast("Server approval failed: "+error.message);return;}
  }
  state.approved={...state,approved:null, approvedAt:new Date().toISOString(),orderToken:crypto.randomUUID?.()||String(Date.now())};
  $("#approval-info").hidden=false;
  $("#approval-detail").textContent="Version "+state.version+" · "+state.size+" mm · ready for operator inspection";
  $("#export").disabled=false;
  toast("Design approved. You can now download the production package.");
});

function rgbToHex(r,g,b){return "#"+[r,g,b].map(v=>Math.max(0,Math.min(255,Math.round(v))).toString(16).padStart(2,"0")).join("");}
function samplePatch(data,w,h,rx,ry,sx,sy){
  let r=0,g=0,b=0,count=0;
  const x0=Math.max(0,Math.floor((rx-sx)*w)),x1=Math.min(w,Math.ceil((rx+sx)*w));
  const y0=Math.max(0,Math.floor((ry-sy)*h)),y1=Math.min(h,Math.ceil((ry+sy)*h));
  for(let y=y0;y<y1;y+=2)for(let x=x0;x<x1;x+=2){
    const k=(y*w+x)*4,red=data[k],green=data[k+1],blue=data[k+2];
    const max=Math.max(red,green,blue),min=Math.min(red,green,blue);
    if(max>247||max<24||(max-min<5&&max>225))continue;
    r+=red;g+=green;b+=blue;count++;
  }
  return count>4?rgbToHex(r/count,g/count,b/count):null;
}
function relative(faceLandmarks,ids,axis){
  const pts=ids.map(i=>faceLandmarks[i]);
  return pts.reduce((acc,p)=>acc+p[axis],0)/pts.length;
}
async function detectFace(img){
  try{
    const vision=await import("https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.21/+esm");
    const mp=vision.default&&vision.default.FaceLandmarker?vision.default:vision;
    const resolver=await mp.FilesetResolver.forVisionTasks("https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.21/wasm");
    const detector=await mp.FaceLandmarker.createFromOptions(resolver,{
      baseOptions:{modelAssetPath:"https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",delegate:"CPU"},
      runningMode:"IMAGE",numFaces:1
    });
    const result=detector.detect(img);detector.close();
    return result.faceLandmarks?.[0]||null;
  }catch(err){console.warn("Face landmarks optional fallback:",err);return null;}
}
async function analyzePhoto(file){
  latestPhotoFile=file;
  remote.projectId=null;remote.token=null;remote.versionId=null;remote.approved=false;
  if(!["image/jpeg","image/png","image/webp"].includes(file.type))throw Error("Please upload JPG, PNG or WEBP.");
  if(file.size>8*1024*1024)throw Error("Photo must be 8 MB or smaller.");
  const url=URL.createObjectURL(file);
  let img;
  try{img=await new Promise((resolve,reject)=>{
    const node=new Image();node.onload=()=>resolve(node);node.onerror=reject;node.src=url;
  });}catch(err){URL.revokeObjectURL(url);throw Error("Could not read that image.");}
  const thumb=$("#photo-thumb");thumb.src=url;thumb.hidden=false;$("#photo-placeholder").hidden=true;
  const status=$("#analysis-status");status.textContent="Matching photo colors and attempting local AI landmarks…";
  const c=document.createElement("canvas"); const factor=Math.min(1,800/Math.max(img.naturalWidth,img.naturalHeight));
  c.width=Math.max(1,Math.round(img.naturalWidth*factor));c.height=Math.max(1,Math.round(img.naturalHeight*factor));
  const ctx=c.getContext("2d",{willReadFrequently:true});ctx.drawImage(img,0,0,c.width,c.height);
  const pixel=ctx.getImageData(0,0,c.width,c.height).data;
  const faces=await detectFace(img);
  let sx=.5,sy=.25, hairY=.10, topY=.65,bottomY=.83;
  if(faces){
    sx=relative(faces,[1,4,6],"x");
    sy=relative(faces,[1,4,6],"y");
    const forehead=relative(faces,[10,151,9],"y");
    const chin=faces[152].y;
    hairY=Math.max(.025,forehead-(chin-forehead)*.19);
    topY=Math.min(.96,chin+(chin-forehead)*.65);
    bottomY=Math.min(.97,topY+.25);
    const eyeSep=Math.abs(faces[33].x-faces[263].x);
    state.eyeSpacing=Math.min(1.12,Math.max(.9,eyeSep/.26));
    const width=Math.abs(faces[234].x-faces[454].x);
    state.faceRatio=Math.min(1.07,Math.max(.94,width/.39));
  }
  const skin=samplePatch(pixel,c.width,c.height,sx,sy,.045,.045);
  const hair=samplePatch(pixel,c.width,c.height,sx,hairY,.13,.025);
  const top=samplePatch(pixel,c.width,c.height,.5,topY,.14,.055);
  const bottom=samplePatch(pixel,c.width,c.height,.5,bottomY,.11,.045);
  if(skin)state.skin=skin;
  if(hair)state.hairColor=hair;
  if(top)state.topColor=top;
  if(bottom)state.bottomColor=bottom;
  for(const [id,key] of [["#skin","skin"],["#hair-color","hairColor"],["#top-color","topColor"],["#bottom-color","bottomColor"]])$(id).value=state[key];
  state.detection=faces?"AI face landmarks + sampled colors":"Sampled colors only (AI unavailable/no face)";
  state.photoAnalyzed=true;
  status.innerHTML="";
  const dot=document.createElement("span");dot.className="status-indicator";status.append(dot,document.createTextNode(state.detection+" · review and adjust"));
  markDirty();
  toast("Photo analyzed locally. Please check colors and likeness.");
}
const photoInput=$("#photo-input");
photoInput.addEventListener("change",e=>{const f=e.target.files?.[0];if(f)analyzePhoto(f).catch(err=>toast(err.message));});
const dropzone=$("#dropzone");
dropzone.addEventListener("dragover",e=>{e.preventDefault();dropzone.classList.add("dragging");});
dropzone.addEventListener("dragleave",()=>dropzone.classList.remove("dragging"));
dropzone.addEventListener("drop",e=>{e.preventDefault();dropzone.classList.remove("dragging");const f=e.dataTransfer.files?.[0];if(f)analyzePhoto(f).catch(err=>toast(err.message));});

// The vendor-neutral print package exports UV-mapped, textured OBJ files and a matching GLB.
// Models are PRINT CANDIDATES: component shells may overlap and still need boolean union and
// thin-feature, surface-quality and color proofing against the selected printer's requirements.
function makeSolidPNG(hex){
  const c=document.createElement("canvas");c.width=c.height=32;
  const x=c.getContext("2d");x.fillStyle=hex;x.fillRect(0,0,32,32);
  return c.toDataURL("image/png").split(",")[1];
}
function objPackage(group,sizeMM){
  group.updateMatrixWorld(true);
  const bounds=new THREE.Box3().setFromObject(group),height=bounds.max.y-bounds.min.y;
  const scale=sizeMM/height;
  const offsetX=(bounds.min.x+bounds.max.x)/2,offsetZ=(bounds.min.z+bounds.max.z)/2;
  const objects=["# MINIMO print candidate | millimetres | Y up"],materials=["# MTL generated by MINIMO"],textures=new Map();
  let index=1;
  const number=(n)=>Number(n.toFixed(5));
  const vertex=new THREE.Vector3();
  group.traverse(mesh=>{
    if(!mesh.isMesh)return;
    const original=mesh.geometry;
    const geo=original.index?original.toNonIndexed():original;
    const pos=geo.getAttribute("position"),uv=geo.getAttribute("uv");
    const color="#"+mesh.material.color.getHexString();
    const key="color_"+color.slice(1);
    if(!textures.has(key)){
      textures.set(key,{color,file:key+".png"});
      materials.push("newmtl "+key,"Kd 1.000 1.000 1.000","Ka 0.000 0.000 0.000","Ks 0.000 0.000 0.000","d 1.0","map_Kd "+key+".png","");
    }
    objects.push("o "+mesh.name.replace(/[^a-zA-Z0-9_-]/g,"_"),"usemtl "+key);
    for(let i=0;i<pos.count;i++){
      vertex.fromBufferAttribute(pos,i).applyMatrix4(mesh.matrixWorld);
      objects.push("v "+number((vertex.x-offsetX)*scale)+" "+number((vertex.y-bounds.min.y)*scale)+" "+number((vertex.z-offsetZ)*scale));
    }
    for(let i=0;i<pos.count;i++)objects.push("vt "+(uv?number(uv.getX(i)):.5)+" "+(uv?number(uv.getY(i)):.5));
    for(let i=0;i<pos.count;i+=3){
      objects.push("f "+(index+i)+"/"+(index+i)+" "+(index+i+1)+"/"+(index+i+1)+" "+(index+i+2)+"/"+(index+i+2));
    }
    index+=pos.count;
    if(geo!==original)geo.dispose();
  });
  objects.splice(1,0,"mtllib miniature.mtl");
  return {obj:objects.join("\n")+"\n",mtl:materials.join("\n")+"\n",textures,scale,heightMM:height*scale};
}
async function glbExport(group){
  return new Promise((resolve,reject)=>new GLTFExporter().parse(group,resolve,reject,{binary:true,onlyVisible:true}));
}
$("#export").addEventListener("click",async()=>{
  if(!state.approved){toast("Approve the current design first.");return;}
  if(remote.base && remote.versionId && remote.approved){
    const button=$("#export");button.disabled=true;button.textContent="Downloading approved Python package…";
    try{
      const response=await pythonFetch("/api/v1/projects/"+remote.projectId+
        "/versions/"+remote.versionId+"/package");
      const blob=await response.blob(),url=URL.createObjectURL(blob);
      const a=document.createElement("a");a.href=url;
      a.download="minimo-python-approved-"+state.size+"mm.zip";document.body.append(a);a.click();a.remove();
      setTimeout(()=>URL.revokeObjectURL(url),20000);
      toast("Server-created print candidate downloaded. Supplier validation is still mandatory.");
    }catch(err){toast("Download failed: "+err.message);}
    finally{button.disabled=false;button.textContent="Download production package ↓";}
    return;
  }
  const button=$("#export");button.disabled=true;button.textContent="Preparing 3D print candidate…";
  try{
    const zip=new JSZip();
    const approved=state.approved;
    const {obj,mtl,textures,heightMM}=objPackage(displayedModel,approved.size);
    const glb=await glbExport(displayedModel);
    zip.file("preview/approved-character.glb",glb);
    zip.file("print-candidate/miniature.obj",obj);
    zip.file("print-candidate/miniature.mtl",mtl);
    textures.forEach((v)=>zip.file("print-candidate/"+v.file,makeSolidPNG(v.color),{base64:true}));
    zip.file("ORDER-MANIFEST.json",JSON.stringify({
      project:"MINIMO Studio",id:approved.orderToken,approvedAt:approved.approvedAt,
      version:approved.version,sizeMM:approved.size,style:approved.style,pose:approved.pose,
      hair:approved.hair,baseInscription:approved.inscription,colors:{
        skin:approved.skin,hair:approved.hairColor,top:approved.topColor,bottom:approved.bottomColor
      },photoAnalyzed:approved.photoAnalyzed,photoAnalysisMethod:approved.detection,
      physicalPrintApproval:"NOT VERIFIED",paymentStatus:"NOT COLLECTED",
      note:"This package is a PRINT CANDIDATE, not automatically manufacturable. Inspect and repair meshes and obtain full-color supplier approval."
    },null,2));
    zip.file("READ-BEFORE-PRINTING.txt","MINIMO STUDIO — PRODUCTION HANDOFF\n\n1. This is a proposed character, not a finished certified printable model.\n2. Review likeness with customer and verify approved version.\n3. Inspect OBJ mesh for intersecting shells, non-manifold boundaries and tiny parts. Perform union/remesh as required.\n4. Verify minimum wall thickness, base stability and scale in mm (Y up).\n5. Verify textures with supplier: OBJ + MTL + individual PNG images. GLB is for digital preview.\n6. Obtain supplier approval and a physical full-color sample before commercial orders.\n7. Do not use unlicensed trademarks or third-party characters.\n8. No customer image or address is included in this ZIP.\n");
    const blob=await zip.generateAsync({type:"blob",compression:"DEFLATE",compressionOptions:{level:5}});
    const url=URL.createObjectURL(blob),a=document.createElement("a");
    a.href=url;a.download="minimo-approved-v"+approved.version+"-"+approved.size+"mm.zip";document.body.append(a);a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),15000);
    toast("Manufacturing candidate downloaded. Operator and printer validation still required.");
  }catch(e){console.error(e);toast("Export failed: "+e.message);}
  finally{button.disabled=!state.approved;button.textContent="Download production package ↓";}
});


// The Python processing service is an optional, independently deployed API.
// The hosted Vercel website remains a functional LOCAL DESIGN DEMO when it is unavailable.
const remote={
  base:String(window.MINIMO_API_URL||"").trim().replace(/\/$/,""),
  projectId:null,token:null,versionId:null,approved:false,busy:false,serial:0
};
let latestPhotoFile=null;
const pythonPanel=$("#python-panel"),pythonButton=$("#python-generate"),pythonState=$("#python-state");
if(!remote.base){
  pythonPanel.hidden=true;
}else{
  pythonPanel.hidden=false;
  pythonState.textContent="Checking secure Python generator…";
  fetch(remote.base+"/api/v1/health",{cache:"no-store"})
    .then(r=>r.ok?r.json():Promise.reject(Error("Service unavailable")))
    .then(data=>{pythonState.textContent=data.generation_enabled?
      "Python CPU generator ready":"Python generator not accepting public jobs";})
    .catch(()=>{pythonState.textContent="Backend offline. Local preview remains available.";});
  pythonButton.addEventListener("click",()=>runPythonGeneration().catch(error=>toast(error.message)));
}
async function pythonFetch(path,init={}){
  if(!remote.base)throw Error("Python backend is not configured");
  const headers={...(init.headers||{})};
  if(remote.token)headers["X-Project-Token"]=remote.token;
  const response=await fetch(remote.base+path,{...init,headers,cache:"no-store"});
  if(!response.ok){
    let msg="HTTP "+response.status;
    try{const data=await response.json();msg=typeof data.detail==="string"?data.detail:msg;}catch{}
    throw Error(msg);
  }
  return response;
}
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function runPythonGeneration(){
  if(remote.busy){toast("A generation is already running.");return;}
  if(!latestPhotoFile){toast("Upload a photograph before starting Python generation.");return;}
  remote.busy=true;pythonButton.disabled=true;
  const serial=++remote.serial;
  try{
    if(!remote.projectId){
      pythonState.textContent="Uploading privately to your configured Python service…";
      const payload=new FormData();payload.append("photo",latestPhotoFile,latestPhotoFile.name);
      const response=await pythonFetch("/api/v1/projects",{method:"POST",body:payload});
      const project=await response.json();
      remote.projectId=project.project_id;remote.token=project.project_token;
    }
    pythonState.textContent="Queued for Python CPU generation…";
    const payload={
      style:state.style,hair:state.hair,pose:state.pose,size_mm:state.size,seed:state.seed,
      inscription:state.inscription,colors:{
        skin:state.skin,hair:state.hairColor,top:state.topColor,bottom:state.bottomColor
      }
    };
    const id=remote.projectId;
    const submit=await pythonFetch("/api/v1/projects/"+id+"/generate",{
      method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)
    });
    const {job_id,version_id}=await submit.json();
    let done=false;
    for(let i=0;i<60;i++){
      if(serial!==remote.serial)throw Error("The design changed while processing; regenerate again.");
      await pause(1500);
      const response=await pythonFetch("/api/v1/projects/"+id+"/jobs/"+job_id);
      const job=await response.json();
      pythonState.textContent="Python worker: "+job.status+" · design version "+state.version;
      if(job.status==="failed")throw Error(job.error||"Generation failed");
      if(job.status==="completed"){done=true;break;}
    }
    if(!done)throw Error("Python worker did not finish. Check worker status before retrying.");
    const preview=await pythonFetch("/api/v1/projects/"+id+"/versions/"+version_id+"/preview");
    const glb=await preview.arrayBuffer();
    const gltf=await new Promise((resolve,reject)=>new GLTFLoader().parse(glb,"",resolve,reject));
    if(serial!==remote.serial)throw Error("The design changed before preview arrived.");
    const model=gltf.scene;
    let bounds=new THREE.Box3().setFromObject(model);
    const modelHeight=bounds.max.y-bounds.min.y;
    if(!(modelHeight>0))throw Error("Backend returned an invalid 3D model.");
    model.scale.setScalar(6.55/modelHeight);
    bounds=new THREE.Box3().setFromObject(model);
    model.position.y-=bounds.min.y;
    studio.scene.remove(studio.model);disposeModel(studio.model);
    studio.model=model;studio.scene.add(model);displayedModel=model;
    remote.versionId=version_id;remote.approved=false;
    state.approved=null;$("#approval-info").hidden=true;$("#export").disabled=true;
    $("#version-label").textContent="PYTHON · VERSION "+String(state.version).padStart(2,"0");
    pythonState.textContent="Python 3D preview ready · rotate, review and approve";
    toast("Python-generated 3D preview is ready. Review before approval.");
  }finally{
    remote.busy=false;pythonButton.disabled=false;
  }
}

if("IntersectionObserver" in window){
  const io=new IntersectionObserver(entries=>entries.forEach(entry=>{
    if(entry.isIntersecting){entry.target.classList.add("visible");io.unobserve(entry.target);}
  }),{threshold:.08});
  document.querySelectorAll(".reveal").forEach(el=>io.observe(el));
}else document.querySelectorAll(".reveal").forEach(el=>el.classList.add("visible"));
