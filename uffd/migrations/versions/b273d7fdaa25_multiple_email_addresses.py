"""Multiple email addresses

Revision ID: b273d7fdaa25
Revises: 9f824f61d8ac
Create Date: 2022-08-19 22:52:48.730877

"""
from alembic import op
import sqlalchemy as sa
import datetime

# revision identifiers, used by Alembic.
revision = 'b273d7fdaa25'
down_revision = 'b8fbefca3675'
branch_labels = None
depends_on = None

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
	user_email_table = op.create_table('user_email',
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('user_id', sa.Integer(), nullable=True),
		sa.Column('address', sa.String(length=128), nullable=False),
		sa.Column('verified', sa.Boolean(create_constraint=True), nullable=False),
		sa.Column('verification_legacy_id', sa.Integer(), nullable=True),
		sa.Column('verification_secret', sa.Text(), nullable=True),
		sa.Column('verification_expires', sa.DateTime(), nullable=True),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_user_email_user_id_user'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_user_email')),
		sa.UniqueConstraint('user_id', 'address', name='uq_user_email_user_id_address')
	)
	user_table = sa.table('user',
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('mail', sa.VARCHAR(length=128), nullable=False),
	)
	op.execute(user_email_table.insert().from_select(
		['user_id', 'address', 'verified'],
		sa.select(user_table.c.id, user_table.c.mail, sa.literal(True, sa.Boolean(create_constraint=True)))
	))
	with op.batch_alter_table('user', schema=None) as batch_op:
		batch_op.add_column(sa.Column('primary_email_id', sa.Integer(), nullable=True))
		batch_op.add_column(sa.Column('recovery_email_id', sa.Integer(), nullable=True))
		batch_op.create_foreign_key(batch_op.f('fk_user_primary_email_id_user_email'), 'user_email', ['primary_email_id'], ['id'], onupdate='CASCADE')
		batch_op.create_foreign_key(batch_op.f('fk_user_recovery_email_id_user_email'), 'user_email', ['recovery_email_id'], ['id'], onupdate='CASCADE', ondelete='SET NULL')
	meta = sa.MetaData()
	user_table = sa.Table('user', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('unix_uid', sa.Integer(), nullable=False),
		sa.Column('loginname', sa.String(length=32), nullable=False),
		sa.Column('displayname', sa.String(length=128), nullable=False),
		sa.Column('mail', sa.VARCHAR(length=128), nullable=False),
		sa.Column('primary_email_id', sa.Integer(), nullable=True),
		sa.Column('recovery_email_id', sa.Integer(), nullable=True),
		sa.Column('pwhash', sa.Text(), nullable=True),
		sa.Column('is_service_user', sa.Boolean(create_constraint=True), nullable=False),
		sa.ForeignKeyConstraint(['primary_email_id'], ['user_email.id'], name=op.f('fk_user_primary_email_id_user_email'), onupdate='CASCADE'),
		sa.ForeignKeyConstraint(['recovery_email_id'], ['user_email.id'], name=op.f('fk_user_recovery_email_id_user_email'), onupdate='CASCADE', ondelete='SET NULL'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_user')),
		sa.UniqueConstraint('loginname', name=op.f('uq_user_loginname')),
		sa.UniqueConstraint('unix_uid', name=op.f('uq_user_unix_uid'))
	)
	op.execute(user_table.update().values(primary_email_id=sa.select(user_email_table.c.id).where(user_email_table.c.user_id==user_table.c.id).limit(1).as_scalar()))
	with op.batch_alter_table('user', copy_from=user_table) as batch_op:
		batch_op.alter_column('primary_email_id', existing_type=sa.Integer(), nullable=False)
		batch_op.drop_column('mail')
	mailToken_table = sa.table('mailToken',
		sa.column('id', sa.Integer()),
		sa.column('token', sa.Text()),
		sa.column('created', sa.DateTime()),
		sa.column('newmail', sa.Text()),
		sa.column('user_id', sa.Integer()),
	)
	for token_id, token, created, newmail, user_id in iter_rows_paged(mailToken_table):
		op.execute(user_email_table.insert().insert().values(
			user_id=user_id,
			address=newmail,
			verified=False,
			verification_legacy_id=token_id,
			verification_secret='{PLAIN}'+token,
			# in-python because of this
			verification_expires=(created + datetime.timedelta(days=2)),
		))
	op.drop_table('mailToken')

def downgrade():
	with op.batch_alter_table('user', schema=None) as batch_op:
		batch_op.add_column(sa.Column('mail', sa.VARCHAR(length=128), nullable=True))
	meta = sa.MetaData()
	user_table = sa.Table('user', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('unix_uid', sa.Integer(), nullable=False),
		sa.Column('loginname', sa.String(length=32), nullable=False),
		sa.Column('displayname', sa.String(length=128), nullable=False),
		sa.Column('mail', sa.VARCHAR(length=128), nullable=False),
		sa.Column('primary_email_id', sa.Integer(), nullable=False),
		sa.Column('recovery_email_id', sa.Integer(), nullable=True),
		sa.Column('pwhash', sa.Text(), nullable=True),
		sa.Column('is_service_user', sa.Boolean(create_constraint=True), nullable=False),
		sa.ForeignKeyConstraint(['primary_email_id'], ['user_email.id'], name=op.f('fk_user_primary_email_id_user_email'), onupdate='CASCADE'),
		sa.ForeignKeyConstraint(['recovery_email_id'], ['user_email.id'], name=op.f('fk_user_recovery_email_id_user_email'), onupdate='CASCADE', ondelete='SET NULL'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_user')),
		sa.UniqueConstraint('loginname', name=op.f('uq_user_loginname')),
		sa.UniqueConstraint('unix_uid', name=op.f('uq_user_unix_uid'))
	)
	user_email_table = sa.table('user_email',
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('address', sa.String(length=128), nullable=False),
	)
	op.execute(user_table.update().values(mail=sa.select(user_email_table.c.address).where(user_email_table.c.id==user_table.c.primary_email_id).limit(1).as_scalar()))
	with op.batch_alter_table('user', copy_from=user_table) as batch_op:
		batch_op.alter_column('mail', existing_type=sa.VARCHAR(length=128), nullable=False)
		batch_op.drop_constraint(batch_op.f('fk_user_recovery_email_id_user_email'), type_='foreignkey')
		batch_op.drop_constraint(batch_op.f('fk_user_primary_email_id_user_email'), type_='foreignkey')
		batch_op.drop_column('recovery_email_id')
		batch_op.drop_column('primary_email_id')
	op.create_table('mailToken',
		sa.Column('id', sa.INTEGER(), nullable=False),
		sa.Column('token', sa.VARCHAR(length=128), nullable=False),
		sa.Column('created', sa.DATETIME(), nullable=True),
		sa.Column('newmail', sa.VARCHAR(length=255), nullable=True),
		sa.Column('user_id', sa.INTEGER(), nullable=False),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id')
	)
	op.drop_table('user_email')

