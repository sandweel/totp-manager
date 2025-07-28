from sqlalchemy import select, delete
from models import TOTPItem, User, SharedTOTP
from config import async_session, master_fernet
from cryptography.fernet import Fernet
import pyotp


class TotpService:
    @staticmethod
    async def create(account: str, issuer: str, secret: str, user: User):
        async with async_session() as session:
            user_fernet = Fernet(master_fernet.decrypt(user.encrypted_dek.encode()))
            encrypted_secret = user_fernet.encrypt(secret.encode()).decode()
            totp_item = TOTPItem(account=account, issuer=issuer, encrypted_secret=encrypted_secret, user_id=user.id)
            session.add(totp_item)
            await session.commit()
            return totp_item

    @staticmethod
    async def list_all(user: User):
        async with async_session() as session:
            user_fernet = Fernet(master_fernet.decrypt(user.encrypted_dek.encode()))
            result = await session.execute(select(TOTPItem).where(TOTPItem.user_id == user.id))
            totps = result.scalars().all()
            output = []
            for totp in totps:
                try:
                    secret = user_fernet.decrypt(totp.encrypted_secret.encode()).decode()
                    code = pyotp.TOTP(secret).now()
                    shared_result = await session.execute(select(SharedTOTP).where(SharedTOTP.totp_item_id == totp.id))
                    shared_with = shared_result.scalars().all()
                    output.append({
                        "id": totp.id,
                        "account": totp.account,
                        "issuer": totp.issuer,
                        "code": code,
                        "is_shared": len(shared_with) > 0
                    })
                except Exception:
                    output.append({
                        "id": totp.id,
                        "account": totp.account,
                        "issuer": totp.issuer,
                        "code": "Error",
                        "is_shared": False
                    })
            return output

    @staticmethod
    async def list_shared_with_me(user: User):
        async with async_session() as session:
            user_fernet = Fernet(master_fernet.decrypt(user.encrypted_dek.encode()))
            result = await session.execute(
                select(TOTPItem, SharedTOTP, User.email)
                .join(SharedTOTP, TOTPItem.id == SharedTOTP.totp_item_id)
                .join(User, TOTPItem.user_id == User.id)
                .where(SharedTOTP.shared_with_user_id == user.id)
            )
            rows = result.all()
            output = []

            for totp, shared_totp, owner_email in rows:
                try:
                    secret = user_fernet.decrypt(shared_totp.encrypted_secret.encode()).decode()
                    code = pyotp.TOTP(secret).now()
                    output.append({
                        "id": totp.id,
                        "account": totp.account,
                        "owner_email": owner_email,
                        "issuer": totp.issuer,
                        "code": code
                    })
                except Exception as e:
                    print(f"Error decrypting shared TOTP {totp.id}: {e}")
                    output.append({
                        "id": totp.id,
                        "account": totp.account,
                        "owner_email": owner_email,
                        "issuer": totp.issuer,
                        "code": "Error"
                    })
            return output

    @staticmethod
    async def delete(item_id: int, user: User):
        async with async_session() as session:
            result = await session.execute(
                select(TOTPItem).where(TOTPItem.id == item_id, TOTPItem.user_id == user.id)
            )
            totp_item = result.scalars().first()
            if totp_item:
                await session.execute(
                    delete(SharedTOTP).where(SharedTOTP.totp_item_id == item_id)
                )
                await session.delete(totp_item)
                await session.commit()
                return True
            return False

    @staticmethod
    async def export_raw(user: User, ids: list[int]):
        async with async_session() as session:
            user_fernet = Fernet(master_fernet.decrypt(user.encrypted_dek.encode()))
            result = await session.execute(
                select(TOTPItem).where(TOTPItem.id.in_(ids), TOTPItem.user_id == user.id)
            )
            totps = result.scalars().all()
            return [{
                "account": t.account,
                "issuer": t.issuer,
                "secret": user_fernet.decrypt(t.encrypted_secret.encode()).decode()
            } for t in totps]

    @staticmethod
    async def share_totp(totp_ids: list[int], email: str, user: User):
        async with async_session() as session:
            result = await session.execute(select(User).where(User.email == email))
            target_user = result.scalars().first()
            if not target_user:
                return 0, "User with this email does not exist."
            if target_user.id == user.id:
                return 0, "Cannot share with yourself."

            result = await session.execute(
                select(TOTPItem).where(TOTPItem.id.in_(totp_ids), TOTPItem.user_id == user.id)
            )
            totp_items = result.scalars().all()
            if not totp_items:
                return 0, "No valid TOTP items found."

            owner_fernet = Fernet(master_fernet.decrypt(user.encrypted_dek.encode()))
            recipient_fernet = Fernet(master_fernet.decrypt(target_user.encrypted_dek.encode()))
            shared_count = 0
            already_shared = []

            for totp_item in totp_items:
                result = await session.execute(
                    select(SharedTOTP).where(
                        SharedTOTP.totp_item_id == totp_item.id,
                        SharedTOTP.shared_with_user_id == target_user.id
                    )
                )
                if result.scalars().first():
                    already_shared.append(f"{totp_item.account} ({totp_item.issuer})")
                    continue
                secret = owner_fernet.decrypt(totp_item.encrypted_secret.encode()).decode()
                encrypted_secret = recipient_fernet.encrypt(secret.encode()).decode()
                shared_totp = SharedTOTP(
                    totp_item_id=totp_item.id,
                    shared_with_user_id=target_user.id,
                    encrypted_secret=encrypted_secret
                )
                session.add(shared_totp)
                shared_count += 1

            if shared_count > 0:
                await session.commit()

            if already_shared:
                return shared_count, f"Shared {shared_count} item(s). Already shared: {', '.join(already_shared)}."
            return shared_count, f"Shared {shared_count} item(s) successfully!"

    @staticmethod
    async def get_shared_users(totp_id: int, user: User):
        async with async_session() as session:
            # Verify the TOTP item belongs to the user
            result = await session.execute(
                select(TOTPItem).where(TOTPItem.id == totp_id, TOTPItem.user_id == user.id)
            )
            if not result.scalars().first():
                return None, "TOTP item not found."

            # Get users with whom the TOTP is shared
            result = await session.execute(
                select(User.email).join(SharedTOTP, SharedTOTP.shared_with_user_id == User.id)
                .where(SharedTOTP.totp_item_id == totp_id)
            )
            emails = result.scalars().all()
            return emails, None

    @staticmethod
    async def unshare_totp(totp_id: int, email: str, user: User):
        async with async_session() as session:
            # Verify the TOTP item belongs to the user
            result = await session.execute(
                select(TOTPItem).where(TOTPItem.id == totp_id, TOTPItem.user_id == user.id)
            )
            if not result.scalars().first():
                return False, "TOTP item not found."

            # Find the target user
            result = await session.execute(select(User).where(User.email == email))
            target_user = result.scalars().first()
            if not target_user:
                return False, "User with this email does not exist."

            # Delete the shared record
            result = await session.execute(
                delete(SharedTOTP).where(
                    SharedTOTP.totp_item_id == totp_id,
                    SharedTOTP.shared_with_user_id == target_user.id
                )
            )
            await session.commit()
            return result.rowcount > 0, "TOTP sharing removed!" if result.rowcount > 0 else "TOTP not shared with this user."