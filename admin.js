// Operator-only API client. Never embed credentials in a public bundle.
const $=selector=>document.querySelector(selector);
const endpoint=$("#api-url"),key=$("#admin-key"),status=$("#status");
endpoint.value=String(window.MINIMO_API_URL||"");
const add=(tag,text)=>{const node=document.createElement(tag);node.textContent=String(text);return node;};
const origin=()=>endpoint.value.trim().replace(/\/+$/,"");
async function request(path,options={}){
 const host=origin();if(!/^https:\/\//.test(host)&&!/^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(host))
   throw Error("Use HTTPS for the Python API; local HTTP is allowed only on localhost.");
 if(key.value.length<32)throw Error("Enter your 32+ character operator key.");
 const response=await fetch(host+path,{...options,headers:{"X-Admin-Key":key.value,...options.headers},cache:"no-store"});
 if(!response.ok){let message="HTTP "+response.status;try{const data=await response.json();message=data.detail||message;}catch{}throw Error(message);}
 return response;
}
function cell(row,content){const td=document.createElement("td");if(content instanceof Node)td.append(content);else td.textContent=String(content);row.append(td);return td;}
function tool(name,callback,css="secondary"){const btn=document.createElement("button");btn.type="button";btn.textContent=name;btn.className=css;btn.addEventListener("click",()=>callback().catch(err=>status.textContent="Error: "+err.message));return btn;}
async function downloadVersion(vid){
 status.textContent="Retrieving private manufacturing candidate…";
 const response=await request("/api/v1/admin/versions/"+encodeURIComponent(vid)+"/package");
 const blob=await response.blob();const url=URL.createObjectURL(blob);
 const link=document.createElement("a");link.href=url;link.download="minimo-operator-"+vid+".zip";
 document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),20000);
 status.textContent="Downloaded private package. Operator QA is still required.";
}
async function transition(version,state){
 await request("/api/v1/admin/versions/"+encodeURIComponent(version.id)+"/production",{
   method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({status:state})
 });await refresh();
}
const transitions={
 unreviewed:["needs_repair","validated","rejected"],
 needs_repair:["validated","rejected"],
 validated:["needs_repair","submitted","rejected"],
 submitted:["printed","rejected"],
 printed:["shipped"],
 shipped:[],rejected:[]
};
async function refresh(){
 status.textContent="Connecting to the private Python service…";
 const data=await (await request("/api/v1/admin/queue")).json();
 const versions=$("#versions");versions.replaceChildren();
 for(const version of data.versions){
   const row=document.createElement("tr");
   cell(row,version.id.slice(0,8));cell(row,version.project_id.slice(0,8));
   cell(row,version.customer_approved?"Approved":"Not approved");
   cell(row,version.production_state);
   const actions=document.createElement("div");actions.className="actions";
   actions.append(tool("Download",()=>downloadVersion(version.id)));
   const dropdown=document.createElement("select");
   dropdown.setAttribute("aria-label","Change production status");
   dropdown.append(add("option","Choose action"));
   for(const next of transitions[version.production_state]||[]){
     const opt=document.createElement("option");opt.value=next;opt.textContent=next.replaceAll("_"," ");
     dropdown.append(opt);
   }
   dropdown.addEventListener("change",()=>{
     if(!dropdown.value)return;
     const next=dropdown.value;dropdown.value="";
     if(confirm("Confirm operator transition to '"+next+"' for "+version.id+"?")){
       transition(version,next).catch(err=>status.textContent="Error: "+err.message);
     }
   });
   actions.append(dropdown);cell(row,actions);versions.append(row);
 }
 if(!data.versions.length)versions.append(Object.assign(document.createElement("tr"),{textContent:"No versions yet."}));
 const jobs=$("#jobs");jobs.replaceChildren();
 for(const job of data.jobs){const row=document.createElement("tr");cell(row,job.id.slice(0,8));cell(row,job.project_id.slice(0,8));cell(row,job.state);cell(row,job.created_at);jobs.append(row);}
 if(!data.jobs.length)jobs.append(Object.assign(document.createElement("tr"),{textContent:"No jobs yet."}));
 status.textContent="Authenticated. "+data.versions.length+" versions and "+data.jobs.length+" jobs loaded.";
}
$("#refresh").addEventListener("click",()=>refresh().catch(err=>status.textContent="Connection failed: "+err.message));
