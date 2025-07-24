// --------- Constants for TOTP ring ----------
const RADIUS = 13;
const FULL_DASH_ARRAY = 2 * Math.PI * RADIUS;
const PERIOD = 30000;
let lastUpdatedCycle = 0;

// --------- Copy code helper ----------
function copyCode(el) {
  navigator.clipboard.writeText(el.innerText);
  const msg = document.createElement('span');
  msg.className = 'absolute -top-6 left-1/2 -translate-x-1/2 bg-primary text-white text-xs px-2 py-1 rounded opacity-0 transition-opacity';
  msg.innerText = 'Copied!';
  el.parentElement.style.position = 'relative';
  el.parentElement.appendChild(msg);
  setTimeout(() => msg.classList.add('opacity-100'), 10);
  setTimeout(() => {
    msg.classList.remove('opacity-100');
    setTimeout(() => el.parentElement.removeChild(msg), 200);
  }, 1600);
}

// --------- Fetch & update codes ----------
async function fetchTotpData() {
  try {
    const resp = await fetch('/api/totp');
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
      if (item.code === "Error") codeCell.classList.add("text-red-600");
      else codeCell.classList.remove("text-red-600");
    }
  });
}

// --------- Progress ring animation ----------
function animateProgress() {
  const now = Date.now();
  const msIntoPeriod = now % PERIOD;
  const progress = msIntoPeriod / PERIOD;
  const dashoffset = FULL_DASH_ARRAY * progress;

  document.querySelectorAll('.countdown-ring__progress').forEach(circle => {
    circle.style.strokeDashoffset = dashoffset;
  });

  const currentCycle = Math.floor(now / PERIOD);
  if (currentCycle !== lastUpdatedCycle) {
    lastUpdatedCycle = currentCycle;
    fetchTotpData().then(data => data && updateCodes(data));
  }

  requestAnimationFrame(animateProgress);
}

// --------- Export bar logic ----------
document.addEventListener('DOMContentLoaded', () => {
  // start ring animation
  animateProgress();

  const selectAll       = document.getElementById('select-all');
  const exportBar       = document.getElementById('export-bar');
  const exportBtn       = document.getElementById('export-btn');
  const exportIdsInput  = document.getElementById('export-ids');
  const exportCancel    = document.getElementById('export-cancel');

  function getChecks() {
    return document.querySelectorAll('.row-check');
  }

  function toggleExportBar(show) {
    if (!exportBar) return;
    if (show) {
      exportBar.classList.remove('translate-y-full', 'opacity-0');
    } else {
      exportBar.classList.add('translate-y-full', 'opacity-0');
    }
  }

  function updateExportState() {
    const checks = getChecks();
    const ids = Array.from(checks).filter(c => c.checked).map(c => c.value);
    if (exportBtn) exportBtn.disabled = ids.length === 0;
    if (exportIdsInput) exportIdsInput.value = ids.join(',');
    toggleExportBar(ids.length > 0);
  }

  if (selectAll) {
    selectAll.addEventListener('change', (e) => {
      getChecks().forEach(c => { c.checked = e.target.checked; });
      updateExportState();
    });
  }

  getChecks().forEach(c => c.addEventListener('change', updateExportState));

  if (exportCancel) {
    exportCancel.addEventListener('click', () => {
      if (selectAll) selectAll.checked = false;
      getChecks().forEach(c => { c.checked = false; });
      updateExportState();
    });
  }

  // init state
  updateExportState();
});
