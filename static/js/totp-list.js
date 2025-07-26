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
async function fetchTotpData() {
  try {
    const resp = await fetch("/totp/list-all");
    if (!resp.ok) throw new Error(`Server error: ${resp.status}`);
    return await resp.json();
  } catch (err) {
    console.error("Failed to fetch TOTP data:", err);
    const rows = document.querySelectorAll("#totp-table tbody tr");
    return Array.from(rows).map(row => ({
      id: row.getAttribute("data-id"),
      code: "Failed to fetch codes"
    }));
  }
}
function updateCodes(data) {
  document.querySelectorAll("#totp-table tbody tr").forEach(row => {
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
    fetchTotpData().then(data => data && updateCodes(data));
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

document.addEventListener("DOMContentLoaded", () => {
  animateProgress();

  const selectAll      = document.getElementById("select-all");
  const exportBar      = document.getElementById("export-bar");
  const exportBtn      = document.getElementById("export-btn");
  const deleteBtn      = document.getElementById("delete-selected-btn");
  const exportIdsInput = document.getElementById("export-ids");
  const deleteIdsInput = document.getElementById("delete-ids");
  const exportCancel   = document.getElementById("export-cancel");

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

    const any = ids.length > 0;
    [exportBtn, deleteBtn].forEach(btn => {
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

  exportBtn.addEventListener("click", async () => {
    const form = document.getElementById("export-selected-form");
    const formData = new FormData(form);
    try {
      const res = await fetch(form.action, {
        method: form.method,
        body: formData
      });
      if (!res.ok) throw new Error(`Status ${res.status}`);
      const blob = await res.blob();
      showQrModalFromBlob(blob);
    } catch (err) {
      console.error(err);
      alert("Failed to load QR code!");
    }
  });

  const importBtn    = document.getElementById("import-btn");
  const importModal  = document.getElementById("import-modal");
  const importText   = document.getElementById("import-text");
  const importCancel = document.getElementById("import-cancel");

  importBtn.addEventListener("click", () => {
    importModal.classList.remove("hidden");
    importText.focus();
  });
  importCancel.addEventListener("click", () => {
    importModal.classList.add("hidden");
    importText.value = "";
  });
});
