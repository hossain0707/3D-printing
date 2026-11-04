// Private operator console: never bake admin credentials into public source.
const $=s=>document.querySelector(s);
const url=$("#api-url"),key=$("#admin-key"),status=$("#status");
url.value=String(window.MINIMO_API_URL||"");
function td(row,value){const cell=document.createElement("td");cell.textContent=String(value);row.append(cell);return cell;}
function sanitizeOrigin(value){
  const base=value.trim().replace(/\/+$/,"");
  if(!/^https:\/\//.test(base)&&!/^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(base))
    throw Error("Use HTTPS (or HTTP localhost for development only).");
  return base;
}
async function api(path,options={}){
  const base=sanitizeOrigin(url.value);
  if(key.value.length<32)throw Error("Enter a valid operator access key.");
  const response=await fetch(base+path,{
    ...options,
    cache:"no-store",
    headers:{"X-Admin-Key":key.value,...options.headers}
  });
  if(!response.ok){let reason="HTTP "+response.status;
    try{reason=(await response.json()).detail||reason;}catch{}
    throw Error(reason);
  }
  return response;
}
const transitions={
  review_required:["needs_repair","geometry_reviewed","rejected"],
  needs_repair:["geometry_reviewed","rejected"],
  geometry_reviewed:["needs_repair","supplier_accepted","rejected"],
  supplier_accepted:["printed","rejected"],
  printed:["shipped"], shipped:[], rejected:[]
};
async function download(id){
  status.textContent="Retrieving real reconstructed model...";
  const response=await api("/api/v2/admin/versions/"+id+"/package");
  const blob=await response.blob(),uri=URL.createObjectURL(blob);
  const a=document.createElement("a");a.href=uri;a.download="minimo-review-"+id+".zip";
  document.body.append(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(uri),20000);
  status.textContent="Downloaded. Verify geometry, texture, physical scale and supplier requirements.";
}
async function update(id,value){
  await api("/api/v2/admin/versions/"+id,{
    method:"PATCH",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({status:value})
  });
  await refresh();
}
function actionsCell(row,version){
  const cell=document.createElement("td");cell.className="actions";
  const button=document.createElement("button");button.textContent="Download";
  button.addEventListener("click",()=>download(version.id).catch(e=>status.textContent=e.message));
  const select=document.createElement("select");select.setAttribute("aria-label","Change production status");
  const first=document.createElement("option");first.value="";first.textContent="Change state";select.append(first);
  for(const value of transitions[version.operator_status]||[]){
    const option=document.createElement("option");option.value=value;option.textContent=value.replaceAll("_"," ");select.append(option);
  }
  select.addEventListener("change",()=>{const value=select.value;select.value="";
    if(value&&confirm("Confirm operator status '"+value+"' for version "+version.id+"?"))
      update(version.id,value).catch(e=>status.textContent=e.message);
  });
  cell.append(button,select);row.append(cell);
}
async function refresh(){
  status.textContent="Connecting...";
  const result=await (await api("/api/v2/admin/queue")).json();
  const versions=$("#versions");versions.replaceChildren();
  for(const v of result.versions){
    const row=document.createElement("tr");
    td(row,v.id.slice(0,10));td(row,v.project_id.slice(0,10));
    td(row,v.customer_approved?"Yes":"Not yet");td(row,v.operator_status);
    actionsCell(row,v);versions.append(row);
  }
  if(!result.versions.length){const row=document.createElement("tr");const cell=td(row,"No models ready for review.");cell.colSpan=5;versions.append(row);}
  const jobs=$("#jobs");jobs.replaceChildren();
  for(const j of result.jobs){
    const row=document.createElement("tr");td(row,j.id.slice(0,10));
    td(row,j.project_id.slice(0,10));td(row,j.stage);td(row,j.state);td(row,j.created_at);
    jobs.append(row);
  }
  if(!result.jobs.length){const row=document.createElement("tr");const cell=td(row,"No reconstruction jobs.");cell.colSpan=5;jobs.append(row);}
  status.textContent="Authenticated. "+result.jobs.length+" jobs, "+result.versions.length+" models.";
}
$("#refresh").addEventListener("click",()=>refresh().catch(e=>status.textContent="Access failed: "+e.message));
