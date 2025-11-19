# Questions for client:
# 1. How to define an incomplete product? Do we have another column saying the status of the product? Or the client has to add "-" in the empty cells?


import string
import faicons as fa
import plotly.express as px
import requests
import re

# Load data and compute static values
from shared import app_dir
from shinywidgets import output_widget, render_plotly

from shiny import App, reactive, render, ui
import pandas as pd

ICONS = {
    "user": fa.icon_svg("user", "regular"),
    "wallet": fa.icon_svg("wallet"),
    "currency-dollar": fa.icon_svg("dollar-sign"),
    "ellipsis": fa.icon_svg("ellipsis"),
}

# Add page title and sidebar
app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.output_ui("login_card"),
        ui.output_ui("modify_product_card")
    ),
    ui.layout_columns(
        ui.card(
            ui.card_header("Incomplete products"),
            ui.tags.div(
                ui.tags.div(
                    ui.output_data_frame("products_with_missing_data_table"),
                    style = "width: 100%"
                ),
                style = "display: flex; flex-direction: row; align-items: top; gap: 1rem"
            ),
            full_screen=True
        )
    ),
    ui.include_css(app_dir / "styles.css"),
    title="Food products",
    fillable=True,
)


def server(input, output, session):
    
    # --------------------------------- #
    # Reactive Values                   #
    # --------------------------------- #
    login_ok = reactive.Value(False)
    reactive_user_name = reactive.Value("")
    reactive_password = reactive.Value("")
    product_to_modify = reactive.Value(pd.DataFrame())
    
    # --------------------------------- #
    # LOG IN                            #
    # --------------------------------- #
    @reactive.calc
    def is_admin():
        return login_ok()
    
    @render.ui
    def login_card():
        if is_admin() == False:
            return ui.card(
                ui.card_header("Admin Login"),
                ui.input_text("email", "Email", placeholder="admin"),
                ui.input_password("password", "Password", placeholder="admin"),
                ui.input_action_button("login", "Login"),
                style = "display: flex; flex-direction: column; align-items: center"
            )
        else:
            return ui.card(
                ui.tags.div(
                    ui.tags.p(f"Hello {reactive_user_name.get()}!")
                )
            )

    # Validate credentials only when the Login button is clicked
    @reactive.effect
    @reactive.event(input.login)
    def _on_login():
        email = input.email()
        password = input.password()
        reactive_user_name.set(email)
        reactive_password.set(password)
        login_ok.set(reactive_user_name.get() == "admin" and reactive_password.get() == "admin")
    
    def get_all_products():
        API_URL = "http://127.0.0.1:5000/products"
        
        try:
            products = requests.get(API_URL)
            return products.json()
        except Exception as e:
            return {"error": str(e)}
        
    def get_product_info(product_id):
        API_URL = "http://127.0.0.1:5000/products/" + str(product_id)
        
        try:
            product = requests.get(API_URL)
            return product.json()
        except Exception as e:
            return {"error": str(e)}

    @render.ui
    def modify_product_card():
        if is_admin():
            return ui.card(
                ui.card_header("Modify product"),
                ui.input_action_button("modify_product", "Get product info")
            )
        
    @reactive.effect
    @reactive.event(input.modify_product)
    def _on_modify_product():
        ui.modal_show(
            ui.modal(
                ui.tags.p("Type in the product id that you want to modify information "),
                ui.input_numeric("product_id", "Product ID", value=0, min=0),
                ui.input_action_button("get_product_info", "Get product info"),
                # ui.input_action_button("save_product", "Save changes"),
                style = "display: flex; flex-direction: column; align-items: left; gap: 1rem"
            )
        )
        
    @reactive.effect
    @reactive.event(input.get_product_info)
    def _on_get_product_info():
        product_id = input.product_id()
        response_product = get_product_info(product_id)
        # Normalize dict (single product) or list of dicts into a DataFrame
        df = pd.json_normalize(response_product)
        product_to_modify.set(df)
        # After loading, show modal with edit form
        ui.modal_show(
            ui.modal(
                ui.tags.h4(f"Edit Product ID {product_id}"),
                ui.output_ui("product_edit_form"),
                ui.input_action_button("save_product", "Save changes"),
                easy_close=True,
                footer=ui.tags.small("Close by clicking outside or Save"),
                size="l"
            )
        )
        
    def _sanitize_id(name: str) -> str:
        # Keep alphanumerics and underscore; replace others with underscore
        return re.sub(r"[^0-9A-Za-z_]+", "_", name)

    @render.ui
    def product_edit_form():
        df = product_to_modify.get()
        if df is None or df.empty:
            return ui.tags.div("No product loaded.", style="color:#666;")

        # Use the first row as the current product
        row = df.iloc[0]

        rows = []
        for col in df.columns:
            input_id = f"edit_{_sanitize_id(col)}"
            val = row[col]
            # Render as text input for simplicity and robustness
            # Convert NaN/None to empty string for display
            display_val = "" if pd.isna(val) else str(val)
            # Vertical (label above input)
            rows.append(
                ui.tags.div(
                    ui.tags.label(col, **{"for": input_id}, style="font-weight:600; margin-bottom:.25rem;"),
                    ui.input_text(input_id, None, value=display_val),
                    style="display:flex; flex-direction:column; width:100%; max-width:320px;"
                )
            )

        return ui.tags.div(
            *rows,
            style="display:flex; flex-wrap:wrap; gap:1rem; align-items:flex-start;"
        )

    @reactive.effect
    @reactive.event(input.save_product)
    def _on_save_product():
        df = product_to_modify.get()
        if df is None or df.empty:
            return
        cols = list(df.columns)
        new_vals = {}
        for col in cols:
            input_id = f"edit_{_sanitize_id(col)}"
            try:
                val = input[input_id]()  # type: ignore[index]
            except Exception:
                val = None
            new_vals[col] = val
        updated = pd.DataFrame([new_vals])
        product_to_modify.set(updated)
        # Optionally close modal after save
        ui.modal_remove()
    
    @render.data_frame
    def products_with_missing_data_table():
        if is_admin():
            res = get_all_products()
            df = pd.json_normalize(res)
            columns_to_show = ['id', 'name', 'active', 'energy', 'protein', 'categories']

            return df[columns_to_show]
        
    @render.data_frame
    def render_product_to_modify():
        # Access the underlying DataFrame via .get() so Shiny tracks dependency
        df = product_to_modify.get()
        cols_to_show = ['id','name', 'barcode']
        
        if df is None or df.empty:
            # Provide an empty structure so UI renders headers consistently
            return pd.DataFrame(columns=cols_to_show)
        
        return df[cols_to_show]
    
    @render.text
    def greeting_admin():
        if is_admin():
            return "Hello admin!"
        else:
            return "You need to log in first!"

app = App(app_ui, server)
