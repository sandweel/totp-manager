document.addEventListener("DOMContentLoaded", () => {
const toast    = document.getElementById("toast");
const backdrop = document.getElementById("toast-backdrop");
const closeBtn = document.getElementById("toast-close");
if (!toast) return;

backdrop.classList.remove("hidden");
toast.classList.remove("translate-y-2", "opacity-0");

function hideToast() {
  toast.classList.add("opacity-0");
  backdrop.classList.add("opacity-0");
  setTimeout(() => {
    backdrop.remove();
    toast.remove();
  }, 500);
}

const timer = setTimeout(hideToast, 3000);

closeBtn.addEventListener("click", () => {
  clearTimeout(timer);
  hideToast();
});

backdrop.addEventListener("click", () => {
  clearTimeout(timer);
  hideToast();
});

toast.addEventListener("click", e => e.stopPropagation());
});

