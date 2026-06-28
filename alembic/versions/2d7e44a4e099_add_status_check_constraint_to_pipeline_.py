"""add status check constraint to pipeline_versions

Revision ID: 2d7e44a4e099
Revisits: 43af7142011f
Create Date: 2026-06-28 15:01:24.935445

"""

from collections.abc import Sequence

from alembic import op

revision: str = "2d7e44a4e099"
down_revision: str | Sequence[str] | None = "43af7142011f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_pipeline_version_status",
        "pipeline_versions",
        "status IN ('active', 'staging', 'archived', 'deleted')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_pipeline_version_status", "pipeline_versions", type_="check")
