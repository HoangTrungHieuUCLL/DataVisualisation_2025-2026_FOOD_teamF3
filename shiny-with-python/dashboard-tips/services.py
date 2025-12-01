import requests

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
    API_URL = "http://127.0.0.1:5000/products/alike/" + str(product_id) + "/" + str(cluster_id)
        
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
    API_URL = "http://127.0.0.1:5000/products/link/" + str(source_product_id) + "/" + str(destination_product_id)
        
    try:
        result = requests.put(API_URL)
        return result.json()
    except Exception as e:
        return {"error": str(e)}