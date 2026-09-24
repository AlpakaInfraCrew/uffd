"""Fix NOT NULL on role_groups.group_id

Revision 878b25c4fae7 wrongly left the column without a NOT NULL constraint.
The missing constraint is only detected by newer Alembic versions.

Revision ID: a60ce68b9214
Revises: 704d1245331c
Create Date: 2022-08-14 02:54:56.609390

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a60ce68b9214'
down_revision = '704d1245331c'
branch_labels = None
depends_on = None

def upgrade():
	meta = sa.MetaData()
	role_groups = sa.Table('role_groups', meta,
		sa.Column('role_id', sa.Integer(), nullable=False),
		sa.Column('group_id', sa.Integer(), nullable=True),
		sa.Column('requires_mfa', sa.Boolean(create_constraint=True), nullable=False),
		sa.ForeignKeyConstraint(['group_id'], ['group.id'], name=op.f('fk_role_groups_group_id_group'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.ForeignKeyConstraint(['role_id'], ['role.id'], name=op.f('fk_role_groups_role_id_role'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('role_id', 'group_id', name=op.f('pk_role_groups'))
	)
	with op.batch_alter_table('role_groups', copy_from=role_groups) as batch_op:
		batch_op.alter_column('group_id', existing_type=sa.INTEGER(), nullable=False)

def downgrade():
	meta = sa.MetaData()
	role_groups = sa.Table('role_groups', meta,
		sa.Column('role_id', sa.Integer(), nullable=False),
		sa.Column('group_id', sa.Integer(), nullable=False),
		sa.Column('requires_mfa', sa.Boolean(create_constraint=True), nullable=False),
		sa.ForeignKeyConstraint(['group_id'], ['group.id'], name=op.f('fk_role_groups_group_id_group'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.ForeignKeyConstraint(['role_id'], ['role.id'], name=op.f('fk_role_groups_role_id_role'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('role_id', 'group_id', name=op.f('pk_role_groups'))
	)
	with op.batch_alter_table('role_groups', copy_from=role_groups) as batch_op:
		batch_op.alter_column('group_id', existing_type=sa.INTEGER(), nullable=True)
