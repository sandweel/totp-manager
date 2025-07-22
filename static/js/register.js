function initPasswordStrengthMeter() {
  const passwordInput = document.getElementById("password");
  const bar = document.getElementById("password-strength-bar");

  const rules = {
    length: document.getElementById("rule-length"),
    digit: document.getElementById("rule-digit"),
    upper: document.getElementById("rule-upper"),
    lower: document.getElementById("rule-lower"),
    special: document.getElementById("rule-special"),
  };

  passwordInput.addEventListener("input", function () {
    const value = passwordInput.value;
    let score = 0;

    const checks = {
      length: value.length >= 10,
      digit: /\d/.test(value),
      upper: /[A-Z]/.test(value),
      lower: /[a-z]/.test(value),
      special: /[!@#$%^&*(),._?":{}|<>]/.test(value),
    };

    Object.keys(checks).forEach((key) => {
      if (checks[key]) {
        rules[key].classList.add("text-green-600");
        rules[key].classList.remove("text-gray-600");
        score++;
      } else {
        rules[key].classList.remove("text-green-600");
        rules[key].classList.add("text-gray-600");
      }
    });

    const percentage = (score / 5) * 100;
    bar.style.width = percentage + "%";

    if (score === 5) {
      bar.className = "h-full bg-green-500 transition-all duration-300";
    } else if (score >= 3) {
      bar.className = "h-full bg-yellow-400 transition-all duration-300";
    } else {
      bar.className = "h-full bg-red-500 transition-all duration-300";
    }
  });
}