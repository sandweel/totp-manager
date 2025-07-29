const $ = sel => document.querySelector(sel);
const $$ = sel => document.querySelectorAll(sel);
const MAX_SIZE = 5 * 1024 * 1024;
const PERIOD = 30000;
const RADIUS = 13;
const FULL_DASH_ARRAY = 2 * Math.PI * RADIUS;

function show(el) {
  el.classList.remove("hidden");
}

function hide(el) {
  el.classList.add("hidden");
}

function fetchJSON(url, options = {}) {
  return fetch(url, options)
    .then(r => r.json().then(data => {
      if (!r.ok) throw new Error(data.message || `Error: ${r.status}`);
      return data;
    }));
}

// === COPY CODE ===
function copyCode(el) {
  navigator.clipboard.writeText(el.innerText);
  const msg = document.createElement("span");
  msg.className = "absolute -top-6 left-1/2 -translate-x-1/2 bg-primary text-primary-text text-xs px-2 py-1 rounded opacity-0 transition-opacity";
  msg.innerText = "Copied!";
  el.parentElement.style.position = "relative";
  el.parentElement.appendChild(msg);
  setTimeout(() => msg.classList.add("opacity-100"), 10);
  setTimeout(() => {
    msg.classList.remove("opacity-100");
    setTimeout(() => el.parentElement.removeChild(msg), 200);
  }, 1600);
}

// === FETCH AND UPDATE CODES ===
async function fetchTotpData(endpoint) {
  try {
    return await fetchJSON(endpoint);
  } catch (err) {
    console.error("Failed to fetch TOTP:", err);
    const table = endpoint.includes("shared") ? "#shared-totp-table" : "#totp-table";
    return [...$$(`${table} tbody tr`)].map(row => ({
      id: row.dataset.id,
      code: "Error"
    }));
  }
}

function updateCodes(data, tableSelector) {
  $$(tableSelector + " tbody tr").forEach(row => {
    const id = row.dataset.id;
    const item = data.find(i => String(i.id) === id);
    const codeCell = row.querySelector(".code-cell code");
    if (item && codeCell && codeCell.textContent !== item.code) {
      codeCell.textContent = item.code;
      codeCell.classList.toggle("text-danger", item.code === "Error");
    }
  });
}

// === ANIMATION ===
let lastCycle = 0;

function animateProgress() {
  const now = Date.now();
  const offset = FULL_DASH_ARRAY * ((now % PERIOD) / PERIOD);
  $$(".countdown-ring__progress").forEach(c => {
    c.style.strokeDashoffset = offset;
  });

  const currentCycle = Math.floor(now / PERIOD);
  if (currentCycle !== lastCycle) {
    lastCycle = currentCycle;
    fetchTotpData("/totp/list-all").then(data => updateCodes(data, "#totp-table"));
    fetchTotpData("/totp/list-shared-with-me").then(data => updateCodes(data, "#shared-totp-table"));
  }
  requestAnimationFrame(animateProgress);
}

// === QR DISPLAY ===
function showQrModalFromBlob(blob) {
  const url = URL.createObjectURL(blob);
  const overlay = document.createElement("div");
  overlay.className = "fixed inset-0 bg-black/75 z-50 flex items-center justify-center";
  overlay.onclick = () => {
    URL.revokeObjectURL(url);
    overlay.remove();
  };

  const img = document.createElement("img");
  img.src = url;
  img.className = "max-w-[90%] max-h-[90%] shadow-xl";
  img.onclick = e => e.stopPropagation();

  overlay.appendChild(img);
  document.body.appendChild(overlay);
}

// === PARSE QR ===
function parseMigrationQRCode(img, targetInput) {
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  ctx.drawImage(img, 0, 0);
  const data = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const code = jsQR(data.data, canvas.width, canvas.height);

  if (!code || !code.data.startsWith("otpauth-migration://")) {
    alert("Invalid QR code.");
    return;
  }

  targetInput.value = code.data;
}

// === SHARING ===
async function showSharedUsers(totpId) {
  const modal = $("#shared-users-modal");
  const list = $("#shared-users-list");
  show(modal);
  list.innerHTML = "<p>Loading...</p>";
  try {
    const data = await fetchJSON(`/totp/shared-users/${totpId}`);
    list.innerHTML = data.emails.length
      ? data.emails.map(email => `
          <div class="flex justify-between items-center mb-2">
            <span>${email}</span>
            <button onclick="unshareTotp(${totpId}, '${email}')" class="text-danger-500 hover:text-danger-700">
              ✕
            </button>
          </div>`).join("")
      : "<p>No users shared with.</p>";
  } catch {
    list.innerHTML = "<p>Failed to load users.</p>";
  }
}

async function unshareTotp(totpId, email) {
  const fd = new FormData();
  fd.append("totp_id", totpId);
  fd.append("email", email);

  try {
    const res = await fetch("/totp/unshare", {
      method: "POST",
      body: fd
    });
    if (!res.ok) throw new Error("Unshare failed");
    await showSharedUsers(totpId);
    const data = await fetchJSON(`/totp/shared-users/${totpId}`);
    if (data.emails.length === 0) {
      const row = $(`#totp-table tr[data-id="${totpId}"]`);
      row?.querySelector(".shared-btn")?.remove();
    }
  } catch (err) {
    console.error(err);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  animateProgress();

  const selectAll = $("#select-all");
  const exportBar = $("#export-bar");
  const exportBtn = $("#export-btn");
  const deleteBtn = $("#delete-selected-btn");
  const shareBtn = $("#share-btn");
  const exportIdsInput = $("#export-ids");
  const deleteIdsInput = $("#delete-ids");
  const shareIdsInput = $("#share-ids");
  const exportCancel = $("#export-cancel");

  const rowCheckboxes = () => $$(".row-check");

  function updateExportState() {
    const ids = [...rowCheckboxes()].filter(c => c.checked).map(c => c.value).join(",");
    [exportIdsInput, deleteIdsInput, shareIdsInput].forEach(el => el.value = ids);
    const active = ids.length > 0;
    [exportBtn, deleteBtn, shareBtn].forEach(btn => {
      btn.disabled = !active;
      btn.classList.toggle("opacity-50", !active);
      btn.classList.toggle("cursor-not-allowed", !active);
    });
    exportBar.classList.toggle("translate-y-full", !active);
    exportBar.classList.toggle("opacity-0", !active);
  }

  selectAll.addEventListener("change", () => {
    rowCheckboxes().forEach(c => c.checked = selectAll.checked);
    updateExportState();
  });

  rowCheckboxes().forEach(c => c.addEventListener("change", updateExportState));
  exportCancel.addEventListener("click", () => {
    selectAll.checked = false;
    rowCheckboxes().forEach(c => c.checked = false);
    updateExportState();
  });

  // Tabs
  const tabs = {
    "my-codes-tab": "my-codes",
    "shared-with-me-tab": "shared-with-me"
  };

  for (const [tabId, contentId] of Object.entries(tabs)) {
    $(`#${tabId}`).addEventListener("click", () => {
      Object.entries(tabs).forEach(([tid, cid]) => {
        $(`#${tid}`).classList.toggle("text-primary", tid === tabId);
        $(`#${tid}`).classList.toggle("text-gray-500", tid !== tabId);
        $(`#${tid}`).classList.toggle("border-primary", tid === tabId);
        $(`#${tid}`).classList.toggle("border-transparent", tid !== tabId);
        $(`#${cid}`).classList.toggle("hidden", cid !== contentId);
      });
      selectAll.checked = false;
      rowCheckboxes().forEach(c => c.checked = false);
      updateExportState();
    });
  }

  // Export QR
  exportBtn.addEventListener("click", async () => {
    const form = $("#export-selected-form");
    const res = await fetch(form.action, {
      method: form.method,
      body: new FormData(form),
      credentials: "same-origin"
    });
    if (!res.ok) return alert("Failed to load QR");
    const blob = await res.blob();
    showQrModalFromBlob(blob);
  });

  // Import QR
  const importModal = $("#import-modal");
  const fileInput = $("#import-file");
  const textInput = $("#import-text");

  $("#import-btn").addEventListener("click", () => {
    show(importModal);
    textInput.value = "";
    fileInput.value = null;
    textInput.focus();
  });
  $("#import-cancel").addEventListener("click", () => hide(importModal));

  fileInput.addEventListener("change", e => {
    const file = e.target.files[0];
    if (!file || !file.type.startsWith("image/") || file.size > MAX_SIZE)
      return alert("Invalid image (max 5MB)");
    const img = new Image();
    img.onload = () => {
      parseMigrationQRCode(img, textInput);
      URL.revokeObjectURL(img.src);
    };
    img.src = URL.createObjectURL(file);
  });

  window.addEventListener("paste", e => {
    if (importModal.classList.contains("hidden")) return;
    [...e.clipboardData.items].forEach(item => {
      if (item.type.startsWith("image/")) {
        const blob = item.getAsFile();
        if (blob.size > MAX_SIZE) return alert("Image too large");
        const img = new Image();
        img.onload = () => {
          parseMigrationQRCode(img, textInput);
          URL.revokeObjectURL(img.src);
        };
        img.src = URL.createObjectURL(blob);
        e.preventDefault();
      }
    });
  });

  // Share
  shareBtn.addEventListener("click", () => {
    const ids = shareIdsInput.value;
    if (!ids) return alert("Select at least one TOTP to share");
    const modal = $("#share-modal");
    show(modal);
    $("#share-email").value = "";
    $("#share-totp-ids").value = ids;
    $("#share-email").focus();
  });

  $("#share-cancel").addEventListener("click", () => hide($("#share-modal")));
  $("#shared-users-cancel").addEventListener("click", () => hide($("#shared-users-modal")));
});

window.showSharedUsers = showSharedUsers;
