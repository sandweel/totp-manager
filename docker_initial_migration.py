import os
import time
import asyncio
import subprocess
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import inspect

DATABASE_URL = os.getenv("DATABASE_URL")

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
