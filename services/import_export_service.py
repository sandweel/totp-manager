from typing import List, Tuple, Optional
from urllib.parse import urlparse, parse_qs, unquote
from services.import_export import decode_migration_uri
from services.totp_service import TotpService
from services.validator import validate_totp


class ImportExportService:
    @staticmethod
    async def import_totp_uris(uri: str, user) -> Tuple[int, Optional[str]]:
        """
        Import TOTP items from URI
        Returns: (created_count, error_message)
        """
        try:
            otp_uris = decode_migration_uri(uri.strip())
            created = 0
            
            for otp_uri in otp_uris:
                success, error = await ImportExportService._parse_and_create_totp(otp_uri, user)
                if success:
                    created += 1
                else:
                    return 0, error
            
            return created, None
            
        except Exception as e:
            return 0, str(e)

    @staticmethod
    async def _parse_and_create_totp(otp_uri: str, user) -> Tuple[bool, Optional[str]]:
        """
        Parse single TOTP URI and create item
        Returns: (success, error_message)
        """
        try:
            p = urlparse(otp_uri)
            if p.scheme != "otpauth" or p.hostname.lower() != "totp":
                return False, f"Unsupported URI: {otp_uri}"
            
            label = unquote(p.path[1:])
            issuer_field, account = label.split(":", 1)
            qs = parse_qs(p.query)
            secret = qs.get("secret", [None])[0]
            
            if not secret:
                return False, "Secret not found in URI."
            
            issuer_qs = qs.get("issuer", [issuer_field])[0]
            
            # Validate TOTP data
            error_msg = validate_totp(account, issuer_qs, secret)
            if error_msg:
                return False, error_msg
            
            # Create TOTP item
            await TotpService.create(account, issuer_qs, secret, user)
            return True, None
            
        except Exception as e:
            return False, f"Error parsing URI: {str(e)}"
