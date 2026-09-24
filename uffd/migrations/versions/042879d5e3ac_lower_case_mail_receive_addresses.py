"""lower-case mail receive addresses

Revision ID: 042879d5e3ac
Revises: 878b25c4fae7
Create Date: 2022-02-01 20:37:32.103288

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '042879d5e3ac'
down_revision = '878b25c4fae7'
branch_labels = None
depends_on = None

def upgrade():
	meta = sa.MetaData()
	mail_receive_address_table = sa.Table('mail_receive_address', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('mail_id', sa.Integer(), nullable=False),
		sa.Column('address', sa.String(length=128), nullable=False),
		sa.ForeignKeyConstraint(['mail_id'], ['mail.id'], name=op.f('fk_mail_receive_address_mail_id_mail'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_mail_receive_address'))
	)
	op.execute(mail_receive_address_table.update().values(address=sa.func.lower(mail_receive_address_table.c.address)))

def downgrade():
	pass
