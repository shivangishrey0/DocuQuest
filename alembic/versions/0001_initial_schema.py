"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "document_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    document_status = postgresql.ENUM("pending", "processing", "completed", "failed", name="document_status", create_type=False)
    document_role = postgresql.ENUM("question_paper", "answer_key", "unknown", name="document_role", create_type=False)
    document_status.create(op.get_bind(), checkfirst=True)
    document_role.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("document_groups.id"), nullable=True),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("stored_path", sa.String(1024), nullable=False),
        sa.Column("file_type", sa.String(16), nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=False),
        sa.Column("status", document_status, nullable=False, server_default="pending"),
        sa.Column("role", document_role, nullable=False, server_default="unknown"),
        sa.Column("is_scanned", sa.Boolean, nullable=True),
        sa.Column("page_count", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_documents_owner_id", "documents", ["owner_id"])
    op.create_index("ix_documents_group_id", "documents", ["group_id"])

    op.create_table(
        "pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_number", sa.Integer, nullable=False),
        sa.Column("raw_text", sa.Text, nullable=True),
        sa.Column("extraction_method", sa.String(32), nullable=False, server_default="text_layer"),
        sa.Column("ocr_confidence", sa.Float, nullable=True),
        sa.Column("image_path", sa.String(1024), nullable=True),
        sa.Column("rotation_applied", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_pages_document_id", "pages", ["document_id"])

    question_type = postgresql.ENUM("mcq_single", "mcq_multi", "true_false", "short_answer", "unknown", name="question_type", create_type=False)
    question_status = postgresql.ENUM("success", "partial", "review", name="question_status", create_type=False)
    question_type.create(op.get_bind(), checkfirst=True)
    question_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("document_groups.id"), nullable=True),
        sa.Column("question_number", sa.String(32), nullable=True),
        sa.Column("question_text", sa.Text, nullable=False, server_default=""),
        sa.Column("options", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("question_type", question_type, nullable=False, server_default="unknown"),
        sa.Column("images", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("answer", sa.String(512), nullable=True),
        sa.Column("answer_confidence", sa.Float, nullable=True),
        sa.Column("answer_source", sa.String(64), nullable=True),
        sa.Column("source_pages", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("spans_multiple_pages", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0"),
        sa.Column("status", question_status, nullable=False, server_default="review"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_questions_document_id", "questions", ["document_id"])
    op.create_index("ix_questions_group_id", "questions", ["group_id"])

    op.create_table(
        "answer_key_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("document_groups.id"), nullable=True),
        sa.Column("question_number", sa.String(32), nullable=False),
        sa.Column("answer_text", sa.String(512), nullable=False),
        sa.Column("raw_line", sa.Text, nullable=True),
        sa.Column("source_page", sa.Integer, nullable=True),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0"),
        sa.Column("matched_question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("questions.id"), nullable=True),
    )
    op.create_index("ix_answer_key_entries_document_id", "answer_key_entries", ["document_id"])
    op.create_index("ix_answer_key_entries_group_id", "answer_key_entries", ["group_id"])

    review_severity = postgresql.ENUM("info", "warning", "critical", name="review_severity", create_type=False)
    review_severity.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "review_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("questions.id"), nullable=True),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("severity", review_severity, nullable=False, server_default="warning"),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_review_items_document_id", "review_items", ["document_id"])


def downgrade() -> None:
    op.drop_table("review_items")
    op.drop_table("answer_key_entries")
    op.drop_table("questions")
    op.drop_table("pages")
    op.drop_table("documents")
    op.drop_table("document_groups")
    op.drop_table("users")

    for enum_name in ("review_severity", "question_status", "question_type", "document_role", "document_status"):
        postgresql.ENUM(name=enum_name).drop(op.get_bind(), checkfirst=True)
