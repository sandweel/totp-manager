"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-10

Hand-authored baseline that mirrors models.py. Generated migrations for
subsequent schema changes go on top of this one via
`alembic revision --autogenerate -m "..."`.
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=256), nullable=False),
        sa.Column("hashed_password", sa.String(length=256), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=True),
        sa.Column("encrypted_dek", sa.String(length=512), nullable=False),
        sa.Column("password_reset_token_id", sa.String(length=512), nullable=True),
        sa.Column("password_reset_requested_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_id", "users", ["id"], unique=False)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "totp_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("issuer", sa.String(length=128), nullable=False),
        sa.Column("account", sa.String(length=128), nullable=False),
        sa.Column("encrypted_secret", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="totp_items_user_id_fkey"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_totp_items_id", "totp_items", ["id"], unique=False)

    op.create_table(
        "shared_totp",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("totp_item_id", sa.Integer(), nullable=False),
        sa.Column("shared_with_user_id", sa.Integer(), nullable=False),
        sa.Column("encrypted_secret", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["totp_item_id"], ["totp_items.id"], name="shared_totp_totp_item_id_fkey"),
        sa.ForeignKeyConstraint(["shared_with_user_id"], ["users.id"], name="shared_totp_shared_with_user_id_fkey"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shared_totp_id", "shared_totp", ["id"], unique=False)

    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=128), nullable=False),
        sa.Column("refresh_token_expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=False),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=256), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("replaced_by_session_id", sa.String(length=36), nullable=True),
        sa.Column("parent_session_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="sessions_user_id_fkey"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sessions_id", "sessions", ["id"], unique=False)
    op.create_index("ix_sessions_session_id", "sessions", ["session_id"], unique=True)
    op.create_index("ix_sessions_user_active", "sessions", ["user_id", "revoked_at"], unique=False)

    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("key_hash", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="api_keys_user_id_fkey"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_keys_id", "api_keys", ["id"], unique=False)
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"], unique=True)
    op.create_index("ix_api_keys_user_active", "api_keys", ["user_id", "revoked_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_api_keys_user_active", table_name="api_keys")
    op.drop_index("ix_api_keys_key_hash", table_name="api_keys")
    op.drop_index("ix_api_keys_id", table_name="api_keys")
    op.drop_table("api_keys")

    op.drop_index("ix_sessions_user_active", table_name="sessions")
    op.drop_index("ix_sessions_session_id", table_name="sessions")
    op.drop_index("ix_sessions_id", table_name="sessions")
    op.drop_table("sessions")

    op.drop_index("ix_shared_totp_id", table_name="shared_totp")
    op.drop_table("shared_totp")

    op.drop_index("ix_totp_items_id", table_name="totp_items")
    op.drop_table("totp_items")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")
