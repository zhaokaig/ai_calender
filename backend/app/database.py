import sqlite3
from pathlib import Path

import click
from flask import current_app, g


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE_PATH"])
        g.db.row_factory = sqlite3.Row

    return g.db


def close_db(error=None) -> None:
    db = g.pop("db", None)

    if db is not None:
        db.close()


def init_db() -> None:
    db_path = Path(current_app.config["DATABASE_PATH"])
    db_path.parent.mkdir(parents=True, exist_ok=True)

    db = get_db()
    schema_path = Path(current_app.root_path) / "schema.sql"

    with schema_path.open() as schema:
        db.executescript(schema.read())


@click.command("init-db")
def init_db_command() -> None:
    init_db()
    click.echo("Initialized the database.")


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
