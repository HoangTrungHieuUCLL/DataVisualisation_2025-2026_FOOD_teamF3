# api.py
from flask import Flask, request, jsonify
import joblib
from more_itertools import one
import numpy as np
from psycopg2 import connect
import psycopg2
import json
import pandas as pd
from sklearn.metrics import pairwise_distances

# Create Flask app
app = Flask(__name__)

try:
    # Load the models saved from the notebook
    dbscan_model = joblib.load("dbscan_model.pkl")
    tfidf_vectorizer = joblib.load("tfidf_vectorizer.pkl")
    print("✅ DBSCAN model and vectorizer loaded successfully")
except Exception as e:
    print(f"❌ Failed to load models: {e}")
    dbscan_model = None
    tfidf_vectorizer = None

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

@app.route("/products/count", methods=["GET"])
def get_products_count():
    conn = connect_to_database()
    cur = conn.cursor()
    try:
        cur.execute('SELECT COUNT(*) FROM product;')
        count = cur.fetchone()[0]
        return jsonify({"count": count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

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

@app.route("/products/<int:product_id>", methods=["PUT"])
def update_product(product_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Build SET clause
    set_clauses = []
    values = []
    for key, value in data.items():
        if key == 'id': continue # Don't update ID
        set_clauses.append(f"{key} = %s")
        values.append(value)
    
    if not set_clauses:
        return jsonify({"error": "No fields to update"}), 400
        
    values.append(product_id)
    
    query = f"UPDATE product SET {', '.join(set_clauses)} WHERE id = %s RETURNING id;"
    
    conn = None
    cur = None
    try:
        conn = connect_to_database()
        cur = conn.cursor()
        cur.execute(query, tuple(values))
        updated_row = cur.fetchone()
        conn.commit()
        
        if updated_row:
            return jsonify({"success": True, "id": updated_row[0]}), 200
        else:
            return jsonify({"error": "Product not found"}), 404
            
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

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

@app.route("/products/link/<int:source_product_id>/<int:destination_product_id>", methods=["PUT"])
def link_product(source_product_id, destination_product_id):
    conn = None
    cur = None
    try:
        conn = connect_to_database()
        if conn is None:
            raise RuntimeError("Failed to establish database connection")
        cur = conn.cursor()
        # return the updated row id so we can detect if update affected a row
        cur.execute('UPDATE product SET link_to = %s WHERE id = %s RETURNING id;', (destination_product_id, source_product_id,))
        updated = cur.fetchone()
        conn.commit()
        if not updated:
            return jsonify({"error": f"Product {source_product_id} not found or not updated"}), 404
        return jsonify({"success": True, "updated_id": updated[0]}), 200
    except Exception as e:
        # attempt rollback if possible
        try:
            if conn:
                conn.rollback()
        except Exception:
            pass
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            if cur:
                cur.close()
        except Exception:
            pass
        try:
            if conn:
                conn.close()
        except Exception:
            pass
        
@app.route("/products/incomplete/alike", methods=["GET"])
def get_incomplete_products_with_alike_products():
    conn = connect_to_database()
    cur = conn.cursor()
    cur.execute('SELECT * FROM product WHERE active = 0 AND cluster_count != 1;')
    rows = cur.fetchall()
    
    # map rows to list[dict] using column names so jsonify can serialize it
    columns = [desc[0] for desc in cur.description] if cur.description else []
    results = [dict(zip(columns, row)) for row in rows] if rows else []
    
    cur.close()
    conn.close()
    
    return jsonify(results)

@app.route("/products/latest", methods=["GET"])
def get_latest_product():
    conn = connect_to_database()
    cur = conn.cursor()
    try:
        # Assuming 'id' is auto-incrementing, the highest ID is the latest
        cur.execute('SELECT * FROM product WHERE newly_added = 1;')
        row = cur.fetchone()
        
        if row:
            columns = [desc[0] for desc in cur.description]
            result = dict(zip(columns, row))
            return jsonify(result)
        return jsonify({"error": "No products found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route("/products/update/cluster", methods=["PUT"])
def update_cluster_id():
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
        
    if isinstance(data, dict):
        data = [data]
        
    conn = connect_to_database()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
        
    cur = conn.cursor()
    updated_count = 0
    
    try:
        for item in data:
            product_id = item.get('id')
            cluster_id = item.get('cluster_id')
            if cluster_id is None:
                cluster_id = item.get('temp_cluster_id')
            
            cluster_count = item.get('cluster_count')
                
            if product_id is not None and cluster_id is not None:
                if cluster_count is not None:
                    cur.execute('UPDATE product SET cluster_id = %s, cluster_count = %s WHERE id = %s;', (int(cluster_id), int(cluster_count), int(product_id)))
                else:
                    cur.execute('UPDATE product SET cluster_id = %s WHERE id = %s;', (int(cluster_id), int(product_id)))
                updated_count += 1
        
        conn.commit()
        return jsonify({"success": True, "updated_count": updated_count}), 200
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    app.run(debug=True)