# Function Mapping to Client Needs

### 1. Show products with incomplete information
The app needs to identify and display products that are unverified (`active = 0`) or missing data.

*   **`app/dashboard app/api.py`**:
    *   `get_all_incompleted_products`: Queries the database for products where `active = 0` and `link_to` is NULL.
    *   `get_incomplete_products_with_alike_products`: Specifically fetches incomplete products that have been clustered (found similar items).
*   **`app/dashboard app/app.py`**:
    *   `incomplete_products_with_alike_products_listing`: Renders the UI table for incomplete products that have potential matches.
    *   `incomplete_products_without_alike_products_listing`: Renders the UI table for "lonely" incomplete products.
    *   `update_the_tables`: Orchestrates fetching this data and updating the UI state.

### 2. Prioritize products that are scanned more
The client wants to fix the most popular products first. This is handled primarily through sorting logic in the backend and display logic in the frontend.

*   **`app/dashboard app/api.py`**:
    *   `get_all_incompleted_products`: The SQL query includes `ORDER BY scan_count DESC`, ensuring the API returns the most scanned items first by default.
*   **`app/dashboard app/tool_functions.py`**:
    *   `render_table`: Explicitly includes the `scan_count` column in the table so admins can see the priority.
*   **`app/dashboard app/app.py`**:
    *   `incomplete_products_with_alike_products_listing`: Contains logic to allow the user to manually sort by `scan_count` if they change the default order.

### 3. Show products alike to the unverified products
To help admins fix data, the app shows "alike" (clustered) products that might be duplicates or correct versions of the incomplete product.

*   **`app/dashboard app/api.py`**:
    *   `get_alike_products`: Queries products that share the same `cluster_id` as the selected product.
*   **`app/dashboard app/app.py`**:
    *   `_on_modify_product_row`: Triggered when a user clicks a product; opens the modal that loads alike products.
    *   `show_alike_products`: Renders the specific section in the modal that lists the similar verified and unverified products.
    *   `compare_dialog`: Renders the Bar and Radar charts to visually compare the nutritional values of alike products.
*   **`app/dashboard app/tool_functions.py`**:
    *   `render_alike_products_table`: Helper to generate the HTML table for these similar items inside the modal.

### 4. Link the products
The ultimate goal is to merge (link) duplicate or incomplete records to a "master" or correct record.

*   **`app/dashboard app/api.py`**:
    *   `link_product`: Executes the database update, setting the `link_to` column of the source product to the ID of the destination product.
*   **`app/dashboard app/app.py`**:
    *   `_on_link_product`: Sets the state to prepare for a link action (identifies the target).
    *   `_on_link_selected_to_current`: Handles the bulk action of linking multiple selected "alike" products to the current product being viewed.
    *   `link_confirmation_dialog`: Shows the "Are you sure?" UI before committing the change.
    *   `_on_confirm_link`: The event handler that actually calls the API to finalize the merge.

# What is shown in the app?
### 1. Side panel
*   **Login / Logout** <br>
    The client wants to have some level of security.
*   **Search by keyword bar** <br>
    With the massive amount of food product, it helps to be able to search by the keywords of product namne, categories, etc.
*   **Recent opened products** <br>
    The goal requires a lot of clicking to different products to make comparison, etc. so it might be helpful to know which product the user clicked before, especially when there might be a lot of products with the same name. This might also help avoid making mistakes or clicking the wrong products.

### 2. The incomplete-product-with-alike-products tab
*   Show all the unverified products with potential alike products. <br>
This helps user separate what the goal they want to achieve in this session.

### 3. The incomplete-products-without-alike-products tab
*  Show all the UNIQUE unverified products. <br>
When user only wants to update the product information without having to worry if the product has alike products or not, this table becomes handy.

### 4. Newly added products tab
*   Show all newly added products. <br>
Since there are only 10, 11 new products are recorded daily, it is not urgent to find the similar products for the newly added products right away. <br>
User can simply go to this tab, and click "Find similar products" for all the newly added products, instead of finding them one by one.

### 5. The modify product pop up
*   When user clicks on the product in the table, a pop up of list of alike products, and all the information of that products is shown. <br>
The information of that product is editable (partly).

### 6. The comparison dashboard
*   When user clicks "Compare" button, this popup will show up. <br>
There are 3 components of this dashboard: compare by text columns (names, categories, ...), compare by nutrition values (protein, energy, ...) and bar chart + radar chart to visualise how different the nutrition values are. <br>
This pop up gives user a detailed sense of how much the products are alike to each other.

# Configuration
### 1. Required packages and dependencies
Run `pip install -r app/dashboard app/requirements.txt` to install all requirements and dependencies.

### 2. Necessary files (assuming the dataset is saved in user's local database)
Create a file called `database_credentials.py` in `app/dashboard app` repository. <br>
Paste the following to the file:
```python
DATABASE = "" # Your local databse name
USER = "" # Your local database user name
HOST= 'localhost'
PASSWORD = "" # Your local database password
PORT = 5432 # Change this depending on which port your local database is using
```

# How to run the app
Open two terminals. In each terminal, run the following commands:
```Bash
# Terminal 1
python3 app/dashboard app/api.py # if macOS or Linux
python app/dashboard app/api.py # if Windows
```

```Bash
# Terminal 2
shiny run --reload app/dashboard app/app.py
```

Access the app's GUI via browser: `http://127.0.0.1:8000/`