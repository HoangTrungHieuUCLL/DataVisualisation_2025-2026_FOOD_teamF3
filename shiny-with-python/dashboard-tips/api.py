# api.py
from flask import Flask, request, jsonify
import joblib
from more_itertools import one
import numpy as np
from psycopg2 import connect
import psycopg2
import json

# 1. Create Flask app
app = Flask(__name__)

def connect_to_database():
    try:
        conn = psycopg2.connect(database = "food", 
                                user = "postgres", 
                                host= 'localhost',
                                password = "Louis.hoang1506",
                                port = 5432)
        print("✅Connection ok")
        return conn
    except:
        print("❌Connection failed")

# 3. Define a predict endpoint
@app.route("/products", methods=["GET"])
def get_10_products():
    conn = connect_to_database()
    cur = conn.cursor()
    cur.execute('SELECT * FROM product LIMIT 10;')
    rows = cur.fetchall()
    conn.commit()
    conn.close()

    # map rows to list[dict] using column names so jsonify can serialize it
    columns = [desc[0] for desc in cur.description]
    results = [dict(zip(columns, row)) for row in rows]
    cur.close()
    
    return jsonify(results)

@app.route("/products/<int:product_id>", methods=["GET"])
def get_product(product_id):
    conn = connect_to_database()
    cur = conn.cursor()
    cur.execute('SELECT * FROM product WHERE id = %s;', (product_id,))
    row = cur.fetchone()
    conn.commit()
    conn.close()

    if row is None:
        return jsonify({"error": "Product not found"}), 404
    
    columns = [desc[0] for desc in cur.description]
    result = dict(zip(columns, row))
    cur.close()
    
    return jsonify(result)

if __name__ == "__main__":
    app.run(debug=True)