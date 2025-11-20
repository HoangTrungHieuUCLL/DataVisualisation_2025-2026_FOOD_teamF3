import requests

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