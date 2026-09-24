"""Unique email addresses

Revision ID: 468995a9c9ee
Revises: 2b68f688bec1
Create Date: 2022-10-21 01:25:01.469670

"""
import unicodedata

from alembic import op
import sqlalchemy as sa

revision = '468995a9c9ee'
down_revision = '2b68f688bec1'
branch_labels = None
depends_on = None

def normalize_address(value):
	return unicodedata.normalize('NFKC', value).lower().strip()

def iter_rows_paged(table, pk='id', limit=1000):
	conn = op.get_bind()
	pk_column = getattr(table.c, pk)
	last_pk = None
	while True:
		expr = table.select().order_by(pk_column).limit(limit)
		if last_pk is not None:
			expr = expr.where(pk_column > last_pk)
		result = conn.execute(expr)
		pk_index = list(result.keys()).index(pk)
		rows = result.fetchall()
		if not rows:
			break
		yield from rows
		last_pk = rows[-1][pk_index]

def upgrade():
	with op.batch_alter_table('user_email', schema=None) as batch_op:
		batch_op.add_column(sa.Column('address_normalized', sa.String(length=128), nullable=True))
		batch_op.add_column(sa.Column('enable_strict_constraints', sa.Boolean(create_constraint=True), nullable=True))
		batch_op.alter_column('verified', existing_type=sa.Boolean(create_constraint=True), nullable=True)
	meta = sa.MetaData()
	user_email_table = sa.Table('user_email', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('user_id', sa.Integer(), nullable=True),
		sa.Column('address', sa.String(length=128), nullable=False),
		sa.Column('address_normalized', sa.String(length=128), nullable=True),
		sa.Column('enable_strict_constraints', sa.Boolean(create_constraint=True), nullable=True),
		sa.Column('verified', sa.Boolean(create_constraint=True), nullable=True),
		sa.Column('verification_legacy_id', sa.Integer(), nullable=True),
		sa.Column('verification_secret', sa.Text(), nullable=True),
		sa.Column('verification_expires', sa.DateTime(), nullable=True),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_user_email_user_id_user'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_user_email')),
		sa.UniqueConstraint('user_id', 'address', name='uq_user_email_user_id_address')
	)
	for row in iter_rows_paged(user_email_table):
		id = row[0]
		address = row[2]
		verified = row[5]
		op.execute(user_email_table.update()\
			.where(user_email_table.c.id == id)\
			.values(
				address_normalized=normalize_address(address),
				verified=(True if verified else None)
			)
		)
	with op.batch_alter_table('user_email', copy_from=user_email_table) as batch_op:
		batch_op.alter_column('address_normalized', existing_type=sa.String(length=128), nullable=False)
		batch_op.create_unique_constraint('uq_user_email_address_normalized_verified', ['address_normalized', 'verified', 'enable_strict_constraints'])
		batch_op.create_unique_constraint('uq_user_email_user_id_address_normalized', ['user_id', 'address_normalized', 'enable_strict_constraints'])
	op.create_table('feature_flag',
		sa.Column('name', sa.String(32), nullable=False),
		sa.PrimaryKeyConstraint('name', name=op.f('pk_feature_flag')),
	)

def downgrade():
	meta = sa.MetaData()
	user_email_table = sa.Table('user_email', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('user_id', sa.Integer(), nullable=True),
		sa.Column('address', sa.String(length=128), nullable=False),
		sa.Column('address_normalized', sa.String(length=128), nullable=False),
		sa.Column('enable_strict_constraints', sa.Boolean(create_constraint=True), nullable=True),
		sa.Column('verified', sa.Boolean(create_constraint=True), nullable=True),
		sa.Column('verification_legacy_id', sa.Integer(), nullable=True),
		sa.Column('verification_secret', sa.Text(), nullable=True),
		sa.Column('verification_expires', sa.DateTime(), nullable=True),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_user_email_user_id_user'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_user_email')),
		sa.UniqueConstraint('user_id', 'address', name='uq_user_email_user_id_address'),
		sa.UniqueConstraint('address_normalized', 'verified', 'enable_strict_constraints', name='uq_user_email_address_normalized_verified'),
		sa.UniqueConstraint('user_id', 'address_normalized', 'enable_strict_constraints', name='uq_user_email_user_id_address_normalized')
	)
	op.execute(user_email_table.update().where(user_email_table.c.verified == None).values(verified=False))
	with op.batch_alter_table('user_email', copy_from=user_email_table) as batch_op:
		batch_op.drop_constraint('uq_user_email_user_id_address_normalized', type_='unique')
		batch_op.drop_constraint('uq_user_email_address_normalized_verified', type_='unique')
		batch_op.alter_column('verified', existing_type=sa.Boolean(create_constraint=True), nullable=False)
		batch_op.drop_column('enable_strict_constraints')
		batch_op.drop_column('address_normalized')
	op.drop_table('feature_flag')
