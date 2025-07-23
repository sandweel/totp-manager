import base64
import io
import qrcode
from urllib.parse import quote

def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        to_write = n & 0x7F
        n >>= 7
        if n:
            out.append(to_write | 0x80)
        else:
            out.append(to_write)
            break
    return bytes(out)

def _field(tag: int, wire_type: int) -> bytes:
    return _varint((tag << 3) | wire_type)

def _len_delimited(tag: int, payload: bytes) -> bytes:
    return _field(tag, 2) + _varint(len(payload)) + payload

def _varint_field(tag: int, value: int) -> bytes:
    return _field(tag, 0) + _varint(value)

ALGO_SHA1  = 1
DIGITS_SIX = 1
TYPE_TOTP  = 2

def _b32_to_bytes(secret: str) -> bytes:
    s = secret.replace(" ", "").upper()
    s += "=" * ((8 - len(s) % 8) % 8)
    return base64.b32decode(s)

def encode_otp_parameters(item: dict) -> bytes:
    parts = []
    # 1: secret (bytes)
    parts.append(_len_delimited(1, _b32_to_bytes(item["secret"])))
    # 2: name (string)
    parts.append(_len_delimited(2, item["name"].encode()))
    # 3: issuer (string) optional
    issuer = item.get("issuer")
    if issuer:
        parts.append(_len_delimited(3, issuer.encode()))
    # 4: algorithm (varint)
    parts.append(_varint_field(4, ALGO_SHA1))
    # 5: digits (varint)
    parts.append(_varint_field(5, DIGITS_SIX))
    # 6: type (varint)
    parts.append(_varint_field(6, TYPE_TOTP))
    # 8: period (varint)
    parts.append(_varint_field(8, item.get("period", 30)))
    return b"".join(parts)

def encode_migration_payload(items: list[dict]) -> bytes:
    parts = []
    for it in items:
        parts.append(_len_delimited(1, encode_otp_parameters(it)))
    parts.append(_varint_field(2, 1))
    parts.append(_varint_field(3, len(items)))
    parts.append(_varint_field(4, 0))
    parts.append(_varint_field(5, 1))
    return b"".join(parts)

def build_ga_link(items: list[dict]) -> str:
    payload = encode_migration_payload(items)
    data_b64 = base64.b64encode(payload).decode()
    return f"otpauth-migration://offline?data={quote(data_b64, safe='')}"

def build_ga_qr_png(items: list[dict]) -> bytes:
    link = build_ga_link(items)
    img = qrcode.make(link)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
