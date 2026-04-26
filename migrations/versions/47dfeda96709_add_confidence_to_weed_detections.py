"""add confidence to weed_detections

Revision ID: 47dfeda96709
Revises: 
Create Date: 2026-04-27 00:33:06.711756

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '47dfeda96709'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('weed_detections', schema=None) as batch_op:
        batch_op.add_column(sa.Column('confidence', sa.Float(), nullable=True))


def downgrade():
    with op.batch_alter_table('weed_detections', schema=None) as batch_op:
        batch_op.drop_column('confidence')
