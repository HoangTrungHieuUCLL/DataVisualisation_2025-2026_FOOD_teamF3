from pathlib import Path
from psycopg2 import connect
import psycopg2
import pandas as pd

app_dir = Path(__file__).parent
# food_products = pd.read_csv(app_dir / "view_food_clean.csv")