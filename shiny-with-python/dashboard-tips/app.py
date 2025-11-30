import ast
import string
import faicons as fa
import plotly.express as px
import requests
import re
import json
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
            ui.nav_panel("Incomplete products with alike products", 
                         ui.output_ui("incomplete_products_with_alike_products_listing")),
            ui.nav_panel("Unique incomplete products",
                         ui.output_ui("incomplete_products_without_alike_products_listing")),
            id="main_tabs",
            selected="Incomplete products with alike products"
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
    incomplete_products_with_alike_products = reactive.Value(pd.DataFrame())
    incomplete_products_without_alike_products = reactive.Value(pd.DataFrame())
    class _ClickedProducts:
        def __init__(self):
            self._rv = reactive.Value([])  # This will be a list of product dicts

        def get(self):
            return self._rv.get()

        def set(self, v):
            self._rv.set(v)

        def append(self, product_dict):
            cur = list(self._rv.get() or [])
            # Avoid duplicates by checking for pid
            if not any(p.get('id') == product_dict.get('id') for p in cur):
                cur.append(product_dict)
                self._rv.set(cur)
            
        def remove(self, pid):
            cur = list(self._rv.get() or [])
            # Remove the dictionary with the matching pid
            cur = [p for p in cur if p.get('id') != pid]
            self._rv.set(cur)
            
        def remove_all(self):
            self._rv.set([])

    clicked_products = _ClickedProducts()
    # current_tab = reactive.Value("Incomplete products with alike products")
    
    # --------------------------------- #
    # LOG IN                            #
    # --------------------------------- #
    @reactive.calc
    def is_admin():
        return login_ok()
    
    # Track selected tab and update current_tab reactive value
    # @reactive.effect
    # def _track_current_tab():
    #     tab = input.main_tabs()
    #     if tab:
    #         current_tab.set(tab)
    
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
            products = get_incompleted_products()
            if isinstance(products, dict) and "error" in products:
                return ui.tags.div(
                    ui.tags.p("Incomplete products"),
                    ui.tags.p(f"Error loading products: {products['error']}", class_="panel-box")
                )
                
            df_tmp = pd.json_normalize(products)
            
            df_with_alike_products = df_tmp[df_tmp['cluster_count'] != 1]
            df_without_alike_products = df_tmp[df_tmp['cluster_count'] == 1]
            
            incomplete_products_with_alike_products.set(df_with_alike_products)
            incomplete_products_without_alike_products.set(df_without_alike_products)
            
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
        # if not is_admin():
        #     return ui.tags.div()
        
        products = get_incompleted_products()
        if isinstance(products, dict) and "error" in products:
            return ui.tags.div(
                ui.tags.p("Incomplete products"),
                ui.tags.p(f"Error loading products: {products['error']}", class_="panel-box")
            )
            
        df_tmp = pd.json_normalize(products)
        
        df_with_alike_products = df_tmp[df_tmp['cluster_count'] != 1]
        df_without_alike_products = df_tmp[df_tmp['cluster_count'] == 1]
        
        incomplete_products_with_alike_products.set(df_with_alike_products)
        incomplete_products_without_alike_products.set(df_without_alike_products)

        # General keyword search across all columns
        search_by_keywords = ui.tags.div(
            ui.input_text('keywords','Search'),
            ui.input_action_button('reset_search_by_keywords', 'Reset', style="width:100%")
        )
        return ui.tags.div(
            ui.tags.hr(),
            ui.tags.div(
                search_by_keywords,
                class_="panel-box"
            ),
            style="display:flex; flex-direction:column; gap: 1rem;"
        )

    # INCOMPLETE TAB #
    @render.text
    def incomplete_products_instruction():
        # if not is_admin():
        #     return ""
        return "Click on the product to check and modify its information."
    
    # Render table
    def render_table(df: pd.DataFrame, title: str):
        if df is None or df.empty:
            return ui.tags.div(ui.tags.h5(title), ui.tags.p("No products.", style="color:#666;"))

        # Decide columns to show (use sensible defaults if present)
        base_cols = [c for c in ['id', 'name', 'energy', 'unit', 'synonyms', 'brands', 'categories', 'updated'] if c in df.columns]

        header = ui.tags.tr(
            *[ui.tags.th(col, style="padding:.25rem .5rem; text-align:left; border:1px solid #ddd;") for col in base_cols]
        )
        body_rows = []
        for _, row in df.iterrows():
            pid = row.get("id")
            cells = [ui.tags.td(str(row.get(
                col, "")), style="padding:.25rem .5rem; vertical-align:top; border: 1px solid #ddd;") for col in base_cols]
            onclick = f"Shiny.setInputValue('modify_product_row', {repr(pid)}, {{priority: 'event'}});"
            body_rows.append(
                ui.tags.tr(
                    *cells,
                    onclick=onclick,
                    class_="incompleted_table_rows",
                    style="cursor:pointer;"
                )
            )

        table = ui.tags.table(
            ui.tags.thead(header),
            ui.tags.tbody(*body_rows),
            style="font-size:.85rem; border:1px solid #ddd;"
        )
        
        return ui.tags.div(
            ui.tags.h5(f"{title}"),
            table,
            style="margin-bottom:1rem;"
        )
    
    @render.ui
    def incomplete_products_with_alike_products_listing():
        # if not is_admin():
        #     return ui.tags.div()
        
        df_with = incomplete_products_with_alike_products.get()
        
        if (df_with is None or df_with.empty):
            return ui.tags.div("No products found.")

        # Apply general keyword search
        try:
            keywords = input.keywords()
            if keywords:
                mask = df_with.astype(str).apply(lambda col: col.str.contains(keywords, case=False, na=False))
                df_with = df_with[mask.any(axis=1)]
        except Exception:
            pass

        table_with = render_table(df_with, "There are similar products to these products:")

        return ui.tags.div(
            table_with,
            style="display:flex; flex-direction:column; gap:1rem; margin-top:1rem; margin-bottom:1rem;"
        )
        
    @render.ui
    def incomplete_products_without_alike_products_listing():
        # if not is_admin():
        #     return ui.tags.div()
        
        df_without = incomplete_products_without_alike_products.get()
        
        if (df_without is None or df_without.empty):
            return ui.tags.div("No products found.")

        # Apply general keyword search
        try:
            keywords = input.keywords()
            if keywords:
                mask = df_without.astype(str).apply(lambda col: col.str.contains(keywords, case=False, na=False))
                df_without = df_without[mask.any(axis=1)]
        except Exception:
            pass

        table_without = render_table(df_without, "These products are unique:")

        return ui.tags.div(
            table_without,
            style="display:flex; flex-direction:column; gap:1rem; margin-top:1rem; margin-bottom:1rem;"
        )
        
    @reactive.effect
    @reactive.event(input.reset_search_by_keywords)
    def _on_reset_search_by_keywords():
        # Clear the keywords text input
        session.send_input_message("keywords", {"value": ""})
        
    @reactive.effect
    @reactive.event(input.reset_all)
    def _on_reset_all():
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
        
        if df.iloc[0]['active'] == 1:
            save_changes_button = ui.tags.div()
        else:
            save_changes_button = ui.input_action_button('save_changes', "Save changes",
                                                         style='width: 15rem')

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
                style="display:flex; flex-direction:column; gap:.5rem; margin-bottom:1rem;"
            ),
            save_changes_button,
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
        
        close_edit_form_button = ui.input_action_button('close_edit_form', 'X',
                                                        style='border: 1px solid #ddd; height: 30px; width: 30px; text-align: center; padding: 0')
        
        ui.modal_show(
            ui.modal(
                ui.tags.div(
                    ui.tags.h4(f"Product ID {pid} | {product_name}"),
                    close_edit_form_button,
                    style='display: flex; flex-direction: row; justify-content: space-between'
                ),
                ui.tags.hr(),
                ui.output_ui("show_alike_products"),
                ui.tags.hr(),
                ui.output_ui("product_edit_form"),
                # This is to remove the default "Dismiss" button
                footer=ui.tags.div(),
                size="xl"
            )
        )

    # Close the currently open modal when the X button is clicked
    @reactive.effect
    @reactive.event(input.close_edit_form)
    def _on_close_edit_form():
        clicked_products.remove_all()
        ui.modal_remove()

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
            ui.tags.th("", style="padding:.25rem .5rem; text-align:center; border:1px solid #ddd; width:2rem;"),
            *[ui.tags.th(c, style="padding:.25rem .5rem; text-align:left; border:1px solid #ddd;") for c in show_cols],
            ui.tags.th("Action", style="padding:.25rem .5rem; text-align:left; border:1px solid #ddd;")
        )

        clicked_list = clicked_products.get() or []
        has_clicked_items = len(clicked_list) > 0

        body_rows_verified = []
        for _, r in df_alike_verified.iterrows():
            pid = r.get("id")
            product_json = json.dumps(r.to_dict())
            # Checkbox cell (prevent row click when toggled)
            is_checked = any(p.get('id') == pid for p in clicked_list)
            checkbox_td = ui.tags.td(
                ui.tags.input(
                    type="checkbox",
                    id=f"alike_select_verified_{pid}",
                    checked="checked" if is_checked else None,
                    onclick=f"event.stopPropagation(); Shiny.setInputValue('toggle_checked_product', {{'product': {product_json}, 'checked': event.target.checked}}, {{priority: 'event'}})"
                ),
                style="padding:.25rem .5rem; vertical-align:top; border:1px solid #ddd; text-align:center;"
            )

            link_btn = ui.tags.div()
            if has_clicked_items and not is_checked:
                link_btn = ui.tags.button(
                    "Link",
                    type="button",
                    onclick=f"event.stopPropagation(); Shiny.setInputValue('link_product', {repr(pid)}, {{priority: 'event'}})",
                    style="padding: 2px 6px; font-size: 0.75rem; cursor: pointer;"
                )
            
            action_td = ui.tags.td(
                link_btn,
                style="padding:.25rem .5rem; vertical-align:top; border:1px solid #ddd;"
            )

            cells = [
            ui.tags.td(str(r.get(c, "")), style="padding:.25rem .5rem; vertical-align:top; border:1px solid #ddd;")
            for c in show_cols
            ]
            onclick = f"Shiny.setInputValue('modify_product_row', {repr(pid)}, {{priority: 'event'}});"
            body_rows_verified.append(
            ui.tags.tr(
                checkbox_td,
                *cells,
                action_td,
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
            ui.tags.th("", style="padding:.25rem .5rem; text-align:center; border:1px solid #ddd; width:2rem;"),
            *[ui.tags.th(c, style="padding:.25rem .5rem; text-align:left; border:1px solid #ddd;") for c in show_cols],
            ui.tags.th("Action", style="padding:.25rem .5rem; text-align:left; border:1px solid #ddd;")
        )

        body_rows_unverified = []
        for _, r in df_alike_unverified.iterrows():
            pid = r.get("id")
            product_json = json.dumps(r.to_dict())
            
            # Checkbox cell (prevent row click when toggled)
            is_checked = any(p.get('id') == pid for p in clicked_list)
            checkbox_td = ui.tags.td(
                ui.tags.input(
                    type="checkbox", 
                    id=f"alike_select_unverified_{pid}", 
                    checked="checked" if is_checked else None,
                    onclick=f"event.stopPropagation(); Shiny.setInputValue('toggle_checked_product', {{'product': {product_json}, 'checked': event.target.checked}}, {{priority: 'event'}})"
                ),
                style="padding:.25rem .5rem; vertical-align:top; border:1px solid #ddd; text-align:center;"
            )

            link_btn = ui.tags.div()
            if has_clicked_items and not is_checked:
                link_btn = ui.tags.button(
                    "Link",
                    type="button",
                    onclick=f"event.stopPropagation(); Shiny.setInputValue('link_product', {repr(pid)}, {{priority: 'event'}})",
                    style="padding: 2px 6px; font-size: 0.75rem; cursor: pointer;"
                )
            
            action_td = ui.tags.td(
                link_btn,
                style="padding:.25rem .5rem; vertical-align:top; border:1px solid #ddd;"
            )

            cells = [
            ui.tags.td(str(r.get(c, "")), style="padding:.25rem .5rem; vertical-align:top; border:1px solid #ddd;")
            for c in show_cols
            ]
            onclick = f"Shiny.setInputValue('modify_product_row', {repr(pid)}, {{priority: 'event'}});"
            body_rows_unverified.append(
            ui.tags.tr(
                checkbox_td,
                *cells,
                action_td,
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
        
    @reactive.effect
    @reactive.event(input.toggle_checked_product)
    def _on_toggle_checked_product():
        data = input.toggle_checked_product()
        product_dict = data['product']
        is_checked = data['checked']
        if is_checked:
            clicked_products.append(product_dict)
        else:
            clicked_products.remove(product_dict.get('id'))


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
