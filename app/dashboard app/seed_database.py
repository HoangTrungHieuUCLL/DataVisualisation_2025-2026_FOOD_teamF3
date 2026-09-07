"""Build the `product` table from the raw CSV in one command: `python seed_database.py`.

The database this dashboard runs on used to be assembled by hand in pgAdmin, which
made it impossible to stand the app up anywhere else. This script reproduces that
setup end to end — encoding repair, text cleaning, TF-IDF vectorisation and DBSCAN
clustering (the same pipeline as food_products_clustering.ipynb) — then loads the
result into whatever database DATABASE_URL points at.

It is idempotent: it does nothing when the table already holds rows, unless you
pass --reset (or set RESEED=1) to rebuild from scratch.

Two columns, `scan_count` and `newly_added`, are NOT in the source CSV — they came
from the client's live system. They are generated here as clearly-labelled demo
data so the "most scanned first" queue and the "Newly added products" tab have
something to show; every other column is real data from the CSV.
"""

import argparse
import csv
import io
import os
import sys

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.feature_extraction.text import TfidfVectorizer

from db_config import get_connection
from preprocessing import create_cleaned_text_feature

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CSV = os.path.join(APP_DIR, "..", "..", "exploration", "view_food_clean.csv")
CSV_PATH = os.environ.get("FOOD_CSV_PATH", DEFAULT_CSV)

# Text columns that feed the clustering, per the notebook.
TEXT_COLS = ["name", "name_search", "remarks", "synonyms", "brands", "brands_search", "bron", "categories"]

# Rows dropped in the notebook (corrupt records).
IDS_TO_REMOVE = [42165, 41132, 42155, 41280, 26568]

# DBSCAN settings from the notebook.
DBSCAN_EPS = 0.3
DBSCAN_MIN_SAMPLES = 3

DEMO_SEED = 20251216  # fixed so a rebuild always produces the same demo numbers

CSV_COLUMNS = [
    "id", "name", "name_search", "active", "energy", "protein", "fat",
    "saturated_fatty_acid", "carbohydrates", "sugar", "starch", "dietary_fiber",
    "salt", "sodium", "k", "ca", "p", "fe", "polyols", "remarks", "cholesterol",
    "omega6", "omega3", "mov", "eov", "vit_d", "vit_c", "vit_b12", "vit_b6",
    "vit_b2", "vit_b1", "vit_a", "mg", "water", "is_food",
    "remarks_carbohydrates", "hash", "user_study_id", "unit", "synonyms",
    "brands", "brands_search", "glucose", "fructose", "excess_fructose",
    "lactose", "sorbitol", "mannitol", "fructans", "gos", "token",
    "token_deleted", "bron", "user_id", "deleted", "categories", "barcode",
    "merged_to", "created", "updated", "app_ver",
]

# Columns the dashboard needs on top of the CSV.
EXTRA_COLUMNS = ["cluster_id", "cluster_count", "scan_count", "newly_added", "link_to"]

TEXT_TYPE_COLUMNS = {
    "name", "name_search", "remarks", "hash", "unit", "synonyms", "brands",
    "brands_search", "token", "token_deleted", "bron", "deleted", "categories",
    "barcode", "merged_to", "app_ver",
}
INT_TYPE_COLUMNS = {"active", "is_food", "cluster_id", "cluster_count", "scan_count", "newly_added", "link_to"}
TIMESTAMP_COLUMNS = {"created", "updated"}

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS product (
{columns}
);
CREATE INDEX IF NOT EXISTS idx_product_cluster_id ON product(cluster_id);
CREATE INDEX IF NOT EXISTS idx_product_active ON product(active);
"""


def column_type(name):
    if name == "id":
        return "BIGINT PRIMARY KEY"
    if name in TEXT_TYPE_COLUMNS:
        return "TEXT"
    if name in INT_TYPE_COLUMNS:
        return "INTEGER"
    if name in TIMESTAMP_COLUMNS:
        return "TIMESTAMP"
    return "DOUBLE PRECISION"


def fix_encoding_multilayer(text):
    """Undo the double mojibake in the source export (UTF-8 read as Windows-1252)."""
    if not isinstance(text, str):
        return text
    for _ in range(2):
        try:
            text = text.encode("latin-1").decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError):
            break
    return text


def load_dataframe():
    print(f"Reading {CSV_PATH} ...")
    df = pd.read_csv(CSV_PATH, low_memory=False)
    df = df[~df["id"].isin(IDS_TO_REMOVE)].reset_index(drop=True)

    print("Repairing text encoding ...")
    for col in TEXT_COLS:
        if col in df.columns:
            df[col] = df[col].apply(fix_encoding_multilayer)

    print("Cleaning and stemming product text ...")
    df = create_cleaned_text_feature(df, TEXT_COLS)

    print("Vectorising with TF-IDF and clustering with DBSCAN ...")
    vectors = TfidfVectorizer(use_idf=True).fit_transform(df["to_vectorize"])
    labels = DBSCAN(eps=DBSCAN_EPS, min_samples=DBSCAN_MIN_SAMPLES, metric="cosine").fit_predict(vectors)
    df["cluster_id"] = labels

    clusters = len(set(labels)) - (1 if -1 in labels else 0)
    print(f"  {clusters} clusters, {list(labels).count(-1)} unclustered products")

    # cluster_count mirrors the notebook's UPDATE: noise (-1) counts as unique.
    counts = df["cluster_id"].value_counts()
    df["cluster_count"] = df["cluster_id"].map(counts).where(df["cluster_id"] != -1, 1)

    add_demo_columns(df)
    df["link_to"] = pd.NA
    return df


def add_demo_columns(df):
    """Generate the two columns the CSV export never included (see module docstring)."""
    rng = np.random.default_rng(DEMO_SEED)
    # Long-tail scan counts: a few very popular products, most rarely scanned.
    df["scan_count"] = np.rint(rng.lognormal(mean=2.5, sigma=1.6, size=len(df))).astype(int)

    # Treat the most recently created unverified products as "newly added",
    # matching the client's ~10 new products a day.
    df["newly_added"] = 0
    created = pd.to_datetime(df["created"], errors="coerce")
    recent = created[df["active"] == 0].nlargest(60).index
    df.loc[recent, "newly_added"] = 1
    print(f"  demo columns: scan_count generated, {int(df['newly_added'].sum())} products flagged newly_added")


def table_row_count(cur):
    cur.execute("SELECT to_regclass('public.product');")
    if cur.fetchone()[0] is None:
        return 0
    cur.execute("SELECT COUNT(*) FROM product;")
    return cur.fetchone()[0]


def copy_dataframe(cur, df):
    columns = CSV_COLUMNS + EXTRA_COLUMNS
    buffer = io.StringIO()
    df[columns].to_csv(buffer, index=False, header=False, na_rep="", quoting=csv.QUOTE_MINIMAL)
    buffer.seek(0)
    cur.copy_expert(
        f"COPY product ({', '.join(columns)}) FROM STDIN WITH (FORMAT csv, NULL '')",
        buffer,
    )


def run(reset=False):
    conn = get_connection()
    conn.autocommit = False
    cur = conn.cursor()

    existing = table_row_count(cur)
    if existing and not reset:
        print(f"product table already holds {existing} rows — nothing to do (use --reset to rebuild).")
        cur.close()
        conn.close()
        return

    df = load_dataframe()

    ddl = CREATE_TABLE.format(
        columns=",\n".join(f"    {name} {column_type(name)}" for name in CSV_COLUMNS + EXTRA_COLUMNS)
    )
    cur.execute(ddl)
    if reset:
        cur.execute("TRUNCATE product;")

    print(f"Loading {len(df)} rows into Postgres ...")
    copy_dataframe(cur, df)
    conn.commit()

    print(f"Done. product now holds {table_row_count(cur)} rows.")
    cur.close()
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="rebuild even if the table already has rows")
    args = parser.parse_args()
    if not os.environ.get("DATABASE_URL") and not os.path.exists(os.path.join(APP_DIR, "database_credentials.py")):
        sys.exit("Set DATABASE_URL, or create database_credentials.py as described in the README.")
    run(reset=args.reset or os.environ.get("RESEED") == "1")
