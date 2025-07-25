document.addEventListener("DOMContentLoaded", () => {
  const fileInput = document.getElementById("qrcode-file");
  const secretInput = document.getElementById("secret");
  const nameInput = document.getElementById("name");
  const MAX_FILE_SIZE = 5 * 1024 * 1024;
  function showFlash(message, category = "success") {
    const containerId = "toast-container";
    let container = document.getElementById(containerId);
    if (!container) {
      container = document.createElement("div");
      container.id = containerId;
      container.className = "fixed top-24 inset-x-0 z-50 flex flex-col items-center space-y-4 pointer-events-none";
      document.body.appendChild(container);
    }
    const baseClass = "pointer-events-auto max-w-sm w-full px-4 py-3 rounded-lg shadow-lg flex items-center space-x-3 transform transition-all duration-300 border";
    const categoryClasses = {
      success: baseClass + " bg-success-200 border-success-500 text-success-700",
      error: baseClass + " bg-danger-200 border-danger-500 text-danger-700",
      warning: baseClass + " bg-warning-200 border-warning-500 text-warning-700",
      info: baseClass + " bg-info-200 border-info-500 text-info-700",
    };
    const toast = document.createElement("div");
    toast.className = `${categoryClasses[category] || categoryClasses.info} translate-y-2 opacity-0`;
    toast.innerHTML = `
      <span class="flex-1">${message}</span>
      <button class="text-xl leading-none focus:outline-none" aria-label="Close">&times;</button>
    `;
    container.appendChild(toast);
    setTimeout(() => {
      toast.classList.remove("translate-y-2", "opacity-0");
      toast.classList.add("translate-y-0", "opacity-100");
    }, 10);
    toast.querySelector("button").addEventListener("click", () => {
      container.removeChild(toast);
    });
    setTimeout(() => {
      if (container.contains(toast)) {
        toast.classList.add("opacity-0", "translate-y-2");
        setTimeout(() => container.removeChild(toast), 300);
      }
    }, 5000);
  }
  function parseQRCodeFromImage(img) {
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    canvas.width = img.naturalWidth || img.width;
    canvas.height = img.naturalHeight || img.height;
    ctx.drawImage(img, 0, 0);
    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const code = jsQR(imageData.data, canvas.width, canvas.height);
    if (code) {
      try {
        const url = new URL(code.data);
        if (url.protocol !== "otpauth:") throw new Error("Not an otpauth URL");
        if (url.hostname.toLowerCase() !== "totp") throw new Error("Only TOTP is supported");
        const secretParam = url.searchParams.get("secret");
        if (!secretParam) throw new Error("Secret not found in QR code.");
        secretInput.value = secretParam;
        const label = decodeURIComponent(url.pathname.slice(1));
        if (label) nameInput.value = label;
        showFlash("Secret key and name auto-filled from QR code!", "success");
      } catch (e) {
        showFlash(e.message || "Invalid otpauth QR code.", "error");
        console.error(e);
      }
    } else {
      showFlash("No QR code found in the image.", "error");
    }
  }
  function bindQRListeners() {
    if (!fileInput) return;
    fileInput.addEventListener("change", (event) => {
      const file = event.target.files[0];
      if (!file) return;
      if (!file.type.startsWith("image/")) {
        showFlash("Unsupported file type, please upload an image.", "error");
        return;
      }
      if (file.size > MAX_FILE_SIZE) {
        showFlash("File is too large. Maximum size is 5MB.", "error");
        return;
      }
      const img = new Image();
      img.src = URL.createObjectURL(file);
      img.onload = () => {
        parseQRCodeFromImage(img);
        URL.revokeObjectURL(img.src);
      };
    });
    window.addEventListener("paste", (event) => {
      const items = event.clipboardData.items;
      for (let i = 0; i < items.length; i++) {
        if (items[i].type.indexOf("image") !== -1) {
          const blob = items[i].getAsFile();
          if (blob.size > MAX_FILE_SIZE) {
            showFlash("Image is too large. Max 5MB allowed.", "error");
            return;
          }
          const img = new Image();
          img.src = URL.createObjectURL(blob);
          img.onload = () => {
            parseQRCodeFromImage(img);
            URL.revokeObjectURL(img.src);
          };
          event.preventDefault();
          break;
        }
      }
    });
  }
  function bindFormValidation() {
    const form = document.querySelector('form[action="/totp/create"]');
    if (!form) return;
    form.addEventListener("submit", (e) => {
      const name = nameInput.value.trim();
      const secret = secretInput.value.trim();
      if (!name || name.length > 32) {
        showFlash("Name is required and must be 32 characters or less.", "error");
        e.preventDefault();
        return;
      }
      const base32Regex = /^[A-Z2-7]{16,64}={0,6}$/i;
      if (!base32Regex.test(secret)) {
        showFlash("Secret must be a valid Base32 string.", "error");
        e.preventDefault();
        return;
      }
    });
  }
  function bindSecretSanitizer() {
    if (!secretInput) return;
    secretInput.addEventListener("input", () => {
      secretInput.value = secretInput.value.replace(/\s+/g, "");
    });
  }
  bindQRListeners();
  bindSecretSanitizer();
  bindFormValidation();
});
