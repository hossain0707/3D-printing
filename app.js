import * as THREE from "three";
import {OrbitControls} from "three/addons/controls/OrbitControls.js";
import {GLTFLoader} from "three/addons/loaders/GLTFLoader.js";

const $ = query => document.querySelector(query);
const base=String(window.MINIMO_API_URL||"").trim().replace(/\/+$/,"");
const STORAGE_KEY="minimo-real-session-v2";
let photos=[];
let project=null;
let jobId=null;
let versionId=null;
let working=false;
let viewer=null;
let fileUrls=[];
let pollRun=0;
let processingOnline=false;
const currentUrl=()=>base;

const stateText=(text,error=false)=>{
  const el=$("#form-status");
  el.textContent=text;el.classList.toggle("error",error);
};
const resultText=(title,subtitle)=>{
  $("#model-title").textContent=title;
  $("#model-subtitle").textContent=subtitle;
};
const stepNames={
  awaiting_worker:"Waiting for an available reconstruction worker",
  starting:"Starting reconstruction",
  extracting_features:"Extracting image features",
  matching_photographs:"Matching overlapping camera views",
  mapping_cameras:"Recovering camera positions and scene structure",
  undistorting_images:"Correcting camera distortion",
  dense_reconstruction:"Estimating dense 3D surface using CUDA",
  fusing_depth:"Fusing recovered depth data",
  building_surface:"Constructing a three-dimensional surface",
  projecting_photo_textures:"Mapping photographic detail onto the 3D surface",
  normalizing_scale_and_exporting:"Creating preview and measurement report",
  packaging:"Packaging the approved print candidate",
  ready_for_review:"3D reconstruction complete",
  worker_restart:"Processing resumed after worker restart",
  failed:"Reconstruction failed",
};
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const validType=f=>["image/jpeg","image/png","image/webp"].includes(f.type);

function renderPhotos(){
  fileUrls.forEach(URL.revokeObjectURL);fileUrls=[];
  const thumbs=$("#image-thumbs");thumbs.replaceChildren();
  photos.forEach((file,index)=>{
    const box=document.createElement("div");
    const img=document.createElement("img");
    const url=URL.createObjectURL(file);fileUrls.push(url);
    img.src=url;img.alt="Selected photograph "+(index+1);
    const remove=document.createElement("button");remove.type="button";
    remove.textContent="×";remove.setAttribute("aria-label","Remove photograph "+(index+1));
    remove.addEventListener("click",()=>{
      photos.splice(index,1);renderPhotos();refreshSubmit();
    });
    box.append(img,remove);thumbs.append(box);
  });
  $("#file-counter").textContent=photos.length+" / 12 minimum photographs";
  refreshSubmit();
}
function addPhotos(fileList){
  if(working||project){stateText("A reconstruction session is already active. Delete that project before changing its photo set.",true);return;}
  const selected=Array.from(fileList||[]);
  for(const file of selected){
    if(!validType(file)){stateText("Use only JPG, PNG or WebP photographs.",true);continue;}
    if(file.size>12*1024*1024){stateText("Photographs must not exceed 12 MB each.",true);continue;}
    if(photos.length>=40){stateText("Maximum 40 photographs per scan.",true);break;}
    if(!photos.some(p=>p.name===file.name&&p.size===file.size&&p.lastModified===file.lastModified))
      photos.push(file);
  }
  renderPhotos();
}
$("#photos").addEventListener("change",e=>{addPhotos(e.target.files);e.target.value="";});
$("#clear-photos").addEventListener("click",()=>{
  if(project){stateText("Delete the current project first to begin a different capture.",true);return;}
  photos=[];renderPhotos();
});
const dropzone=$("#dropzone");
dropzone.addEventListener("dragover",e=>{e.preventDefault();dropzone.classList.add("drag");});
dropzone.addEventListener("dragleave",()=>dropzone.classList.remove("drag"));
dropzone.addEventListener("drop",e=>{e.preventDefault();dropzone.classList.remove("drag");addPhotos(e.dataTransfer.files);});
$("#consent").addEventListener("change",refreshSubmit);

function refreshSubmit(){
  $("#submit-scan").disabled=working||!!project||!processingOnline||photos.length<12||photos.length>40||!$("#consent").checked;
  $("#clear-photos").disabled=!!project;
}
function setProgress(stage){
  $("#reconstruction-details").hidden=false;
  $("#stage-description").textContent=stepNames[stage]||stage.replace(/_/g," ");
  $("#result-state").textContent=stage.replace(/_/g," ").toUpperCase();
  $("#activity-bar").style.animationPlayState=stage==="ready_for_review"?"paused":"running";
}
function saveSession(){
  if(!project)return;
  sessionStorage.setItem(STORAGE_KEY,JSON.stringify({
    project_id:project.id,project_token:project.token,job_id:jobId,version_id:versionId
  }));
}
function clearSession(){
  sessionStorage.removeItem(STORAGE_KEY);
  project=null;jobId=null;versionId=null;
  pollRun++;working=false;
  $("#delete-project").disabled=true;
  $("#approve-model").disabled=true;
  $("#download-model").disabled=true;
  $("#view-report").disabled=true;
  $("#reconstruction-details").hidden=true;
  $("#result-state").textContent="NO RECONSTRUCTION";
  resultText("Awaiting a capture session","Submit 12–40 photographs to begin.");
  if(viewer){viewer.dispose();viewer=null;}
  $("#viewer").hidden=true;$("#empty-model").hidden=false;$("#qa-result").hidden=true;
  refreshSubmit();
}
async function api(path,options={}){
  if(!base)throw Error("A private Python processing service has not been configured.");
  const headers={...(options.headers||{})};
  if(project?.token)headers["X-Project-Token"]=project.token;
  const response=await fetch(base+path,{...options,headers,cache:"no-store"});
  if(!response.ok){
    let error="HTTP "+response.status;
    try{const j=await response.json();if(typeof j.detail==="string")error=j.detail;}catch{}
    throw Error(error);
  }
  return response;
}
async function checkServer(){
  if(!base){
    $("#backend-badge").textContent="PROCESSING NOT CONNECTED";
    $("#backend-badge").className="availability offline";
    stateText("Realistic reconstruction is unavailable until the private Python/GPU processing server is connected.",true);
    processingOnline=false;refreshSubmit();return;
  }
  try{
    const info=await (await api("/api/v2/health")).json();
    processingOnline=!!(info.upload_enabled&&info.colmap_installed&&info.blender_installed);
    $("#backend-badge").textContent=processingOnline?"PROCESSING ONLINE":"PROCESSING NOT READY";
    $("#backend-badge").className="availability "+(processingOnline?"online":"offline");
    stateText(processingOnline?
      "Processing server connected. Capture enough real photographs, then submit.":
      "Processing is not enabled or the COLMAP / Blender tools are unavailable on the server.",
      !processingOnline);
  }catch(error){
    processingOnline=false;
    $("#backend-badge").textContent="SERVICE UNREACHABLE";
    $("#backend-badge").className="availability offline";
    stateText("Could not reach the Python service. "+error.message,true);
  }
  refreshSubmit();
}
async function startProject(){
  if(!processingOnline||photos.length<12||!$("#consent").checked||working)return;
  working=true;refreshSubmit();
  try{
    stateText("Uploading photos privately. Please keep this tab open.");
    const data=new FormData();
    data.append("consent","true");
    photos.forEach(photo=>data.append("photos",photo,photo.name));
    const created=await (await api("/api/v2/projects",{method:"POST",body:data})).json();
    project={id:created.project_id,token:created.project_token};
    $("#delete-project").disabled=false;
    resultText("Photos received by processing service",created.image_count+" different photographs securely stored");
    const config={target_height_mm:Number($("#height").value),quality:$("#quality").value};
    const started=await (await api("/api/v2/projects/"+project.id+"/reconstruct",{
      method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(config)
    })).json();
    jobId=started.job_id;versionId=started.version_id;
    saveSession();
    setProgress("awaiting_worker");
    stateText("Reconstruction queued. The result will be a real model, not a generic character.");
    await pollUntilFinished();
  }catch(error){
    stateText("Could not start: "+error.message,true);
    if(project)saveSession();
  }finally{working=false;refreshSubmit();}
}
$("#submit-scan").addEventListener("click",startProject);

async function pollUntilFinished(){
  const run=++pollRun;
  if(!project||!jobId)return;
  while(run===pollRun){
    let job;
    try{
      job=await (await api("/api/v2/projects/"+project.id+"/jobs/"+jobId)).json();
    }catch(error){
      stateText("Connection interrupted: "+error.message+" — reload this tab to resume.",true);break;
    }
    setProgress(job.stage||job.state);
    if(job.state==="failed"){
      stateText(job.error||"The photographs could not be reconstructed. Choose a better photo set.",true);
      resultText("No valid 3D reconstruction", "The scan did not pass; no substitute was generated.");
      break;
    }
    if(job.state==="completed"){
      await loadModel(versionId);
      break;
    }
    await sleep(5000);
  }
}
async function loadModel(vid){
  if(!project||!vid)throw Error("No completed version");
  setProgress("ready_for_review");
  $("#model-title").textContent="Real reconstructed geometry";
  $("#model-subtitle").textContent="Drag to orbit · Scroll or pinch to zoom · Compare with your photographs";
  const res=await api("/api/v2/projects/"+project.id+"/versions/"+vid+"/preview");
  const glb=await res.arrayBuffer();
  if(glb.byteLength<1024)throw Error("Reconstruction preview is incomplete");
  const gltf=await new Promise((resolve,reject)=>
    new GLTFLoader().parse(glb,"",resolve,reject));
  if(!gltf.scene)throw Error("No 3D geometry in preview");
  const scene=new THREE.Scene();
  scene.background=new THREE.Color("#e4f0ec");
  scene.add(gltf.scene);
  scene.add(new THREE.HemisphereLight("#ffffff","#a6baba",3));
  const key=new THREE.DirectionalLight("#ffffff",3);key.position.set(3,5,8);scene.add(key);
  const host=$("#viewer");host.hidden=false;$("#empty-model").hidden=true;
  if(viewer)viewer.dispose();
  host.replaceChildren();
  const renderer=new THREE.WebGLRenderer({antialias:true,powerPreference:"low-power"});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));
  renderer.outputColorSpace=THREE.SRGBColorSpace;
  renderer.setClearColor("#e4f0ec",1);
  host.append(renderer.domElement);
  const bounds=new THREE.Box3().setFromObject(gltf.scene);
  const target=bounds.getCenter(new THREE.Vector3());
  const extent=bounds.getSize(new THREE.Vector3());
  const radius=Math.max(extent.length(),.08);
  const cam=new THREE.PerspectiveCamera(42,1,.001,Math.max(100,radius*50));
  cam.position.copy(target).add(new THREE.Vector3(radius*1.2,radius*.7,radius*1.3));
  const controls=new OrbitControls(cam,renderer.domElement);
  controls.target.copy(target);controls.enableDamping=true;
  controls.minDistance=radius*.4;controls.maxDistance=radius*8;controls.update();
  const onResize=()=>{
    if(!host.isConnected)return;
    const w=Math.max(1,host.clientWidth),h=Math.max(1,host.clientHeight);
    renderer.setSize(w,h,false);cam.aspect=w/h;cam.updateProjectionMatrix();
  };
  const resize=new ResizeObserver(onResize);resize.observe(host);onResize();
  let active=true;let frameId;
  const loop=()=>{if(!active)return;frameId=requestAnimationFrame(loop);controls.update();renderer.render(scene,cam);};loop();
  viewer={dispose(){active=false;cancelAnimationFrame(frameId);resize.disconnect();controls.dispose();renderer.dispose();host.replaceChildren();}};
  $("#approve-model").disabled=false;
  $("#view-report").disabled=false;
  stateText("Real model loaded. Review the full 360° reconstruction before approving.");
  try{
    const status=await (await api("/api/v2/projects/"+project.id)).json();
    if(status.versions.find(v=>v.id===vid)?.customer_approved)$("#download-model").disabled=false;
  }catch{}
}
$("#approve-model").addEventListener("click",async()=>{
  if(!project||!versionId)return;
  try{
    const confirmed=await (await api("/api/v2/projects/"+project.id+"/versions/"+versionId+"/approve",{
      method:"POST"
    })).json();
    if(confirmed.status==="design_approved_unpaid"){
      $("#download-model").disabled=false;
      stateText("Design approved. This is not a paid order or a certified manufacturing file.");
    }
  }catch(error){stateText(error.message,true);}
});
$("#download-model").addEventListener("click",async()=>{
  if(!project||!versionId)return;
  const button=$("#download-model");button.disabled=true;
  try{
    stateText("Retrieving the private manufacturing candidate...");
    const response=await api("/api/v2/projects/"+project.id+"/versions/"+versionId+"/package");
    const blob=await response.blob(),url=URL.createObjectURL(blob);
    const a=document.createElement("a");a.href=url;a.download="minimo-realistic-"+versionId+".zip";
    document.body.append(a);a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),30000);
    stateText("ZIP downloaded. Repair and supplier inspection are mandatory before printing.");
  }catch(error){stateText(error.message,true);}
  finally{button.disabled=false;}
});
$("#view-report").addEventListener("click",async()=>{
  if(!project||!versionId)return;
  try{
    const data=await (await api("/api/v2/projects/"+project.id+"/versions/"+versionId+"/report")).json();
    const out=$("#qa-result");out.hidden=false;
    out.textContent=JSON.stringify(data,null,2);
  }catch(error){stateText(error.message,true);}
});
$("#delete-project").addEventListener("click",async()=>{
  if(!project)return;
  if(!confirm("Delete this project and its uploaded photographs? This cannot be undone."))return;
  try{
    await api("/api/v2/projects/"+project.id,{method:"DELETE"});
    clearSession();photos=[];renderPhotos();
    stateText("The project and associated photographs were deleted from the processing service.");
  }catch(error){stateText("Deletion failed: "+error.message,true);}
});
async function resume(){
  let saved;
  try{saved=JSON.parse(sessionStorage.getItem(STORAGE_KEY)||"null");}catch{}
  if(!saved?.project_id||!saved?.project_token)return;
  project={id:saved.project_id,token:saved.project_token};
  jobId=saved.job_id||null;
  versionId=saved.version_id||null;
  $("#delete-project").disabled=false;
  refreshSubmit();
  try{
    const details=await (await api("/api/v2/projects/"+project.id)).json();
    resultText("Previous capture restored",details.image_count+" photographs · private project session");
    const job=details.jobs.find(j=>j.id===jobId);
    if(job?.state==="completed"&&versionId)await loadModel(versionId);
    else if(job?.state==="failed"){setProgress("failed");stateText(job.error||"Reconstruction failed",true);}
    else if(jobId)pollUntilFinished();
  }catch(error){
    if(error.message.includes("404")||error.message.includes("410"))clearSession();
    else stateText("Saved project unavailable: "+error.message,true);
  }
}
await checkServer();
await resume();
