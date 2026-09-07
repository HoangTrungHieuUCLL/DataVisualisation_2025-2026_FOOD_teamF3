"""Database connection settings.

Reads DATABASE_URL when it is set (that is what Railway, Heroku and most hosts
inject), and otherwise falls back to the local `database_credentials.py`
described in the README, so running the app on your own machine is unchanged.
"""

import os

import psycopg2


def get_connection():
    """Open a psycopg2 connection using whichever configuration is available."""
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return psycopg2.connect(database_url)

    # Local development: app/dashboard app/database_credentials.py (gitignored)
    from database_credentials import DATABASE, HOST, PASSWORD, PORT, USER

    return psycopg2.connect(
        database=DATABASE,
        user=USER,
        host=HOST,
        password=PASSWORD,
        port=PORT,
    )
