Database Migrations
===================

While we use Alembic in a single-database configuration, the migration scripts
are compatible with both SQLite and MySQL/MariaDB.

Compatibility with SQLite almost always requires `batch_alter_table` operations
to modify existing tables. These recreate the tables, copy the data and finally
replace the old with the newly created ones. Alembic is configured to
auto-generate those operations, but in most cases the generated code fails to
fully reflect all details of the original schema. This way some constraints
(i.e. `CHECK` constrains on Enums) are lost. Define the full table and pass it
with `copy_from` to `batch_alter_table` to prevent this.

Compatibility with MySQL requires special care when changing primary keys and
when dealing with foreign keys. It often helps to temporarily remove foreign
key constraints concerning the table that is subject to change. When adding an
auto-increment id column as the new primary key of a table, recreate the table
with `batch_alter_table`.

The `check_migrations.py` script verifies that upgrading and downgrading works
with both databases. While it is far from perfect, it catches many common
errors. It runs automatically as part of the CI pipeline. Make sure to update
the script when adding new tables and when making significant changes to
existing tables.
