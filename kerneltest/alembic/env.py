import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, event, pool

if "KERNELTEST_CONFIG" not in os.environ and os.path.exists("/etc/kerneltest/kerneltest.cfg"):
    print("Using configuration file `/etc/kerneltest/kerneltest.cfg`")
    os.environ["kerneltest/kerneltest.cfg"] = "/etc/kerneltest/kerneltest.cfg"


from kerneltest.app import APP
from kerneltest.dbtools import BASE

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Use the options from the Bodhi config
config.set_main_option("sqlalchemy.url", APP.config["DB_URL"])

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)

target_metadata = BASE.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url)

    with context.begin_transaction():
        if config.get_main_option("bdr").strip().lower() == "true":
            context.execute("SET LOCAL bdr.permit_ddl_locking = true")
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    engine = engine_from_config(
        config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool
    )

    if config.get_main_option("bdr").strip().lower() == "true":

        def enable_bdr(connection, connection_record):
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL bdr.permit_ddl_locking = true")

        event.listen(engine, "connect", enable_bdr)

    connection = engine.connect()
    context.configure(connection=connection, target_metadata=target_metadata)

    try:
        with context.begin_transaction():
            context.run_migrations()
    finally:
        connection.close()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
