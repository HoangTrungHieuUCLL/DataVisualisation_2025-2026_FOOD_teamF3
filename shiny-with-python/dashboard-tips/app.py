import string
import faicons as fa
import plotly.express as px
import requests
import re
from services import get_incompleted_products, get_product_info, get_all_products, get_alike_products


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
        ui.output_ui("dynamic_control_center")
    ),
    ui.layout_columns(
        ui.navset_tab(
            ui.nav_panel("Incomplete products", 
                         ui.output_text("incomplete_products_instruction"),
                         ui.output_ui("incomplete_products_listing")),
            ui.nav_panel("Alike products"),
            id="main_tabs",
            selected="Incomplete products"
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
    all_products = reactive.Value(pd.DataFrame())
    incomplete_products = reactive.Value(pd.DataFrame())
    product_to_modify = reactive.Value(pd.DataFrame())
    current_tab = reactive.Value("Incomplete products")
    show_product_info = reactive.Value(False)
    
    # --------------------------------- #
    # LOG IN                            #
    # --------------------------------- #
    @reactive.calc
    def is_admin():
        return login_ok()
    
    # Track selected tab and update current_tab reactive value
    @reactive.effect
    def _track_current_tab():
        tab = input.main_tabs()
        if tab:
            current_tab.set(tab)
    
    @render.ui
    def login_card():
        if is_admin() == False:
            return ui.tags.div(
                ui.tags.h4("Admin Login"),
                ui.input_text("username", "Username"),
                ui.input_password("password", "Password"),
                ui.input_action_button("login", "Login"),
                class_="panel-box"
            )
        else:
            return ui.tags.div(
                    ui.tags.h4(f"Hello {reactive_user_name.get()}!"),
                    ui.input_action_button("logout", "Logout"),
                    class_="panel-box"
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
        
    # Filtering
    @render.ui
    def dynamic_control_center():
        if not is_admin():
            return ui.tags.div()
        
        if current_tab.get() == "Incomplete products":
            # Get products to determine dynamic max for slider
            products = get_incompleted_products()
            if isinstance(products, dict) and "error" in products:
                return ui.tags.div(
                    ui.tags.p("Incomplete products"),
                    ui.tags.p(f"Error loading products: {products['error']}", class_="panel-box")
                )
                
            df_tmp = pd.json_normalize(products)
            incomplete_products.set(df_tmp)
            
            total = len(df_tmp.index)
            if total == 0:
                slider = ui.tags.p("No incomplete products available.")
                sort_controls = ui.tags.div()
                search_by_keywords = ui.tags.div()
            else:
                # Control number of producs to show
                default_val = 10 if total >= 10 else total
                slider = ui.input_slider(
                    "incomplete_limit",
                    "Number of products",
                    min=1,
                    max=total,
                    value=default_val,
                    step=1
                )
                
                # Column choices and placeholder
                col_choices = list(df_tmp.columns)
                # Sorting controls with inactive default '-'
                sort_controls = ui.tags.div(
                    ui.input_select(
                        "sort_column",
                        "Sort column",
                        choices=["-"] + col_choices,
                        selected="-"
                    ),
                    ui.input_select(
                        "sort_direction",
                        "Sort order",
                        choices=["-", "ASC", "DESC"],
                        selected="-"
                    ),
                    ui.input_action_button("reset_sort", "Reset", style="width:100%"),
                    style="display:flex; flex-direction:column; gap:1rem;"
                )

                # Search by keywords (independent of sort) with column placeholder
                search_by_keywords = ui.tags.div(
                    ui.input_select(
                        "search_in_column",
                        "Search in column",
                        choices=["-"] + col_choices,
                        selected="-"
                    ),
                    ui.input_text('keywords','Keywords'),
                    ui.input_action_button('reset_search_by_keywords', 'Reset', style="width:100%")
                )
            return ui.tags.div(
                ui.tags.hr(),
                ui.tags.div(
                    slider,
                    class_="panel-box"
                ),
                ui.tags.div(
                    sort_controls,
                    class_="panel-box"
                ),
                ui.tags.div(
                    search_by_keywords,
                    class_="panel-box"
                ),
                ui.tags.div(
                    ui.input_action_button('reset_all', 'Reset all', class_="reset_all_button"),
                    class_="panel-box"
                ),
                style="display:flex; flex-direction:column; gap: 1rem;"
            )
        else:
            return ui.tags.div(
                "Alike products",
                class_="panel-box"
                )

    # INCOMPLETE TAB #
    @render.text
    def incomplete_products_instruction():
        if not is_admin():
            return ""
        return "Click on the product to check and modify its information."
    
    @render.ui
    def incomplete_products_listing():
        if not is_admin():
            return ui.tags.div()
        
        df = incomplete_products.get()
        
        if df.empty:
            return ui.tags.div("No products found.")

        # Apply limit from slider (default 10 if slider not yet mounted)
        limit = 10
        try:
            limit = input.incomplete_limit()
        except Exception:
            pass
        df = df.head(limit)
        
        # Apply search if active (before sorting/limit for efficiency)
        try:
            search_by_keyword_col = input.search_in_column()
            keywords = input.keywords()
            if search_by_keyword_col in df.columns and search_by_keyword_col != "-" and keywords:
                df = df[df[search_by_keyword_col].astype(str).str.contains(keywords, case=False, na=False)]
        except Exception:
            pass

        # Apply sorting if active
        try:
            sort_col = input.sort_column()
            sort_dir = input.sort_direction()
            if sort_col in df.columns and sort_col != "-" and sort_dir in ["ASC", "DESC"]:
                df = df.sort_values(by=sort_col, ascending=(sort_dir == "ASC"))
        except Exception:
            pass
        
        # Decide columns to show
        base_cols = [c for c in ['id', 'name', 'name_search', 'energy', 'protein', 'fat',
           'saturated_fatty_acid', 'carbohydrates', 'unit', 'synonyms', 'brands', 'brands_search', 'bron', 'categories',
           'barcode', 'updated'] if c in df.columns]
        
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
        
    @reactive.effect
    @reactive.event(input.reset_search_by_keywords)
    def _on_reset_search_by_keywords():
        # Clear the keywords text input
        session.send_input_message("search_in_column", {"value": "-"})
        session.send_input_message("keywords", {"value": ""})

    @reactive.effect
    @reactive.event(input.reset_sort)
    def _on_reset_sort():
        # Reset sorting selects to inactive '-'
        session.send_input_message("sort_column", {"value": "-"})
        session.send_input_message("sort_direction", {"value": "-"})
        
    @reactive.effect
    @reactive.event(input.reset_all)
    def _on_reset_all():
        session.send_input_message("search_in_column", {"value": "-"})
        session.send_input_message("keywords", {"value": ""})
        session.send_input_message("sort_column", {"value": "-"})
        session.send_input_message("sort_direction", {"value": "-"})
        
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
            # If product is active (==1) make field unchangeable (read-only)
            is_readonly = ("active" in row.index and row.get("active") == 1)
            if is_readonly:
                return ui.tags.div(
                    ui.tags.label(col_name, **{"for": input_id}, style="font-weight:600; margin-bottom:.25rem;"),
                    ui.tags.div(
                        display_val or "",
                        id=input_id,
                        style="padding:.4rem .55rem; background:#f5f5f5; border:1px solid #ddd; border-radius:.35rem; font-size:.85rem; min-height:2rem; display:flex; align-items:center;"
                    ),
                    style="display:flex; flex-direction:column; width:100%; max-width:320px;"
                )
            else:
                return ui.tags.div(
                    ui.tags.label(col_name, **{"for": input_id}, style="font-weight:600; margin-bottom:.25rem;"),
                    ui.input_text(input_id, None, value=display_val),
                    style="display:flex; flex-direction:column; width:100%; max-width:320px;"
                )

        primary_rows = [render_field(c) for c in primary_fields]
        nutrition_rows = [render_field(c) for c in nutrition_fields]
        other_rows = [render_field(c) for c in other_fields]

        return ui.tags.div(
            ui.tags.div(
            ui.tags.h5("Basic Info"),
            ui.tags.div(
                *primary_rows,
                style="display:grid; grid-template-columns: repeat(3, 1fr); gap:1rem; align-items:start;"
            ),
            style="display:flex; flex-direction:column; gap:.5rem; margin-bottom:1rem;"
            ),
            ui.tags.hr(),
            ui.tags.div(
            ui.tags.h5("Nutrition Info"),
            ui.tags.div(
                *nutrition_rows,
                style="display:grid; grid-template-columns: repeat(3, 1fr); gap:1rem; align-items:start;"
            ),
            style="display:flex; flex-direction:column; gap:.5rem; margin-bottom:1rem;"
            ),
            ui.tags.hr(),
            ui.tags.div(
            ui.tags.h5("Other Fields"),
            ui.tags.div(
                *other_rows,
                style="display:grid; grid-template-columns: repeat(3, 1fr); gap:1rem; align-items:start;"
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
        
        # Safely extract product name from the DataFrame (use first row if present)
        if df is None or df.empty:
            product_name = ""
        elif "name" in df.columns:
            try:
                product_name = df.iloc[0]["name"]
            except Exception:
                product_name = ""
        else:
            product_name = ""
        
        ui.modal_show(
            ui.modal(
                ui.tags.h4(f"Product ID {pid} | {product_name}"),
                ui.tags.hr(),
                ui.output_ui("show_alike_products"),
                ui.tags.hr(),
                ui.output_ui("edit_or_view"),
                ui.input_action_button("save_product", "Save changes"),
                easy_close=True,
                footer=ui.tags.small("Close by clicking outside or Save"),
                size="xl"
            )
        )
        
    @reactive.effect
    @reactive.event(input.show_product_info)
    def _on_show_product_info():
        show_product_info.set(True)
        
    @reactive.effect
    @reactive.event(input.hide_product_info)
    def _on_show_product_info():
        show_product_info.set(False)
        
    @render.ui
    def edit_or_view():
        if product_to_modify.get().iloc[0]["active"] == 1:
            return ui.tags.div(
                ui.output_ui("product_edit_form"),
                style="display:flex; flex-direction:column; gap:1rem;"
            )
            
        # Dynamically render the edit/view region inside the modal
        # Re-renders when show_product_info or product_to_modify changes
        try:
            show = show_product_info.get()
        except Exception:
            show = False
        if show:
            return ui.tags.div(
                ui.input_action_button('hide_product_info', 'Close'),
                ui.output_ui("product_edit_form"),
                style="display:flex; flex-direction:column; gap:1rem;"
            )
        else:
            return ui.input_action_button('show_product_info', 'Edit / Show info')
        

    @render.ui
    def show_alike_products():
        df_selected = product_to_modify.get()
        if df_selected is None or df_selected.empty:
            return ui.tags.div()
        
        product_id = df_selected.iloc[0]['id']
        cluster_id = df_selected.iloc[0]['cluster_id']
        
        df_alike_products = get_alike_products(product_id, cluster_id)
        
        # Handle possible error response
        if isinstance(df_alike_products, dict) and "error" in df_alike_products:
            return ui.tags.div(ui.tags.small("This product has no alike products"), class_="panel-box")

        # Normalize into DataFrame
        try:
            df_alike = pd.json_normalize(df_alike_products)
        except Exception:
            try:
                df_alike = pd.DataFrame(df_alike_products)
            except Exception:
                df_alike = pd.DataFrame()

        if df_alike.empty:
            return ui.tags.div(ui.tags.small("No alike products found."), class_="panel-box")
        
        df_alike_verified = df_alike[df_alike['active'] == 1]
        df_alike_unverified = df_alike[df_alike['active'] == 0]
        
        # Choose sensible columns to display if present
        show_cols = [c for c in ['id', 'name', 'energy', 'protein', 'categories','barcode'] if c in df_alike.columns]

        header_verified = ui.tags.tr(
            *[ui.tags.th(c, style="padding:.25rem .5rem; text-align:left; border:1px solid #ddd;") for c in show_cols]
        )

        body_rows_verified = []
        for _, r in df_alike_verified.iterrows():
            pid = r.get("id")
            cells = [
            ui.tags.td(str(r.get(c, "")), style="padding:.25rem .5rem; vertical-align:top; border:1px solid #ddd;")
            for c in show_cols
            ]
            onclick = f"Shiny.setInputValue('modify_product_row', {repr(pid)}, {{priority: 'event'}});"
            body_rows_verified.append(
            ui.tags.tr(
                *cells,
                onclick=onclick,
                class_="incompleted_table_rows",
                style="cursor:pointer;"
            )
            )

        table_verified = ui.tags.table(
            ui.tags.thead(header_verified),
            ui.tags.tbody(*body_rows_verified),
            style="width:100%; border-collapse:collapse; font-size:.75rem; border:1px solid #ddd;"
        )
        
        header_unverified = ui.tags.tr(
            *[ui.tags.th(c, style="padding:.25rem .5rem; text-align:left; border:1px solid #ddd;") for c in show_cols]
        )

        body_rows_unverified = []
        for _, r in df_alike_unverified.iterrows():
            pid = r.get("id")
            cells = [
            ui.tags.td(str(r.get(c, "")), style="padding:.25rem .5rem; vertical-align:top; border:1px solid #ddd;")
            for c in show_cols
            ]
            onclick = f"Shiny.setInputValue('modify_product_row', {repr(pid)}, {{priority: 'event'}});"
            body_rows_unverified.append(
            ui.tags.tr(
                *cells,
                onclick=onclick,
                class_="incompleted_table_rows",
                style="cursor:pointer;"
            )
            )

        table_unverified = ui.tags.table(
            ui.tags.thead(header_unverified),
            ui.tags.tbody(*body_rows_unverified),
            style="width:100%; border-collapse:collapse; font-size:.75rem; border:1px solid #ddd;"
        )

        return ui.tags.div(
            ui.tags.h5(f"Alike products"),
            ui.tags.p("Verified products:", style="margin-top:2rem;"),
            table_verified,
            ui.tags.p("Unverified products:", style="margin-top:2rem;"),
            table_unverified,
            style="width: 100%;"
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
