"""whoop v0.4 schema additions

Revision ID: 002_whoop_v04
Revises:
Create Date: 2026-03-18

"""
from alembic import op
from sqlalchemy import inspect as sa_inspect
import sqlalchemy as sa

revision = "002_whoop_v04"
down_revision = None
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    conn = op.get_bind()
    cols = [c["name"] for c in sa_inspect(conn).get_columns(table)]
    return column in cols


def _has_table(table: str) -> bool:
    conn = op.get_bind()
    return table in sa_inspect(conn).get_table_names()


def upgrade() -> None:
    if not _has_column("workouts", "whoop_activity_id"):
        op.add_column("workouts", sa.Column("whoop_activity_id", sa.String(), nullable=True))

    if not _has_column("exercises", "whoop_exercise_id"):
        op.add_column("exercises", sa.Column("whoop_exercise_id", sa.String(), nullable=True))

    if not _has_column("meals", "journal_signals"):
        op.add_column("meals", sa.Column("journal_signals", sa.Text(), nullable=True))

    # make whoop_sync_queue.workout_id nullable and add sync_type
    if not _has_column("whoop_sync_queue", "sync_type"):
        with op.batch_alter_table("whoop_sync_queue") as batch_op:
            batch_op.alter_column("workout_id", existing_type=sa.Integer(), nullable=True)
            batch_op.add_column(sa.Column("sync_type", sa.String(), server_default="workout"))

    if not _has_table("exercise_catalog"):
        op.create_table(
            "exercise_catalog",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("whoop_id", sa.String(), nullable=False, unique=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("equipment", sa.String(), nullable=True),
            sa.Column("muscle_group", sa.String(), nullable=True),
            sa.Column("cached_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("exercise_catalog")

    with op.batch_alter_table("whoop_sync_queue") as batch_op:
        batch_op.drop_column("sync_type")
        batch_op.alter_column("workout_id", existing_type=sa.Integer(), nullable=False)

    op.drop_column("meals", "journal_signals")
    op.drop_column("exercises", "whoop_exercise_id")
    op.drop_column("workouts", "whoop_activity_id")
