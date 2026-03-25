"""merge v012 and v15b heads

Revision ID: ecbf26370492
Revises: manual_v012_cols, manual_v15b_enums
Create Date: 2026-03-25 11:55:22.524255
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ecbf26370492'
down_revision: Union[str, None] = ('manual_v012_cols', 'manual_v15b_enums')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
