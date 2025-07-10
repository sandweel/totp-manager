document.addEventListener('DOMContentLoaded', () => {
  const fileInput = document.getElementById('qrcode-file');
  const secretInput = document.getElementById('secret');
  const nameInput = document.getElementById('name');
  const notificationContainer = document.getElementById('notification-container');
  const MAX_FILE_SIZE = 5 * 1024 * 1024;

  function showNotification(message, type = 'success') {
    const colors = {
      success: {
        bg: 'bg-green-100',
        border: 'border border-green-400',
        text: 'text-green-700'
      },
      error: {
        bg: 'bg-red-100',
        border: 'border border-red-400',
        text: 'text-red-700'
      }
    };
    const c = colors[type] || colors.success;

    notificationContainer.innerHTML = `
      <div class="${c.bg} ${c.border} ${c.text} px-4 py-3 rounded mb-4">
        ${message}
      </div>
    `;

    setTimeout(() => {
      notificationContainer.innerHTML = '';
    }, 10000);
  }

  function parseQRCodeFromImage(img) {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    canvas.width = img.naturalWidth || img.width;
    canvas.height = img.naturalHeight || img.height;
    ctx.drawImage(img, 0, 0);
    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const code = jsQR(imageData.data, canvas.width, canvas.height);

    if (code) {
      try {
        const url = new URL(code.data);
        if (url.protocol !== 'otpauth:') throw new Error('Not an otpauth URL');
        if (url.hostname.toLowerCase() !== 'totp') throw new Error(`Unsupported OTP type: ${url.hostname}. Only TOTP (time-based) is supported.`);

        const secretParam = url.searchParams.get('secret');
        if (!secretParam) throw new Error('Secret not found in QR code');

        secretInput.value = secretParam;
        const label = decodeURIComponent(url.pathname.slice(1));
        if (label) nameInput.value = label;

        showNotification('Secret key and name auto-filled from QR code!', 'success');
      } catch (e) {
        showNotification(e.message || 'Invalid otpauth QR code.', 'error');
        console.error(e);
      }
    } else {
      showNotification('No QR code found in the image.', 'error');
    }
  }

  function bindQRListeners() {
    if (!fileInput) return;

    fileInput.addEventListener('change', (event) => {
      const file = event.target.files[0];
      if (!file) return;
      if (!file.type.startsWith('image/')) {
        showNotification('Unsupported file type, please upload an image file.', 'error');
        return;
      }
      if (file.size > MAX_FILE_SIZE) {
        showNotification('File size is too large. Maximum 5 MB.', 'error');
        return;
      }

      const img = new Image();
      img.src = URL.createObjectURL(file);
      img.onload = () => {
        parseQRCodeFromImage(img);
        URL.revokeObjectURL(img.src);
      };
    });

    window.addEventListener('paste', (event) => {
      const items = event.clipboardData.items;
      for (let i = 0; i < items.length; i++) {
        if (items[i].type.indexOf('image') !== -1) {
          const blob = items[i].getAsFile();
          if (blob.size > MAX_FILE_SIZE) {
            showNotification('File size is too large. Maximum 5 MB.', 'error');
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

  function bindSecretSanitizer() {
    if (!secretInput) return;
    secretInput.addEventListener('input', () => {
      secretInput.value = secretInput.value.replace(/\s+/g, '');
    });
  }

  bindQRListeners();
  bindSecretSanitizer();
});
