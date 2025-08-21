const $=sel=>document.querySelector(sel);
const $$=sel=>Array.from(document.querySelectorAll(sel));
const MAX_SIZE=5*1024*1024;
const PERIOD=30000;
const RADIUS=13;
const FULL_DASH_ARRAY=2*Math.PI*RADIUS;

function show(el){el.classList.remove("hidden");}
function hide(el){el.classList.add("hidden");}
function fetchJSON(u,o={}){return fetch(u,o).then(r=>r.json().then(d=>{if(!r.ok)throw new Error(d.message||`Error: ${r.status}`);return d}))}

function copyCode(el){
  navigator.clipboard.writeText(el.innerText);
  const msg=document.createElement("span");
  msg.className="absolute -top-6 left-1/2 -translate-x-1/2 bg-primary text-primary-text text-xs px-2 py-1 rounded opacity-0 transition-opacity";
  msg.innerText="Copied!";
  el.parentElement.style.position="relative";
  el.parentElement.appendChild(msg);
  setTimeout(()=>msg.classList.add("opacity-100"),10);
  setTimeout(()=>{msg.classList.remove("opacity-100");setTimeout(()=>el.parentElement.removeChild(msg),200);},1600);
}
window.copyCode=copyCode;

function normalizeList(json){
  if(Array.isArray(json))return json;
  if(json&&typeof json==="object"){
    if(Array.isArray(json.items))return json.items;
    if(Array.isArray(json.totps))return json.totps;
    if(Array.isArray(json.data))return json.data;
    const k=Object.keys(json).find(k=>Array.isArray(json[k]));
    if(k)return json[k];
  }
  return [];
}
function getItemId(it){return String(it.id??it.totp_id??it.totpId??it.tid??"");}
function getItemCode(it){return String(it.code??it.current_code??it.value??it.otp??it.token??"");}
function findCodeEl(row){return row.querySelector(".totp-code")||row.querySelector(".code-cell code")||row.querySelector("td:nth-child(3) code")||row.querySelector("code");}

async function fetchTotpData(endpoint){
  try{const d=await fetchJSON(endpoint);return normalizeList(d);}catch(err){console.error("Failed to fetch TOTP:",err);const table=endpoint.includes("shared")?"#shared-totp-table":"#totp-table";return [...$$(table+" tbody tr")].map(row=>({id:row.dataset.id,code:"Error"}));}
}
function updateCodes(data,tableSelector){
  const list=normalizeList(data);
  $$(tableSelector+" tbody tr").forEach(row=>{
    const id=row.dataset.id;
    const it=list.find(i=>getItemId(i)===id);
    const code=it?getItemCode(it):"";
    const codeEl=findCodeEl(row);
    if(codeEl&&code&&codeEl.textContent!==code){
      codeEl.textContent=code;
      codeEl.classList.toggle("text-danger",code==="Error");
    }
  });
}

function isMyTabActive(){return !$("#my-codes").classList.contains("hidden");}
function rowCheckboxes(){return $$("#totp-table .row-check");}
function mobileSelectWrap(){const m=$("#select-all-mobile");return m?m.closest(".md\\:hidden"):null;}
function toggleMobileSelectVisible(v){const wrap=mobileSelectWrap();if(!wrap)return;wrap.classList.toggle("hidden",!v);}

let lastCycle=0;
function refreshCodes(){fetchTotpData("/totp/list-all").then(d=>updateCodes(d,"#totp-table"));fetchTotpData("/totp/list-shared-with-me").then(d=>updateCodes(d,"#shared-totp-table"))}
function animateProgress(){
  const now=Date.now();
  const offset=FULL_DASH_ARRAY*((now%PERIOD)/PERIOD);
  $$(".countdown-ring__progress").forEach(c=>{c.style.strokeDashoffset=offset;});
  const currentCycle=Math.floor(now/PERIOD);
  if(currentCycle!==lastCycle){lastCycle=currentCycle;refreshCodes();}
  requestAnimationFrame(animateProgress);
}

function showQrModalFromBlob(blob){
  const url=URL.createObjectURL(blob);
  const overlay=document.createElement("div");
  overlay.className="fixed inset-0 bg-black/75 z-50 flex items-center justify-center";
  overlay.onclick=()=>{URL.revokeObjectURL(url);overlay.remove();};
  const img=document.createElement("img");
  img.src=url;img.className="max-w-[90%] max-h-[90%] shadow-xl";img.onclick=e=>e.stopPropagation();
  overlay.appendChild(img);document.body.appendChild(overlay);
}

function parseMigrationQRCode(img,targetInput){
  const canvas=document.createElement("canvas");
  const ctx=canvas.getContext("2d");
  canvas.width=img.naturalWidth;canvas.height=img.naturalHeight;
  ctx.drawImage(img,0,0);
  const data=ctx.getImageData(0,0,canvas.width,canvas.height);
  const code=jsQR(data.data,canvas.width,canvas.height);
  if(!code||!code.data.startsWith("otpauth-migration://")){alert("Invalid QR code.");return;}
  targetInput.value=code.data;
}

async function showSharedUsers(totpId){
  const modal=$("#shared-users-modal");
  const list=$("#shared-users-list");
  show(modal);
  list.innerHTML="<p>Loading...</p>";
  try{
    const data=await fetchJSON(`/totp/shared-users/${totpId}`);
    list.innerHTML=data.emails.length?data.emails.map(email=>`<div class="flex justify-between items-center mb-2"><span>${email}</span><button onclick="unshareTotp(${totpId}, '${email}')" class="text-danger-500 hover:text-danger-700">✕</button></div>`).join(""):"<p>No users shared with.</p>";
  }catch{list.innerHTML="<p>Failed to load users.</p>";}
}
window.showSharedUsers=showSharedUsers;

async function unshareTotp(totpId,email){
  const fd=new FormData();
  fd.append("totp_id",totpId);
  fd.append("email",email);
  try{
    const res=await fetch("/totp/unshare",{method:"POST",body:fd});
    if(!res.ok)throw new Error("Unshare failed");
    await showSharedUsers(totpId);
    const data=await fetchJSON(`/totp/shared-users/${totpId}`);
    if(data.emails.length===0){
      const row=$(`#totp-table tr[data-id="${totpId}"]`);
      const btn=row?.querySelector('.shared-btn')||row?.querySelector('button[onclick^="showSharedUsers"]');
      if(btn)btn.remove();
    }
  }catch(err){console.error(err);}
}
window.unshareTotp=unshareTotp;

document.addEventListener("DOMContentLoaded",()=>{
  refreshCodes();
  animateProgress();

  const selectAll=$("#select-all");
  const selectAllMobile=$("#select-all-mobile");
  const exportBar=$("#export-bar");
  const exportBtn=$("#export-btn");
  const deleteBtn=$("#delete-selected-btn");
  const shareBtn=$("#share-btn");
  const exportIdsInput=$("#export-ids");
  const deleteIdsInput=$("#delete-ids");
  const shareIdsInput=$("#share-ids");
  const exportCancel=$("#export-cancel");

  function updateExportState(){
    const ids=rowCheckboxes().filter(c=>c.checked).map(c=>c.value).join(",");
    [exportIdsInput,deleteIdsInput,shareIdsInput].forEach(el=>el.value=ids);
    const active=ids.length>0;
    [exportBtn,deleteBtn,shareBtn].forEach(btn=>{btn.disabled=!active;btn.classList.toggle("opacity-50",!active);btn.classList.toggle("cursor-not-allowed",!active);});
    exportBar.classList.toggle("translate-y-full",!active);
    exportBar.classList.toggle("opacity-0",!active);
  }

  function clearSelection(){
    if(selectAll)selectAll.checked=false;
    if(selectAllMobile)selectAllMobile.checked=false;
    rowCheckboxes().forEach(c=>c.checked=false);
    updateExportState();
  }

  if(selectAll){
    selectAll.addEventListener("change",()=>{if(!isMyTabActive())return;rowCheckboxes().forEach(c=>c.checked=selectAll.checked);if(selectAllMobile)selectAllMobile.checked=selectAll.checked;updateExportState();});
  }
  if(selectAllMobile){
    selectAllMobile.addEventListener("change",()=>{if(!isMyTabActive())return;if(selectAll)selectAll.checked=selectAllMobile.checked;rowCheckboxes().forEach(c=>c.checked=selectAllMobile.checked);updateExportState();});
  }
  rowCheckboxes().forEach(c=>c.addEventListener("change",updateExportState));
  if(exportCancel)exportCancel.addEventListener("click",clearSelection);

  const tabs={"my-codes-tab":"my-codes","shared-with-me-tab":"shared-with-me"};
  for(const [tabId,contentId] of Object.entries(tabs)){
    $(`#${tabId}`).addEventListener("click",()=>{
      Object.entries(tabs).forEach(([tid,cid])=>{$(`#${tid}`).classList.toggle("text-primary",tid===tabId);$(`#${tid}`).classList.toggle("text-gray-500",tid!==tabId);$(`#${tid}`).classList.toggle("border-primary",tid===tabId);$(`#${tid}`).classList.toggle("border-transparent",tid!==tabId);$(`#${cid}`).classList.toggle("hidden",cid!==contentId);});
      toggleMobileSelectVisible(contentId==="my-codes");
      clearSelection();
    });
  }
  toggleMobileSelectVisible(isMyTabActive());

  const exportForm=$("#export-selected-form");
  if(exportBtn&&exportForm){
    exportBtn.addEventListener("click",async()=>{
      const res=await fetch(exportForm.action,{method:exportForm.method,body:new FormData(exportForm),credentials:"same-origin"});
      if(!res.ok)return alert("Failed to load QR");
      const blob=await res.blob();
      showQrModalFromBlob(blob);
    });
  }

  const importModal=$("#import-modal");
  const fileInput=$("#import-file");
  const textInput=$("#import-text");
  const importBtn=$("#import-btn");
  const importCancel=$("#import-cancel");

  if(importBtn)importBtn.addEventListener("click",()=>{show(importModal);textInput.value="";fileInput.value=null;textInput.focus();});
  if(importCancel)importCancel.addEventListener("click",()=>hide(importModal));

  if(fileInput)fileInput.addEventListener("change",e=>{
    const file=e.target.files[0];
    if(!file||!file.type.startsWith("image/")||file.size>MAX_SIZE){alert("Invalid image (max 5MB)");return;}
    const img=new Image();
    img.onload=()=>{parseMigrationQRCode(img,textInput);URL.revokeObjectURL(img.src);};
    img.src=URL.createObjectURL(file);
  });

  window.addEventListener("paste",e=>{
    if(!importModal||importModal.classList.contains("hidden"))return;
    [...e.clipboardData.items].forEach(item=>{
      if(item.type.startsWith("image/")){
        const blob=item.getAsFile();
        if(blob.size>MAX_SIZE){alert("Image too large");return;}
        const img=new Image();
        img.onload=()=>{parseMigrationQRCode(img,textInput);URL.revokeObjectURL(img.src);};
        img.src=URL.createObjectURL(blob);
        e.preventDefault();
      }
    });
  });

  if(shareBtn)shareBtn.addEventListener("click",()=>{
    const ids=shareIdsInput.value;
    if(!ids){alert("Select at least one TOTP to share");return;}
    const modal=$("#share-modal");
    show(modal);
    $("#share-email").value="";
    $("#share-totp-ids").value=ids;
    $("#share-email").focus();
  });

  $("#share-cancel")?.addEventListener("click",()=>hide($("#share-modal")));
  $("#shared-users-cancel")?.addEventListener("click",()=>hide($("#shared-users-modal")));
});
