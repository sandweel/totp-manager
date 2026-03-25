import os
import time
import asyncio
import subprocess
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import inspect
from urllib.parse import quote_plus

load_dotenv()

MYSQL_HOST: str = os.getenv("MYSQL_HOST", "db")
MYSQL_PORT: str = os.getenv("MYSQL_PORT", "3306")
MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE")
MYSQL_USER: str = os.getenv("MYSQL_USER")
MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD")

password = quote_plus(MYSQL_PASSWORD or "")

DATABASE_URL = (
    f"mysql+asyncmy://{MYSQL_USER}:"
    f"{password}@"
    f"{MYSQL_HOST}:"
    f"{MYSQL_PORT}/"
    f"{MYSQL_DATABASE}"
)

async def main():
    engine = create_async_engine(DATABASE_URL)

    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())

    await engine.dispose()

    if 'alembic_version' not in tables:
        print("First run: creating initial migration...")
        subprocess.run(["alembic", "revision", "--autogenerate", "-m", "initial migration"], check=True)
        subprocess.run(["alembic", "upgrade", "head"], check=True)
    else:
        print("Migrations already applied, skipping...")

asyncio.run(main())
