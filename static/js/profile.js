// Profile page JavaScript

document.addEventListener('DOMContentLoaded', function() {
  // Initialize password strength meter if available
  if (typeof initPasswordStrengthMeter === 'function') {
    initPasswordStrengthMeter();
  }
  
  // Tab switching functionality
  const tabs = document.querySelectorAll('.tab-button');
  const tabContents = document.querySelectorAll('.tab-content');
  
  function switchTab(targetTab) {
    tabs.forEach(t => {
      t.classList.remove('bg-primary', 'text-primary-text');
      t.classList.add('text-gray-600', 'hover:bg-gray-100');
    });
    
    tabContents.forEach(content => content.classList.add('hidden'));
    
    const targetTabButtons = document.querySelectorAll(`[data-tab="${targetTab}"]`);
    targetTabButtons.forEach(button => {
      button.classList.remove('text-gray-600', 'hover:bg-gray-100');
      button.classList.add('bg-primary', 'text-primary-text');
    });
    
    const targetContent = document.getElementById(targetTab);
    if (targetContent) {
      targetContent.classList.remove('hidden');
    }
    
    const url = new URL(window.location);
    url.searchParams.set('tab', targetTab);
    window.history.replaceState({}, '', url);
  }
  
  // Set active tab from URL or default to 'security'
  const urlParams = new URLSearchParams(window.location.search);
  const activeTab = urlParams.get('tab') || 'security';
  
  switchTab(activeTab);

  // Add click handlers to tabs
  tabs.forEach(tab => {
    tab.addEventListener('click', function() {
      const targetTab = this.getAttribute('data-tab');
      switchTab(targetTab);
    });
  });
});

// API Key Modal functions
function showCreateKeyModal() {
  const modal = document.getElementById('createKeyModal');
  if (modal) {
    modal.classList.remove('hidden');
  }
}

function hideCreateKeyModal() {
  const modal = document.getElementById('createKeyModal');
  if (modal) {
    modal.classList.add('hidden');
  }
}

// Copy API key to clipboard
function copyApiKey(event) {
  const apiKeyElement = document.getElementById('api-key-value');
  if (!apiKeyElement) {
    alert('API key not found');
    return;
  }
  
  const apiKey = apiKeyElement.textContent.trim();
  
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(apiKey).then(() => {
      const button = event ? event.target : document.querySelector('#new-api-key-box button');
      if (button) {
        const originalText = button.textContent;
        button.textContent = 'Copied!';
        button.classList.add('bg-green-600', 'hover:bg-green-700');
        button.classList.remove('bg-yellow-600', 'hover:bg-yellow-700');
        
        setTimeout(() => {
          button.textContent = originalText;
          button.classList.remove('bg-green-600', 'hover:bg-green-700');
          button.classList.add('bg-yellow-600', 'hover:bg-yellow-700');
        }, 2000);
      }
    }).catch(err => {
      console.error('Failed to copy:', err);
      fallbackCopy(apiKey);
    });
  } else {
    fallbackCopy(apiKey);
  }
}

// Fallback copy function for older browsers
function fallbackCopy(text) {
  const textArea = document.createElement('textarea');
  textArea.value = text;
  textArea.style.position = 'fixed';
  textArea.style.left = '-999999px';
  document.body.appendChild(textArea);
  textArea.select();
  try {
    document.execCommand('copy');
    alert('API key copied to clipboard!');
  } catch (err) {
    alert('Failed to copy. Please select and copy manually.');
  }
  document.body.removeChild(textArea);
}

// Close modal on outside click
document.addEventListener('DOMContentLoaded', function() {
  const modal = document.getElementById('createKeyModal');
  if (modal) {
    modal.addEventListener('click', function(e) {
      if (e.target === this) {
        hideCreateKeyModal();
      }
    });
  }
});

