  const RADIUS = 13;
  const FULL_DASH_ARRAY = 2 * Math.PI * RADIUS;
  const PERIOD = 30000;
  let lastUpdatedCycle = 0;

  function copyCode(el) {

    navigator.clipboard.writeText(el.textContent).then(() => {
      alert('Code copied: ' + el.textContent);
    });
  }

 async function fetchTotpData() {
  try {
    const resp = await fetch('/api/totp');
    if (!resp.ok) {
      throw new Error(`Server error: ${resp.status}`);
    }
    return await resp.json();
  } catch (err) {
    console.error("Failed to fetch TOTP data:", err);

    const rows = document.querySelectorAll("#totp-table tbody tr");
    const errorData = Array.from(rows).map(row => ({
      id: row.getAttribute("data-id"),
      code: "Failed to fetch codes"
    }));
    return errorData;
  }
}

  function updateCodes(data) {
    const rows = document.querySelectorAll("#totp-table tbody tr");
    rows.forEach(row => {
      const id = row.getAttribute("data-id");
      const item = data.find(el => el.id == id);
      if (item) {
        const codeCell = row.querySelector(".code-cell code");
        if (codeCell.textContent !== item.code) {
          codeCell.textContent = item.code;
        }
        if (item.code === "Error") {
          codeCell.classList.add("text-red-600");
        } else {
          codeCell.classList.remove("text-red-600");
        }
      }
    });
  }

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
      fetchTotpData().then(data => {
        if (data) updateCodes(data);
      });
    }

    requestAnimationFrame(animateProgress);
  }

  animateProgress();

    function copyCode(el) {
      navigator.clipboard.writeText(el.innerText);
      let msg = document.createElement('span');
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