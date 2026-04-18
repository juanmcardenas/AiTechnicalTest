"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand", sa.String(100), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("color", sa.String(50), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("km", sa.Integer, nullable=False, server_default="0"),
        sa.Column("fuel_type", sa.String(30), nullable=False),
        sa.Column("transmission", sa.String(20), nullable=False),
        sa.Column("condition", sa.String(20), nullable=False, server_default="used"),
        sa.Column("vin", sa.String(17), unique=True, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("image_url", sa.Text, nullable=True),
        sa.Column("available", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "leads",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("telegram_chat_id", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="new"),
        sa.Column("preferred_language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("last_contacted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "conversation_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("lead_id", UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("input_modality", sa.String(10), nullable=False, server_default="text"),
        sa.Column("tool_calls", sa.JSON, nullable=True),
        sa.Column("tokens_used", sa.Integer, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_conv_history_lead", "conversation_history", ["lead_id", "created_at"])

    op.create_table(
        "meetings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("lead_id", UUID(as_uuid=True), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("car_id", UUID(as_uuid=True), sa.ForeignKey("inventory.id"), nullable=False),
        sa.Column("google_event_id", sa.String(200), nullable=True),
        sa.Column("google_meet_link", sa.Text, nullable=True),
        sa.Column("scheduled_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer, nullable=False, server_default="60"),
        sa.Column("location", sa.Text, nullable=False, server_default="Dealership showroom"),
        sa.Column("status", sa.String(30), nullable=False, server_default="scheduled"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "reminders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("lead_id", UUID(as_uuid=True), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("remind_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("sent", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_reminders_pending", "reminders", ["remind_at"], postgresql_where=sa.text("sent = false"))

    op.create_table(
        "email_sent_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("lead_id", UUID(as_uuid=True), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("car_id", UUID(as_uuid=True), sa.ForeignKey("inventory.id"), nullable=False),
        sa.Column("recipient_email", sa.String(200), nullable=False),
        sa.Column("subject", sa.String(300), nullable=False),
        sa.Column("template_used", sa.String(100), nullable=False, server_default="car_specs"),
        sa.Column("success", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("error_msg", sa.Text, nullable=True),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("email_sent_logs")
    op.drop_index("idx_reminders_pending", table_name="reminders")
    op.drop_table("reminders")
    op.drop_table("meetings")
    op.drop_index("idx_conv_history_lead", table_name="conversation_history")
    op.drop_table("conversation_history")
    op.drop_table("leads")
    op.drop_table("inventory")
