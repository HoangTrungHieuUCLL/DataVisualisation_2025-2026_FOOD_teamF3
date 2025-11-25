# api.py
from flask import Flask, request, jsonify
import joblib
from more_itertools import one
import numpy as np
from psycopg2 import connect
import psycopg2
import json

# Create Flask app
app = Flask(__name__)

# Connection to database
def connect_to_database():
    try:
        conn = psycopg2.connect(database = "view_food_clustered", 
                                user = "postgres", 
                                host= 'localhost',
                                password = "Louis.hoang1506",
                                port = 5432)
        print("✅Connection ok")
        return conn
    except:
        print("❌Connection failed")

# Get all products
@app.route("/products", methods=["GET"])
def get_all_products():
    conn = connect_to_database()
    cur = conn.cursor()
    cur.execute('SELECT * FROM product;')
    rows = cur.fetchall()
    conn.commit()
    conn.close()

    # map rows to list[dict] using column names so jsonify can serialize it
    columns = [desc[0] for desc in cur.description]
    results = [dict(zip(columns, row)) for row in rows]
    cur.close()
    
    return jsonify(results)

@app.route("/products/<int:product_id>", methods=["GET"])
def get_product_by_id(product_id):
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

# Get all incompleted products
@app.route("/products/incompleted", methods=["GET"])
def get_all_incompleted_products():
    conn = connect_to_database()
    cur = conn.cursor()
    # Use a simple SELECT and filter incomplete rows (rows with any NULL) in Python
    cur.execute('SELECT * FROM product WHERE active = 0;')
    rows = cur.fetchall()

    # map rows to list[dict] using column names so jsonify can serialize it
    columns = [desc[0] for desc in cur.description]
    results = [dict(zip(columns, row)) for row in rows]

    # filter for incomplete products (any field is None)
    incompleted = [r for r in results if any(v is None for v in r.values())]

    cur.close()
    conn.commit()
    conn.close()
    
    return jsonify(incompleted)

# Get all products that are alike product {id}
@app.route("/products/alike/<int:product_id>/<int:cluster_id>", methods=["GET"])
def get_alike_products(product_id, cluster_id):
    conn = connect_to_database()
    cur = conn.cursor()
    cur.execute('SELECT * FROM product WHERE cluster_id = %s AND id != %s;', (cluster_id, product_id,))
    rows = cur.fetchall()
    
    # map rows to list[dict] using column names so jsonify can serialize it
    columns = [desc[0] for desc in cur.description] if cur.description else []
    results = [dict(zip(columns, row)) for row in rows] if rows else []
    
    cur.close()
    conn.close()
    
    return jsonify(results)


if __name__ == "__main__":
    app.run(debug=True)