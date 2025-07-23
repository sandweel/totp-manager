import pyotp
from cryptography.fernet import Fernet
from sqlalchemy import select
from config import async_session, master_fernet
from models import TOTPItem, User

class TotpService:
    @staticmethod
    async def create(name: str, secret: str, user: User) -> TOTPItem:
        user_dek = master_fernet.decrypt(user.encrypted_dek.encode())
        user_fernet = Fernet(user_dek)
        encrypted_secret = user_fernet.encrypt(secret.encode()).decode()
        async with async_session() as session:
            item = TOTPItem(name=name, encrypted_secret=encrypted_secret, user_id=user.id)
            session.add(item)
            await session.commit()
            await session.refresh(item)
            return item

    @staticmethod
    async def list_all(user: User) -> list[dict]:
        async with async_session() as session:
            result = await session.execute(select(TOTPItem).where(TOTPItem.user_id == user.id))
            items = result.scalars().all()
        user_dek = master_fernet.decrypt(user.encrypted_dek.encode())
        user_fernet = Fernet(user_dek)
        output = []
        for item in items:
            try:
                raw_secret = user_fernet.decrypt(item.encrypted_secret.encode()).decode()
                totp = pyotp.TOTP(raw_secret)
                code = totp.now()
            except Exception:
                code = "Error"
            output.append({"id": item.id, "name": item.name, "code": code})
        return output

    @staticmethod
    async def delete(item_id: int, user: User) -> bool:
        async with async_session() as session:
            result = await session.execute(
                select(TOTPItem).where(
                    TOTPItem.id == item_id,
                    TOTPItem.user_id == user.id
                )
            )
            item = result.scalars().first()
            if not item:
                return False
            await session.delete(item)
            await session.commit()
            return True

    @staticmethod
    async def export_raw(user: User, ids: list[int]) -> list[dict]:
        if not ids:
            return []
        async with async_session() as session:
            result = await session.execute(
                select(TOTPItem).where(
                    TOTPItem.user_id == user.id,
                    TOTPItem.id.in_(ids)
                )
            )
            items = result.scalars().all()

        user_dek = master_fernet.decrypt(user.encrypted_dek.encode())
        user_fernet = Fernet(user_dek)

        out = []
        for it in items:
            secret = user_fernet.decrypt(it.encrypted_secret.encode()).decode()
            out.append({
                "name": it.name,
                "secret": secret,
                "digits": 6,
                "period": 30,
                "algorithm": "SHA1",
                "issuer": ""
            })
        return out
