import joblib
from pandas import DataFrame
import requests
from preprocessing import create_cleaned_text_feature
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.cluster import DBSCAN
from sklearn.feature_extraction.text import CountVectorizer
from matplotlib import pyplot as plt
from sklearn.decomposition import TruncatedSVD

# Get all products


def get_all_products():
    API_URL = "http://127.0.0.1:5000/products"

    try:
        products = requests.get(API_URL)
        return products.json()
    except Exception as e:
        return {"error": str(e)}

# Get all incompleted products


def get_incompleted_products():
    API_URL = "http://127.0.0.1:5000/products/incompleted"

    try:
        products = requests.get(API_URL)
        return products.json()
    except Exception as e:
        return {"error": str(e)}

# Get product info based on id


def get_product_info(product_id):
    API_URL = "http://127.0.0.1:5000/products/" + str(product_id)

    try:
        product = requests.get(API_URL)
        return product.json()
    except Exception as e:
        return {"error": str(e)}


def update_product_info(product_id, data):
    API_URL = "http://127.0.0.1:5000/products/" + str(product_id)
    try:
        response = requests.put(API_URL, json=data)
        return response.json()
    except Exception as e:
        return {"error": str(e)}


def get_alike_products(product_id, cluster_id):
    API_URL = "http://127.0.0.1:5000/products/alike/" + \
        str(product_id) + "/" + str(cluster_id)

    try:
        products = requests.get(API_URL)
        return products.json()
    except Exception as e:
        return {"error": str(e)}


def get_incomplete_products_with_alike_products():
    API_URL = "http://127.0.0.1:5000/products/incomplete/alike"

    try:
        products = requests.get(API_URL)
        return products.json()
    except Exception as e:
        return {"error": str(e)}


def link_product(source_product_id, destination_product_id):
    API_URL = "http://127.0.0.1:5000/products/link/" + \
        str(source_product_id) + "/" + str(destination_product_id)

    try:
        result = requests.put(API_URL)
        return result.json()
    except Exception as e:
        return {"error": str(e)}


def get_products_count():
    API_URL = "http://127.0.0.1:5000/products/count"
    try:
        response = requests.get(API_URL)
        return response.json().get("count", 0)
    except Exception:
        return 0


def get_latest_product():
    API_URL = "http://127.0.0.1:5000/products/latest"
    try:
        response = requests.get(API_URL)
        return response.json()
    except Exception:
        return {"error": "Failed to fetch latest product"}


def re_clustering(df: DataFrame):
    text_cols = ['name', 'name_search', 'remarks', 'synonyms', 'brands', 'brands_search', 'bron', 'categories']
    
    df_cleaned = create_cleaned_text_feature(df, text_cols)
    
    tfidf_vectorizer = TfidfVectorizer(use_idf=True)
    tfidf_vectors = tfidf_vectorizer.fit_transform(df_cleaned['to_vectorize'])
    
    dbscan = DBSCAN(eps=0.3, min_samples=3, metric='cosine') # Using cosine distance for better text vector comparison

    # Fit DBSCAN on the TF-IDF matrix (one row per product) and save labels to product_text
    labels = dbscan.fit_predict(tfidf_vectors)
    df_cleaned['temp_cluster_id'] = labels
    
    # Calculate cluster_count
    cluster_counts = df_cleaned['temp_cluster_id'].value_counts()
    df_cleaned['cluster_count'] = df_cleaned['temp_cluster_id'].map(cluster_counts)

    # Call API to update cluster_id
    API_URL = "http://127.0.0.1:5000/products/update/cluster"
    try:
        # Convert to list of dicts
        data = df_cleaned[['id', 'temp_cluster_id', 'cluster_count']].to_dict(orient='records')
        requests.put(API_URL, json=data)
    except Exception as e:
        print(f"Error updating clusters: {e}")