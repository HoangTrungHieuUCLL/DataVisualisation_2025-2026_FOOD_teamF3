import string
import faicons as fa
import plotly.express as px
import requests
import re
from services import get_incompleted_products, get_product_info


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
        # ui.output_ui("modify_product_card")
    ),
    ui.layout_columns(
        ui.navset_tab(
            ui.nav_panel("Incomplete products", ui.output_ui("all_products_listing")),
            ui.nav_panel("Alike products")
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
                ui.input_text("username", "Username"),
                ui.input_password("password", "Password"),
                ui.input_action_button("login", "Login"),
                style = "display: flex; flex-direction: column; align-items: center"
            )
        else:
            return ui.card(
                ui.tags.div(
                    ui.tags.p(f"Hello {reactive_user_name.get()}!"),
                    ui.input_action_button("logout", "Logout"),
                    style = "display: flex; flex-direction: column; align-items: left"
                )
            )

    # Login
    @reactive.effect
    @reactive.event(input.login)
    def _on_login():
        username = input.username()
        password = input.password()
        reactive_user_name.set(username)
        reactive_password.set(password)
        login_ok.set(username == "Danny" and password == "admin")
        
        if login_ok.get() == False:
            ui.modal_show(
                ui.modal(
                    ui.tags.p("Wrong username or password."),
                    easy_close=True,
                    size="s"
                )
            )
    
    # Logout
    @reactive.effect
    @reactive.event(input.logout)
    def _on_logout():
        reactive_user_name.set("")
        reactive_password.set("")
        login_ok.set(False)

    # INCOMPLETE TAB #
    @render.ui
    def all_products_listing():
        if not is_admin():
            return ui.tags.div()
        
        # Get 50 products (just to test it out)
        products = get_incompleted_products()
        
        if isinstance(products, dict) and "error" in products:
            return ui.tags.div(f"Error loading products: {products['error']}", style="color:#b00;")
        
        df = pd.json_normalize(products)
        
        if df.empty:
            return ui.tags.div("No products found.")
        
        # Decide columns to show
        base_cols = [c for c in ["id","name","active","categories"] if c in df.columns]
        header = ui.tags.tr(
            *[ui.tags.th(col, style="padding:.25rem .5rem; text-align:left; border:1px solid #ddd;") for col in base_cols]
            # ui.tags.th("Actions", style="padding:.25rem .5rem; text-align:left; border: 1px solid #ddd;")
        )
        body_rows = []
        for _, row in df.iterrows():
            pid = row.get("id")
            cells = [ui.tags.td(str(row.get(col,"")), style="padding:.25rem .5rem; vertical-align:top; border: 1px solid #ddd;") for col in base_cols]
            
            # Make the entire row clickable to trigger modify
            body_rows.append(
                ui.tags.tr(
                    *cells,
                    onclick=f"Shiny.setInputValue('modify_product_row', {pid}, {{priority: 'event'}});",
                    class_="incompleted_table_rows",
                    style="cursor:pointer;"
                )
            )
        table = ui.tags.table(
            ui.tags.thead(header),
            ui.tags.tbody(*body_rows),
            style="width:100%; border-collapse:collapse; font-size:.85rem; border:1px solid #ddd;"
        )
        return ui.tags.div(
            table,
            style="margin-top:1rem; margin-bottom:1rem"
        )
        
    def _sanitize_id(name: str) -> str:
        # Keep alphanumerics and underscore; replace others with underscore
        return re.sub(r"[^0-9A-Za-z_]+", "_", name)

    @render.ui
    def product_edit_form():
        df = product_to_modify.get()
        if df is None or df.empty:
            return ui.tags.div("This product does not exist.", style="color:#666;")

        # Use the first row as the current product
        row = df.iloc[0]

        # Segment fields into 3 groups
        primary_fields = [
            "id",
            "name",
            "name_search",
            "active",
            "synonyms",
            "brands",
            "brands_search",
            "categories",
            "barcode",
            "bron"
        ]
        nutrition_fields = [
            "energy",
            "protein",
            "fat",
            "saturated_fatty_acid",
            "carbohydrates",
            "sugar",
            "starch",
            "dietary_fiber",
            "salt",
            "sodium",
            "k",
            "ca",
            "p",
            "fe",
            "polyols",
            "cholesterol",
            "omega3",
            "omega6",
            "mov",
            "eov",
            "vit_a",
            "vit_b12",
            "vit_b6",
            "vit_b1",
            "vit_b2",
            "vit_c",
            "vit_d",
            "mg",
            "water",
            "remarks_carbohydrates",
            "glucose",
            "fructose",
            "excess_fructose",
            "lactose",
            "sorbitol",
            "mannitol",
            "fructans",
            "gos"
        ]
        other_fields = [c for c in df.columns if c not in primary_fields + nutrition_fields]

        def render_field(col_name: str):
            input_id = f"edit_{_sanitize_id(col_name)}"
            val = row[col_name] if col_name in row.index else None
            display_val = "" if (val is None or (isinstance(val, float) and pd.isna(val)) or (isinstance(val, str) and val == "nan")) else str(val)
            return ui.tags.div(
                ui.tags.label(col_name, **{"for": input_id}, style="font-weight:600; margin-bottom:.25rem;"),
                ui.input_text(input_id, None, value=display_val),
                style="display:flex; flex-direction:column; width:100%; max-width:320px;"
            )

        primary_rows = [render_field(c) for c in primary_fields]
        nutrition_rows = [render_field(c) for c in nutrition_fields]
        other_rows = [render_field(c) for c in other_fields]

        return ui.tags.div(
            ui.tags.hr(),
            ui.tags.div(
                ui.tags.h5("Basic Info"),
                ui.tags.div(
                    *primary_rows,
                    style="display:flex; flex-wrap:wrap; gap:1rem; align-items:flex-start;"
                ),
                style="display:flex; flex-direction:column; gap:.5rem; margin-bottom:1rem;"
            ),
            ui.tags.hr(),
            ui.tags.div(
                ui.tags.h5("Nutrition Info"),
                ui.tags.div(
                    *nutrition_rows,
                    style="display:flex; flex-wrap:wrap; gap:1rem; align-items:flex-start;"
                ),
                style="display:flex; flex-direction:column; gap:.5rem; margin-bottom:1rem;"
            ),
            ui.tags.hr(),
            ui.tags.div(
                ui.tags.h5("Other Fields"),
                ui.tags.div(
                    *other_rows,
                    style="display:flex; flex-wrap:wrap; gap:1rem; align-items:flex-start;"
                ),
                style="display:flex; flex-direction:column; gap:.5rem;"
            ),
            style="display:flex; flex-direction:column;"
        )


    @reactive.effect
    @reactive.event(input.modify_product_row)
    def _on_modify_product_row():
        pid = input.modify_product_row()
        response_product = get_product_info(pid)
        df = pd.json_normalize(response_product)
        product_to_modify.set(df)
        ui.modal_show(
            ui.modal(
                ui.tags.h4(f"Edit Product ID {pid}"),
                ui.output_ui("product_edit_form"),
                ui.input_action_button("save_product", "Save changes"),
                easy_close=True,
                footer=ui.tags.small("Close by clicking outside or Save"),
                size="l"
            )
        )

    # @reactive.effect
    # @reactive.event(input.save_product)
    # def _on_save_product():
    #     df = product_to_modify.get()
    #     if df is None or df.empty:
    #         return
    #     cols = list(df.columns)
    #     new_vals = {}
    #     for col in cols:
    #         input_id = f"edit_{_sanitize_id(col)}"
    #         try:
    #             val = input[input_id]()  # type: ignore[index]
    #         except Exception:
    #             val = None
    #         new_vals[col] = val
    #     updated = pd.DataFrame([new_vals])
    #     product_to_modify.set(updated)
    #     # Optionally close modal after save
    #     ui.modal_remove()

app = App(app_ui, server)
