import re
from functools import lru_cache
from typing import Optional
from user_agents import parse as ua_parse


_ARCH_PATTERNS = [
    (r"(WOW64|Win64; x64|x64;|x86_64|amd64)", "x64"),
    (r"(i686|i386|x86(?!_64))", "x86"),
    (r"(aarch64|arm64|ARM64)", "arm64"),
    (r"(armv8l|armv8)", "armv8"),
    (r"(armv7l|armv7)", "armv7"),
]

_BROWSER_OVERRIDES = [
    (r"\bBrave/", "Brave"),
    (r"\bVivaldi/", "Vivaldi"),
    (r"\bOPR/", "Opera"),
    (r"\bEdgA/", "Edge (Android)"),
    (r"\bEdgiOS/", "Edge (iOS)"),
    (r"\bEdg/", "Edge"),
    (r"\bSamsungBrowser/", "Samsung Internet"),
    (r"\bDuckDuckGo/", "DuckDuckGo"),
    (r"\bArc/", "Arc"),
    (r"\bChromium/", "Chromium"),
    (r"\bFxiOS/", "Firefox (iOS)"),
    (r"\bCriOS/", "Chrome (iOS)"),
]

_MACOS_CODENAMES = {
    "10.15": "Catalina",
    "11": "Big Sur",
    "12": "Monterey",
    "13": "Ventura",
    "14": "Sonoma",
    "15": "Sequoia",
}

def _detect_arch(ua: str) -> Optional[str]:
    for pat, arch in _ARCH_PATTERNS:
        if re.search(pat, ua, flags=re.I):
            return arch
    return None

def _detect_locale(ua: str) -> Optional[str]:
    m = re.search(r"([a-z]{2,3}[-_][A-Z]{2})", ua)
    return m.group(1) if m else None

def _detect_app_wrapper(ua: str) -> Optional[str]:
    pairs = [
        ("HeadlessChrome", "Headless"),
        ("Electron", "Electron"),
        ("Instagram", "Instagram In-App"),
        ("FBAV", "Facebook In-App"),
        ("FBAN", "Facebook In-App"),
        ("WhatsApp", "WhatsApp In-App"),
        ("Telegram", "Telegram In-App"),
        ("Line/", "LINE In-App"),
        ("Snapchat", "Snapchat In-App"),
        ("Twitter", "X/Twitter In-App"),
        ("wv)", "Android WebView"),
        ("; wv", "Android WebView"),
        ("GSA/", "Google App WebView"),
    ]
    low = ua.lower()
    for needle, label in pairs:
        if needle.lower() in low:
            return label
    return None

def _device_icon_and_type(ua_obj) -> tuple[str, str]:
    if ua_obj.is_tablet:
        return "📱", "Tablet"
    if ua_obj.is_mobile:
        return "📱", "Mobile"
    if ua_obj.is_pc:
        return "🖥️", "Desktop"
    return "📦", "Other"

def _engine_from_tokens(ua_raw: str, fam: str) -> str:
    s = ua_raw.lower()
    f = (fam or "").lower()
    if "applewebkit" in s and ("safari" in f or "mobile safari" in f or "crios" in s or "edgios" in s):
        return "WebKit"
    if "firefox" in s or f == "firefox":
        return "Gecko"
    if any(tok in s for tok in ["edg/", "opr/", "chrome/", "samsungbrowser", "brave/", "chromium", "arc/"]):
        return "Blink"
    if "applewebkit" in s:
        return "WebKit"
    if "gecko" in s:
        return "Gecko"
    return "Unknown"

def _override_browser_name(raw: str, family: str) -> str:
    for pat, label in _BROWSER_OVERRIDES:
        m = re.search(pat, raw)
        if m:
            ver = None
            try:
                ver = re.search(rf"{pat.strip('()').strip('\\b')}\s*([0-9][\w\.\-_]*)", raw)
            except re.error:
                ver = None
            if ver and ver.group(1):
                return f"{label} {ver.group(1)}"
            return label
    return family

def _nice_macos(version_string: str) -> Optional[str]:
    if not version_string:
        return None
    major_minor = ".".join(version_string.split(".")[:2])
    codename = _MACOS_CODENAMES.get(major_minor) or _MACOS_CODENAMES.get(version_string.split(".")[0])
    if codename:
        return f"macOS {codename} {version_string}"
    return f"macOS {version_string}"

def _nice_windows(raw_ua: str, family: str, ver_str: str) -> str:
    if "Windows NT 10.0" in raw_ua:
        return "Windows 10/11"
    if family and ver_str:
        return f"{family} {ver_str}"
    return family or "Windows"

def _os_label(raw_ua: str, family: str, ver_str: str, arch: Optional[str]) -> str:
    icon = "🪟" if "Windows" in family else ("🍎" if "Mac" in family or "iOS" in family else ("🤖" if "Android" in family else ("🐧" if "Linux" in family else "💻")))
    if "Mac" in family:
        nice = _nice_macos(ver_str) or "macOS"
        chip = " (Apple Silicon)" if arch in {"arm64"} else (" (Intel)" if arch in {"x64","x86"} else "")
        return f"{icon} {nice}{chip}"
    if "iOS" in family or "iPadOS" in family:
        return f"{icon} {family} {ver_str}".strip()
    if "Android" in family:
        return f"{icon} Android {ver_str or ''}".strip()
    if "Windows" in family:
        base = _nice_windows(raw_ua, family, ver_str)
        return f"{icon} {base}{(' ('+arch+')') if arch else ''}"
    return f"{icon} {family}{(' ' + ver_str) if ver_str else ''}{(' ('+arch+')') if arch else ''}".strip()

def _device_label(ua_obj) -> Optional[str]:
    if ua_obj.is_mobile or ua_obj.is_tablet:
        brand = (ua_obj.device.brand or "").strip()
        model = (ua_obj.device.model or "").strip()
        fam = (ua_obj.device.family or "").strip()
        pretty = None
        if re.match(r"SM\-S92\d", model):  # S24 линия
            pretty = "Samsung Galaxy S24"
        elif re.match(r"SM\-S91\d", model):
            pretty = "Samsung Galaxy S23"
        elif re.match(r"SM\-S90\d", model):
            pretty = "Samsung Galaxy S22"
        if pretty:
            return pretty
        label = " ".join(x for x in [brand, model] if x) or fam
        if label and label.lower() != "other":
            return label
    return None

@lru_cache(maxsize=4096)
def _format_cached(ua_string: str) -> str:
    ua = ua_parse(ua_string)
    icon, dev_type = _device_icon_and_type(ua)

    arch = _detect_arch(ua_string)
    os_family = ua.os.family or "Unknown OS"
    os_ver = ua.os.version_string or ""
    os_part = _os_label(ua_string, os_family, os_ver, arch)

    base_family = ua.browser.family or "Unknown Browser"
    base_ver = ua.browser.version_string or ""
    family_over = _override_browser_name(ua_string, base_family)
    if re.search(r"\b\d", family_over):
        br_name = family_over
    else:
        br_name = f"{family_over}{(' ' + base_ver) if base_ver else ''}"

    engine = _engine_from_tokens(ua_string, base_family)
    browser_part = f"{br_name} ({engine})"

    dev_details = _device_label(ua)
    loc = _detect_locale(ua_string)
    wrapper = _detect_app_wrapper(ua_string)

    parts = [f"{icon} {dev_type}", os_part, browser_part]
    if dev_details:
        parts.append(f"Device: {dev_details}")
    if loc:
        parts.append(f"Locale: {loc}")
    if wrapper:
        parts.append(f"App: {wrapper}")

    return " • ".join(parts)

def ua_pretty(ua_string: Optional[str]) -> str:
    if not ua_string:
        return "—"
    try:
        return _format_cached(ua_string)
    except Exception:
        return ua_string
