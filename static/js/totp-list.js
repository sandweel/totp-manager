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

async function fetchTotpData(endpoint = "/totp/list-all") {
  try {
    const resp = await fetch(endpoint);
    if (!resp.ok) throw new Error(`Server error: ${resp.status}`);
    return await resp.json();
  } catch (err) {
    console.error("Failed to fetch TOTP data:", err);
    const tableId = endpoint === "/totp/list-all" ? "#totp-table" : "#shared-totp-table";
    const rows = document.querySelectorAll(`${tableId} tbody tr`);
    return Array.from(rows).map(row => ({
      id: row.getAttribute("data-id"),
      code: "Failed to fetch codes"
    }));
  }
}

function updateCodes(data, tableId = "#totp-table") {
  document.querySelectorAll(`${tableId} tbody tr`).forEach(row => {
    const id = row.getAttribute("data-id");
    const item = data.find(el => String(el.id) === id);
    if (item) {
      const codeCell = row.querySelector(".code-cell code");
      if (codeCell && codeCell.textContent !== item.code) {
        codeCell.textContent = item.code;
      }
      codeCell.classList.toggle("text-danger", item.code === "Error");
    }
  });
}

const RADIUS = 13;
const FULL_DASH_ARRAY = 2 * Math.PI * RADIUS;
const PERIOD = 30000;
let lastUpdatedCycle = 0;

function animateProgress() {
  const now = Date.now();
  const msIntoPeriod = now % PERIOD;
  const dashoffset = FULL_DASH_ARRAY * (msIntoPeriod / PERIOD);
  document.querySelectorAll(".countdown-ring__progress").forEach(circle => {
    circle.style.strokeDashoffset = dashoffset;
  });
  const currentCycle = Math.floor(now / PERIOD);
  if (currentCycle !== lastUpdatedCycle) {
    lastUpdatedCycle = currentCycle;
    fetchTotpData("/totp/list-all").then(data => data && updateCodes(data, "#totp-table"));
    fetchTotpData("/totp/list-shared-with-me").then(data => data && updateCodes(data, "#shared-totp-table"));
  }
  requestAnimationFrame(animateProgress);
}

function showQrModalFromBlob(blob) {
  const url = URL.createObjectURL(blob);
  const overlay = document.createElement("div");
  overlay.style.cssText = `
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.75);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    pointer-events: auto;
  `;
  overlay.addEventListener("click", () => {
    URL.revokeObjectURL(url);
    document.body.removeChild(overlay);
  });
  const img = document.createElement("img");
  img.src = url;
  img.style.cssText = `
    max-width: 90%;
    max-height: 90%;
    box-shadow: 0 0 10px rgba(0,0,0,0.5);
  `;
  img.addEventListener("click", e => e.stopPropagation());
  overlay.appendChild(img);
  document.body.appendChild(overlay);
}

async function showSharedUsers(totpId) {
  const modal = document.getElementById("shared-users-modal");
  const list = document.getElementById("shared-users-list");
  list.innerHTML = "<p>Loading...</p>";
  modal.classList.remove("hidden");

  try {
    const resp = await fetch(`/totp/shared-users/${totpId}`);
    const data = await resp.json();
    if (!resp.ok) {
      list.innerHTML = `<p>${data.message || "Error loading shared users."}</p>`;
      return;
    }
    list.innerHTML = data.emails.length
      ? data.emails.map(email => `
          <div class="flex justify-between items-center mb-2">
            <span>${email}</span>
            <button onclick="unshareTotp(${totpId}, '${email}')" class="text-danger-500 hover:text-danger-700">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
              </svg>
            </button>
          </div>
        `).join("")
      : "<p>No users shared with.</p>";
  } catch (err) {
    console.error(err);
    list.innerHTML = "<p>Error loading shared users.</p>";
  }
}

async function unshareTotp(totpId, email) {
  const formData = new FormData();
  formData.append("totp_id", totpId);
  formData.append("email", email);
  try {
    const resp = await fetch("/totp/unshare", {
      method: "POST",
      body: formData,
      credentials: "same-origin"
    });
    const data = await resp.json();
    if (resp.ok) {
      showSharedUsers(totpId);
      const row = document.querySelector(`#totp-table tr[data-id="${totpId}"]`);
      if (row && !data.emails?.length) {
        const sharedBtn = row.querySelector(".shared-btn");
        if (sharedBtn) sharedBtn.remove();
      }
    }
  } catch (err) {
    console.error(err);
  }
}

function addSharedButton(totpId) {
  const row = document.querySelector(`#totp-table tr[data-id="${totpId}"]`);
  if (row && !row.querySelector(".shared-btn")) {
    const actions = row.querySelector("td:last-child div");
    const sharedBtn = document.createElement("button");
    sharedBtn.className = "bg-info-500 hover:bg-info-400 text-white px-4 py-1.5 rounded-md text-sm shadow-sm transition shared-btn";
    sharedBtn.textContent = "Shared";
    sharedBtn.onclick = () => showSharedUsers(totpId);
    actions.appendChild(sharedBtn);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  animateProgress();

  const selectAll = document.getElementById("select-all");
  const exportBar = document.getElementById("export-bar");
  const exportBtn = document.getElementById("export-btn");
  const deleteBtn = document.getElementById("delete-selected-btn");
  const shareBtn = document.getElementById("share-btn");
  const exportIdsInput = document.getElementById("export-ids");
  const deleteIdsInput = document.getElementById("delete-ids");
  const shareIdsInput = document.getElementById("share-ids");
  const exportCancel = document.getElementById("export-cancel");

  const myCodesTab = document.getElementById("my-codes-tab");
  const sharedWithMeTab = document.getElementById("shared-with-me-tab");
  const myCodesContent = document.getElementById("my-codes");
  const sharedWithMeContent = document.getElementById("shared-with-me");

  function toggleExportBar(show) {
    exportBar.classList.toggle("translate-y-full", !show);
    exportBar.classList.toggle("opacity-0", !show);
  }

  function updateExportState() {
    const ids = Array.from(document.querySelectorAll(".row-check"))
      .filter(c => c.checked)
      .map(c => c.value)
      .join(",");

    exportIdsInput.value = ids;
    deleteIdsInput.value = ids;
    shareIdsInput.value = ids;

    const any = ids.length > 0;
    [exportBtn, deleteBtn, shareBtn].forEach(btn => {
      btn.disabled = !any;
      btn.classList.toggle("opacity-50", !any);
      btn.classList.toggle("cursor-not-allowed", !any);
    });

    toggleExportBar(any);
  }

  selectAll.addEventListener("change", e => {
    document.querySelectorAll(".row-check").forEach(c => c.checked = e.target.checked);
    updateExportState();
  });
  document.querySelectorAll(".row-check").forEach(c => c.addEventListener("change", updateExportState));

  exportCancel.addEventListener("click", () => {
    selectAll.checked = false;
    document.querySelectorAll(".row-check").forEach(c => c.checked = false);
    updateExportState();
  });

  myCodesTab.addEventListener("click", () => {
    myCodesTab.classList.add("text-primary", "border-primary");
    myCodesTab.classList.remove("text-gray-500", "border-transparent");
    sharedWithMeTab.classList.add("text-gray-500", "border-transparent");
    sharedWithMeTab.classList.remove("text-primary", "border-primary");
    myCodesContent.classList.remove("hidden");
    sharedWithMeContent.classList.add("hidden");
    selectAll.checked = false;
    document.querySelectorAll(".row-check").forEach(c => c.checked = false);
    updateExportState();
  });

  sharedWithMeTab.addEventListener("click", () => {
    sharedWithMeTab.classList.add("text-primary", "border-primary");
    sharedWithMeTab.classList.remove("text-gray-500", "border-transparent");
    myCodesTab.classList.add("text-gray-500", "border-transparent");
    myCodesTab.classList.remove("text-primary", "border-primary");
    sharedWithMeContent.classList.remove("hidden");
    myCodesContent.classList.add("hidden");
    selectAll.checked = false;
    document.querySelectorAll(".row-check").forEach(c => c.checked = false);
    updateExportState();
  });

  exportBtn.addEventListener("click", async () => {
    const form = document.getElementById("export-selected-form");
    const formData = new FormData(form);
    try {
      const res = await fetch(form.action, {
        method: form.method,
        body: formData,
        credentials: 'same-origin'
      });
      if (!res.ok) throw new Error(`Status ${res.status}`);
      const blob = await res.blob();
      showQrModalFromBlob(blob);
    } catch (err) {
      console.error(err);
      alert("Failed to load QR code!");
    }
  });

  const importBtn = document.getElementById("import-btn");
  const importModal = document.getElementById("import-modal");
  const importCancel = document.getElementById("import-cancel");
  const fileInput = document.getElementById("import-file");
  const textInput = document.getElementById("import-text");
  const shareModal = document.getElementById("share-modal");
  const shareCancel = document.getElementById("share-cancel");
  const shareForm = document.getElementById("share-form");
  const shareEmailInput = document.getElementById("share-email");
  const shareTotpIdsInput = document.getElementById("share-totp-ids");
  const sharedUsersModal = document.getElementById("shared-users-modal");
  const sharedUsersCancel = document.getElementById("shared-users-cancel");
  const MAX_SIZE = 5 * 1024 * 1024;

  function showImportModal() {
    importModal.classList.remove("hidden");
    textInput.value = "";
    fileInput.value = null;
    textInput.focus();
  }

  function hideImportModal() {
    importModal.classList.add("hidden");
  }

  function showShareModal(totpIds) {
    shareModal.classList.remove("hidden");
    shareEmailInput.value = "";
    shareTotpIdsInput.value = totpIds;
    shareEmailInput.focus();
  }

  function hideShareModal() {
    shareModal.classList.add("hidden");
  }

  function parseMigrationQRCode(img) {
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    canvas.width = img.naturalWidth || img.width;
    canvas.height = img.naturalHeight || img.height;
    ctx.drawImage(img, 0, 0);
    const data = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const code = jsQR(data.data, canvas.width, canvas.height);
    if (!code) {
      alert("No QR code found in the image.");
      return;
    }
    if (!code.data.startsWith("otpauth-migration://")) {
      alert("QR code is not a migration URI.");
      return;
    }
    textInput.value = code.data;
  }

  fileInput.addEventListener("change", e => {
    const file = e.target.files[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      alert("Please select an image file.");
      return;
    }
    if (file.size > MAX_SIZE) {
      alert("Image too large (max 5MB).");
      return;
    }
    const img = new Image();
    img.src = URL.createObjectURL(file);
    img.onload = () => {
      parseMigrationQRCode(img);
      URL.revokeObjectURL(img.src);
    };
  });

  window.addEventListener("paste", e => {
    if (importModal.classList.contains("hidden")) return;
    const items = e.clipboardData.items;
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.startsWith("image/")) {
        const blob = items[i].getAsFile();
        if (blob.size > MAX_SIZE) {
          alert("Pasted image too large (max 5MB).");
          return;
        }
        const img = new Image();
        img.src = URL.createObjectURL(blob);
        img.onload = () => {
          parseMigrationQRCode(img);
          URL.revokeObjectURL(img.src);
        };
        e.preventDefault();
        break;
      }
    }
  });

  shareBtn.addEventListener("click", () => {
    const ids = shareIdsInput.value.split(",").filter(id => id);
    if (ids.length === 0) {
      alert("Please select at least one TOTP item to share.");
      return;
    }
    showShareModal(ids.join(","));
  });

  importBtn.addEventListener("click", showImportModal);
  importCancel.addEventListener("click", hideImportModal);
  shareCancel.addEventListener("click", hideShareModal);
  sharedUsersCancel.addEventListener("click", () => sharedUsersModal.classList.add("hidden"));
});

window.showSharedUsers = showSharedUsers;