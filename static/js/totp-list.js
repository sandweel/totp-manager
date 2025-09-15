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
const getItemId=it=>String(it.id??it.totp_id??it.totpId??it.tid??"");
const getItemCode=it=>String(it.code??it.current_code??it.value??it.otp??it.token??"");
function findCodeEl(row){return row.querySelector(".totp-code")||row.querySelector(".code-cell code")||row.querySelector("td:nth-child(3) code")||row.querySelector("code");}

async function fetchTotpData(endpoint){
  try{return normalizeList(await fetchJSON(endpoint));}
  catch(err){console.error("Failed to fetch TOTP:",err);const table=endpoint.includes("shared")?"#shared-totp-table":"#totp-table";return [...$$(table+" tbody tr")].map(row=>({id:row.dataset.id,code:"Error"}));}
}

function updateCodes(data,tableSelector){
  const map=new Map(normalizeList(data).map(i=>[getItemId(i),getItemCode(i)]));
  $$(tableSelector+" tbody tr").forEach(row=>{
    const code=map.get(row.dataset.id)||"";
    const codeEl=findCodeEl(row);
    if(codeEl&&code&&codeEl.textContent!==code){
      codeEl.textContent=code;
      codeEl.classList.toggle("text-danger",code==="Error");
    }
  });
}

function isMyTabActive(){return !$("#my-codes").classList.contains("hidden");}
function mobileSelectWrap(){const m=$("#select-all-mobile");return m?m.closest(".md\\:hidden"):null;}
function toggleMobileSelectVisible(v){const wrap=mobileSelectWrap();if(!wrap)return;wrap.classList.toggle("hidden",!v);}

let lastCycle=0,progressEls=null;
function refreshCodes(){
  fetchTotpData("/totp/list-all").then(d=>updateCodes(d,"#totp-table"));
  fetchTotpData("/totp/list-shared-with-me").then(d=>updateCodes(d,"#shared-totp-table"));
}
function animateProgress(){
  const now=Date.now();
  const offset=FULL_DASH_ARRAY*((now%PERIOD)/PERIOD);
  (progressEls||(progressEls=$$(".countdown-ring__progress"))).forEach(c=>{c.style.strokeDashoffset=offset;});
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
  const totpTable=$("#totp-table");
  const sharedTable=$("#shared-totp-table");
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
  const mySearch=$("#my-codes-search");
  const sharedSearch=$("#shared-codes-search");
  const exportForm=$("#export-selected-form");
  const importModal=$("#import-modal");
  const fileInput=$("#import-file");
  const textInput=$("#import-text");
  const importBtn=$("#import-btn");
  const importCancel=$("#import-cancel");

  const rowChecks=()=>Array.from(totpTable.querySelectorAll("tbody tr")).filter(row=>row.style.display!=="none"&&!row.classList.contains("hidden")).map(row=>row.querySelector(".row-check")).filter(Boolean);

  function updateExportState(){
    const ids=[];
    const checks=rowChecks();
    for(const c of checks)if(c.checked)ids.push(c.value);
    const joined=ids.join(",");
    [exportIdsInput,deleteIdsInput,shareIdsInput].forEach(el=>{if(el)el.value=joined;});
    const active=joined.length>0;
    [exportBtn,deleteBtn,shareBtn].forEach(btn=>{if(!btn)return;btn.disabled=!active;btn.classList.toggle("opacity-50",!active);btn.classList.toggle("cursor-not-allowed",!active);});
    exportBar?.classList.toggle("translate-y-full",!active);
    exportBar?.classList.toggle("opacity-0",!active);
  }

  function syncSelectAllFromRows(){
    const checks=rowChecks();
    const total=checks.length;
    let selected=0;
    for(const c of checks)if(c.checked)selected++;
    const all=total>0&&selected===total;
    const none=selected===0;
    [selectAll,selectAllMobile].forEach(el=>{if(!el)return;el.indeterminate=!none&&!all;el.checked=all;});
  }

  function applyToRows(checked){
    rowChecks().forEach(cb=>cb.checked=checked);
    updateExportState();
    syncSelectAllFromRows();
  }

  refreshCodes();
  animateProgress();

  if(selectAllMobile)selectAllMobile.addEventListener("change",()=>{if(!isMyTabActive())return;if(selectAll){selectAll.checked=selectAllMobile.checked;selectAll.indeterminate=false;}applyToRows(selectAllMobile.checked);});
  if(selectAll)selectAll.addEventListener("change",()=>{if(!isMyTabActive())return;if(selectAllMobile){selectAllMobile.checked=selectAll.checked;selectAllMobile.indeterminate=false;}applyToRows(selectAll.checked);});

  document.addEventListener("change",e=>{
    if(e.target.closest(".row-check")){updateExportState();syncSelectAllFromRows();}
  });

  if(exportCancel)exportCancel.addEventListener("click",()=>{
    [selectAll,selectAllMobile].forEach(el=>{if(el){el.checked=false;el.indeterminate=false;}});
    rowChecks().forEach(c=>c.checked=false);
    updateExportState();
  });

  function normalize(s){return (s||"").toLowerCase();}
  function filterTableRows(input,table,rowSelector,fields){
    const filter=normalize(input.value);
    table.querySelectorAll(rowSelector).forEach(row=>{
      let text="";
      for(const sel of fields){const el=row.querySelector(sel);if(el)text+=" "+el.textContent;}
      row.style.display=normalize(text).includes(filter)?"":"none";
    });
    syncSelectAllFromRows();
    updateExportState();
  }
  function debounce(fn,ms){let t;return (...a)=>{clearTimeout(t);t=setTimeout(()=>fn(...a),ms);};}

  if(mySearch)mySearch.addEventListener("input",debounce(()=>{filterTableRows(mySearch,totpTable,"tbody > tr",['[data-field="account"]','[data-field="issuer"]',".totp-code"]);},150));
  if(sharedSearch)sharedSearch.addEventListener("input",debounce(()=>{filterTableRows(sharedSearch,sharedTable,"tbody > tr",['[data-field="account"]','[data-field="issuer"]','[data-field="owner"]',".totp-code"]);},150));

  const tabs={"my-codes-tab":"my-codes","shared-with-me-tab":"shared-with-me"};
  for(const [tabId,contentId] of Object.entries(tabs)){
    $(`#${tabId}`).addEventListener("click",()=>{
      for(const [tid,cid] of Object.entries(tabs)){
        $(`#${tid}`).classList.toggle("text-primary",tid===tabId);
        $(`#${tid}`).classList.toggle("text-gray-500",tid!==tabId);
        $(`#${tid}`).classList.toggle("border-primary",tid===tabId);
        $(`#${tid}`).classList.toggle("border-transparent",tid!==tabId);
        $(`#${cid}`).classList.toggle("hidden",cid!==contentId);
      }
      toggleMobileSelectVisible(contentId==="my-codes");
      [selectAll,selectAllMobile].forEach(el=>{if(el){el.checked=false;el.indeterminate=false;}});
      rowChecks().forEach(c=>c.checked=false);
      updateExportState();
    });
  }
  toggleMobileSelectVisible(isMyTabActive());

  if(exportBtn&&exportForm){
    exportBtn.addEventListener("click",async()=>{
      const res=await fetch(exportForm.action,{method:exportForm.method,body:new FormData(exportForm),credentials:"same-origin"});
      if(!res.ok)return alert("Failed to load QR");
      const blob=await res.blob();
      showQrModalFromBlob(blob);
    });
  }

  function handleImageFile(file){
    if(!file||!file.type.startsWith("image/")||file.size>MAX_SIZE){alert("Invalid image (max 5MB)");return;}
    const img=new Image();
    img.onload=()=>{parseMigrationQRCode(img,textInput);URL.revokeObjectURL(img.src);};
    img.src=URL.createObjectURL(file);
  }

  if(importBtn)importBtn.addEventListener("click",()=>{show(importModal);textInput.value="";if(fileInput)fileInput.value=null;textInput.focus();});
  if(importCancel)importCancel.addEventListener("click",()=>hide(importModal));
  if(fileInput)fileInput.addEventListener("change",e=>handleImageFile(e.target.files[0]));
  window.addEventListener("paste",e=>{
    if(!importModal||importModal.classList.contains("hidden"))return;
    for(const item of e.clipboardData.items){
      if(item.type.startsWith("image/")){
        const blob=item.getAsFile();
        if(blob.size>MAX_SIZE){alert("Image too large");return;}
        handleImageFile(blob);
        e.preventDefault();
      }
    }
  });

  if(shareBtn)shareBtn.addEventListener("click",()=>{
    const ids=shareIdsInput?.value||"";
    if(!ids){alert("Select at least one TOTP to share");return;}
    const modal=$("#share-modal");
    show(modal);
    $("#share-email").value="";
    $("#share-totp-ids").value=ids;
    $("#share-email").focus();
  });

  $("#share-cancel")?.addEventListener("click",()=>hide($("#share-modal")));
  $("#shared-users-cancel")?.addEventListener("click",()=>hide($("#shared-users-modal")));

  document.addEventListener("click",e=>{
    const btn=e.target.closest(".shared-btn[data-shared-id]");
    if(btn){const id=btn.getAttribute("data-shared-id");if(id)showSharedUsers(id);}
  });

  document.addEventListener("click",e=>{
    const editBtn=e.target.closest(".edit-totp");
    if(!editBtn)return;
    const row=editBtn.closest("tr");
    const accountEl=row.querySelector('[data-editable-account]');
    const controls=row.querySelector(".totp-controls");
    const saveControl=controls.querySelector(".save-totp");
    const cancelControl=controls.querySelector(".cancel-edit");
    const accVal=accountEl.textContent.trim();
    const rect=accountEl.getBoundingClientRect();
    accountEl.style.position="relative";
    accountEl.style.minHeight=`${Math.ceil(rect.height)}px`;
    accountEl.classList.add("rounded");
    accountEl.innerHTML=`<span class="block truncate pointer-events-none">${accVal}</span><input type="text" class="absolute inset-0 w-full h-full text-sm bg-warning-100 border border-gray-300 outline-none focus:ring-0 px-1" value="${accVal}" data-input-account />`;
    controls.querySelector(".edit-totp").classList.add("hidden");
    saveControl.classList.remove("hidden");
    cancelControl.classList.remove("hidden");
    const input=accountEl.querySelector("[data-input-account]");
    if(input){input.focus();input.select();}
  });

  document.addEventListener("click",e=>{
    const saveBtn=e.target.closest(".save-totp");
    if(!saveBtn)return;
    const row=saveBtn.closest("tr");
    const totpId=saveBtn.getAttribute("data-id");
    const accountEl=row.querySelector('[data-editable-account]');
    const controls=row.querySelector(".totp-controls");
    const editControl=controls.querySelector(".edit-totp");
    const cancelControl=controls.querySelector(".cancel-edit");
    const input=accountEl.querySelector("[data-input-account]");
    const newAccount=input?input.value.trim():accountEl.textContent.trim();
    if(!newAccount){alert("Account is required");return;}
    const fd=new FormData();
    fd.append("totp_id",totpId);
    fd.append("account",newAccount);
    fetch("/totp/update",{method:"POST",body:fd,credentials:"same-origin"})
      .then(r=>r.json().then(j=>({ok:r.ok,body:j})))
      .then(({ok,body})=>{
        if(!ok){showFlash(body.flash?.message||"Update failed",body.flash?.category||"error");throw new Error(body.flash?.message||"Update failed");}
        accountEl.textContent=newAccount;
        accountEl.classList.remove("rounded");
        accountEl.style.position="";
        accountEl.style.minHeight="";
        saveBtn.classList.add("hidden");
        cancelControl.classList.add("hidden");
        editControl.classList.remove("hidden");
        if(body.flash)showFlash(body.flash.message,body.flash.category);
      })
      .catch(err=>{console.error(err);});
  });

  document.addEventListener("click",e=>{
    const cancelBtn=e.target.closest(".cancel-edit");
    if(!cancelBtn)return;
    const row=cancelBtn.closest("tr");
    const accountEl=row.querySelector('[data-editable-account]');
    const controls=row.querySelector(".totp-controls");
    const editControl=controls.querySelector(".edit-totp");
    const saveControl=controls.querySelector(".save-totp");
    const input=accountEl.querySelector("[data-input-account]");
    const original=input?input.defaultValue:accountEl.textContent;
    accountEl.textContent=original;
    accountEl.classList.remove("rounded");
    accountEl.style.position="";
    accountEl.style.minHeight="";
    saveControl.classList.add("hidden");
    cancelBtn.classList.add("hidden");
    editControl.classList.remove("hidden");
  });

  let lastSaveTime=0;
  const SAVE_DEBOUNCE=2000;
  document.addEventListener("keydown",e=>{
    const input=e.target.closest("[data-input-account]");
    if(!input)return;
    if(e.key==="Enter"){
      e.preventDefault();
      const now=Date.now();
      if(now-lastSaveTime<SAVE_DEBOUNCE){showFlash("Not so fast!","warning");return;}
      lastSaveTime=now;
      const row=input.closest("tr");
      const saveBtn=row.querySelector(".save-totp");
      if(saveBtn)saveBtn.click();
    }
    if(e.key==="Escape"){
      e.preventDefault();
      const row=input.closest("tr");
      const cancelBtn=row.querySelector(".cancel-edit");
      if(cancelBtn)cancelBtn.click();
    }
  });
});
