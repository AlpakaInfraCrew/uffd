"""invite creator and role moderator group

Revision ID: 5cab70e95bf8
Revises: 54b2413586fd
Create Date: 2021-04-14 15:46:29.910342

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5cab70e95bf8'
down_revision = '54b2413586fd'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('invite', schema=None) as batch_op:
        batch_op.add_column(sa.Column('creator_dn', sa.String(length=128), nullable=True))

    with op.batch_alter_table('role', schema=None) as batch_op:
        batch_op.add_column(sa.Column('moderator_group_dn', sa.String(length=128), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('role', schema=None) as batch_op:
        batch_op.drop_column('moderator_group_dn')

    with op.batch_alter_table('invite', schema=None) as batch_op:
        batch_op.drop_column('creator_dn')

    # ### end Alembic commands ###
