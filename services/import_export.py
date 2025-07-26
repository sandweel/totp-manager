import base64
import io
import urllib.parse
import qrcode
from services.otp_migration_pb2 import MigrationPayload

ALG_MAP_INV = {'SHA1': 1, 'SHA256': 2, 'SHA512': 3}
DIG_MAP_INV = {6: 1, 8: 2}
TYPE_MAP_INV = {'hotp': 1, 'totp': 2}

def build_migration_uri(items: list[dict]) -> str:
    if len(items) == 1:
        t = items[0]
        return (
            f"otpauth://totp/"
            f"{urllib.parse.quote(t['issuer'])}:"
            f"{urllib.parse.quote(t['account'])}"
            f"?secret={t['secret']}&issuer={urllib.parse.quote(t['issuer'])}"
        )
    payload = MigrationPayload()
    payload.version = 1
    payload.batch_size = len(items)
    payload.batch_index = 0
    payload.batch_id = 0

    for t in items:
        otp = payload.otp_parameters.add()
        otp.name      = t['account']
        otp.issuer    = t['issuer']
        otp.secret    = base64.b32decode(t['secret'].upper())
        otp.type      = 2

        otp.algorithm = ALG_MAP_INV.get(t.get('algorithm', 'SHA1'), 1)
        otp.digits    = DIG_MAP_INV.get(t.get('digits', 6), 1)


    raw = payload.SerializeToString()
    b64 = base64.b64encode(raw).decode()
    data = urllib.parse.quote(b64, safe='')
    return f"otpauth-migration://offline?data={data}"


def decode_migration_uri(uri: str) -> list[str]:
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme == "otpauth-migration":
        qs = urllib.parse.parse_qs(parsed.query)
        data = qs.get("data", [None])[0]
        if not data:
            raise ValueError("No migration data in URI.")
        raw = base64.urlsafe_b64decode(data + '=' * (-len(data) % 4))
        payload = MigrationPayload()
        payload.ParseFromString(raw)

        results = []
        for otp in payload.otp_parameters:
            secret = base64.b32encode(otp.secret).decode().rstrip('=')
            issuer = urllib.parse.quote(otp.issuer)
            name   = urllib.parse.quote(otp.name)
            uri    = (
                f"otpauth://totp/{issuer}:{name}"
                f"?secret={secret}&issuer={issuer}"
            )
            results.append(uri)
        return results
    if uri.startswith("otpauth://"):
        return [uri]

    raise ValueError("Unsupported URI format.")


def build_qr_png(items: list[dict]) -> bytes:
    migration_uri = build_migration_uri(items)
    qr = qrcode.QRCode(
        version=10,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(migration_uri)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
