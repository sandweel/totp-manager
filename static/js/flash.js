function showFlash(message, category = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const base =
    "pointer-events-auto max-w-sm w-full px-4 py-3 rounded-lg shadow-lg flex items-center space-x-3 transform transition-all duration-300 border";
  let cls = base;

  switch (category) {
    case "success":
      cls += " bg-success-200 border-success-500 text-success-700";
      break;
    case "error":
      cls += " bg-danger-200 border-danger-500 text-danger-700";
      break;
    case "warning":
      cls += " bg-warning-200 border-warning-500 text-warning-700";
      break;
    case "info":
      cls += " bg-info-200 border-info-500 text-info-700";
      break;
    default:
      cls += " bg-gray-200 border-gray-700 text-gray-800";
  }

  const toast = document.createElement("div");
  toast.className = cls + " translate-y-2 opacity-0";
  toast.innerHTML = `
    <span class="flex-1">${message}</span>
    <button class="text-xl leading-none focus:outline-none">&times;</button>
  `;

  toast.querySelector("button").addEventListener("click", () => {
    toast.remove();
  });

  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.remove("translate-y-2", "opacity-0");
  }, 50);
  setTimeout(() => {
    toast.classList.add("opacity-0", "translate-y-2");
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

window.showFlash = showFlash;
