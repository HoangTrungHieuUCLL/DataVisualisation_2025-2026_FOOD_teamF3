import ast
import string
import faicons as fa
import plotly.express as px
import requests
import re
import json
from services import get_incompleted_products, get_product_info, get_all_products, get_alike_products, link_product, get_incomplete_products_with_alike_products, update_product_info


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
    alike_products = reactive.Value(pd.DataFrame())
    incomplete_products_without_alike_products = reactive.Value(pd.DataFrame())
    target_link_id = reactive.Value(None)
    products_to_compare = reactive.Value(pd.DataFrame())
    chart_type = reactive.Value("bar")
    
    class _ClickedProducts:
        def __init__(self):
            self._rv = reactive.Value([])  # This will be a list of product dicts

        def get(self):
            return self._rv.get()

        def set(self, v):
            self._rv.set(v)

        def append(self, pid):
            # Accept only a pid and store it if not already present
            if pid is None:
                return
            cur = list(self._rv.get() or [])
            
            if pid not in cur:
                cur.append(pid)
            self._rv.set(cur)
            
        def remove(self, pid):
            # Remove the pid from the stored list of pids
            cur = list(self._rv.get() or [])
            cur = [p for p in cur if p != pid]
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
        if not is_admin():
            return ui.tags.div()
        
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
        if not is_admin():
            return ""
        return "Click on the product to check and modify its information."
    
    # Render table
    def render_table(df: pd.DataFrame, title: str):
        if df is None or df.empty:
            return ui.tags.div(ui.tags.h5(title), ui.tags.p("No products.", style="color:#666;"))

        # Decide columns to show (use sensible defaults if present)
        base_cols = [c for c in ['id', 'name', 'energy', 'unit', 'synonyms', 'brands', 'categories', 'link_to'] if c in df.columns]

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
        if not is_admin():
            return ui.tags.div()
        
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
        if not is_admin():
            return ui.tags.div()
        
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
        primary_fields = ["id", "name", "link_to", "name_search", "active", "unit", "synonyms", "brands", "brands_search", "categories", "barcode", "bron"]
        nutrition_fields = ["energy", "protein", "fat", "saturated_fatty_acid", "carbohydrates", "sugar", "starch", "dietary_fiber", "salt", "sodium", "k", "ca", "p", "fe", "polyols", "cholesterol", "omega3", "omega6", "mov", "eov", "vit_a", "vit_b12", "vit_b6", "vit_b1", "vit_b2", "vit_c", "vit_d", "mg", "water", "remarks_carbohydrates", "glucose", "fructose", "excess_fructose", "lactose", "sorbitol", "mannitol", "fructans", "gos"]
        other_fields = [c for c in df.columns if c not in primary_fields + nutrition_fields]

        def render_field(col_name: str):
            input_id = f"edit_{_sanitize_id(col_name)}"
            val = row[col_name] if col_name in row.index else None
            display_val = "" if (val is None or (isinstance(val, float) and pd.isna(val)) or (isinstance(val, str) and val == "nan")) else str(val)
            # If product is active (==1) make field unchangeable (read-only)
            # Also make 'id' and 'link_to' read-only
            is_readonly = ("active" in row.index and row.get("active") == 1) or (col_name in ["id", "link_to", "cluster_id", "cluster_count", "app_ver", "created", "updated", "token"])
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
                if col_name == "active":
                    return ui.tags.div(
                        ui.tags.label(col_name, **{"for": input_id}, style="font-weight:600; margin-bottom:.25rem;"),
                        ui.input_select(input_id, None, choices={"0": "0", "1": "1"}, selected=display_val),
                        style="display:flex; flex-direction:column; width:100%; max-width:320px;"
                    )
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
            save_changes_button = ui.input_action_button('save_product', "Save changes",
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
        
        cur_clicked = clicked_products.get() or []
        if pid not in cur_clicked:
            clicked_products.remove_all()
        
        response_product = get_product_info(pid)
        df = pd.json_normalize(response_product)
        
        if df.iloc[0]['active'] == 0:
            clicked_products.append(pid)
        else:
            clicked_products.remove_all()
            
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
        
        is_active = df.iloc[0]['active'] == 1
        status_text = "Verified" if is_active else "Unverified"
        status_color = "green" if is_active else "red"

        ui.modal_show(
            ui.modal(
                ui.tags.div(
                    ui.tags.div(
                        ui.tags.h4(f"Product ID {pid} | {product_name}"),
                        ui.tags.h5(status_text, style=f"color: {status_color}; margin-top: 0;")
                    ),
                    close_edit_form_button,
                    style='display: flex; flex-direction: row; justify-content: space-between'
                ),
                ui.tags.hr(),
                ui.output_ui("show_alike_products"),
                ui.tags.hr(),
                ui.output_ui("product_edit_form"),
                ui.output_ui("link_confirmation_dialog"),
                ui.output_ui("compare_dialog"),
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
        current_product_active = df_selected.iloc[0]['active']
        
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
                
        alike_products.set(df_alike)

        # Use the reactive alike_products instead of the local df_alike variable
        df_alike = alike_products.get()

        if df_alike is None:
            return ui.tags.div(ui.tags.small("No alike products found."), class_="panel-box")

        # Ensure we have a DataFrame
        try:
            if df_alike.empty:
                return ui.tags.div(ui.tags.small("No alike products found."), class_="panel-box")
        except Exception:
            try:
                df_alike = pd.json_normalize(df_alike)
                if df_alike.empty:
                    return ui.tags.div(ui.tags.small("No alike products found."), class_="panel-box")
            except Exception:
                return ui.tags.div(ui.tags.small("No alike products found."), class_="panel-box")
        
        # Split verified / unverified safely
        if "active" in df_alike.columns:
            df_alike_verified = df_alike[df_alike["active"] == 1]
            df_alike_unverified = df_alike[(df_alike["active"] == 0) & (df_alike["link_to"].isnull())]
        
        # Choose sensible columns to display if present
        show_cols = [c for c in ['id', 'name', 'energy', 'protein', 'categories'] if c in df_alike.columns]

        clicked_list = clicked_products.get() or []
        has_clicked_items = len(clicked_list) > 0
        
        # Count checked verified products
        verified_ids = df_alike_verified['id'].tolist() if not df_alike_verified.empty else []
        checked_verified_count = sum(1 for pid in clicked_list if pid in verified_ids)
        
        # Verified Header Checkbox
        all_verified_checked = bool(verified_ids) and all(pid in clicked_list for pid in verified_ids)
        verified_checkbox_header = ui.tags.input(
            type="checkbox",
            checked="checked" if all_verified_checked else None,
            onclick=f"event.stopPropagation(); Shiny.setInputValue('toggle_all_products', {{'ids': {repr(verified_ids)}, 'checked': event.target.checked}}, {{priority: 'event'}})"
        )

        header_verified = ui.tags.tr(
            ui.tags.th(verified_checkbox_header, style="padding:.25rem .5rem; text-align:center; border:1px solid #ddd; width:2rem;"),
            *[ui.tags.th(c, style="padding:.25rem .5rem; text-align:left; border:1px solid #ddd;") for c in show_cols],
            ui.tags.th("Action", style="padding:.25rem .5rem; text-align:left; border:1px solid #ddd;")
        )

        body_rows_verified = []
        for _, r in df_alike_verified.iterrows():
            pid = r.get("id")
            
            # Checkbox cell (prevent row click when toggled)
            is_checked = any(p == pid for p in clicked_list)
            checkbox_td = ui.tags.td(
                ui.tags.input(
                    type="checkbox",
                    id=f"alike_select_verified_{pid}",
                    checked="checked" if is_checked else None,
                    onclick=f"event.stopPropagation(); Shiny.setInputValue('toggle_checked_product', {{'pid': {repr(pid)}, 'checked': event.target.checked}}, {{priority: 'event'}})"
                ),
                style="padding:.25rem .5rem; vertical-align:top; border:1px solid #ddd; text-align:center;"
            )
            

            if current_product_active == 0 and not is_checked:
                if checked_verified_count <= 1:
                    link_btn = ui.tags.button(
                        "Link",
                        type="button",
                        onclick=f"event.stopPropagation(); Shiny.setInputValue('link_product', {repr(pid)}, {{priority: 'event'}})",
                        style="padding: 2px 6px; font-size: 0.75rem; cursor: pointer;"
                    )
                else:
                    link_btn = ui.tags.div()

                compare_btn = ui.tags.button(
                    "Compare",
                    type="button",
                    onclick=f"event.stopPropagation(); Shiny.setInputValue('compare_products', {repr(pid)}, {{priority: 'event'}})",
                    style="padding: 2px 6px; font-size: 0.75rem; cursor: pointer;"
                )

            else:
                link_btn = ui.tags.div()
                compare_btn = ui.tags.div()
            
            
            action_td = ui.tags.td(
                link_btn,
                compare_btn,
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
                style="cursor:pointer; height: 20px;"
            )
            )

        table_verified = ui.tags.table(
            ui.tags.thead(header_verified),
            ui.tags.tbody(*body_rows_verified),
            style="width:100%; border-collapse:collapse; font-size:.75rem; border:1px solid #ddd;"
        )
        
        # Unverified Header Checkbox
        unverified_ids = df_alike_unverified['id'].tolist() if not df_alike_unverified.empty else []
        all_unverified_checked = bool(unverified_ids) and all(pid in clicked_list for pid in unverified_ids)
        
        if current_product_active == 0:
            unverified_checkbox_header = ui.tags.input(
                type="checkbox",
                checked="checked" if all_unverified_checked else None,
                onclick=f"event.stopPropagation(); Shiny.setInputValue('toggle_all_products', {{'ids': {repr(unverified_ids)}, 'checked': event.target.checked}}, {{priority: 'event'}})"
            )
        else:
            unverified_checkbox_header = ""

        header_unverified = ui.tags.tr(
            ui.tags.th(unverified_checkbox_header, style="padding:.25rem .5rem; text-align:center; border:1px solid #ddd; width:2rem;"),
            *[ui.tags.th(c, style="padding:.25rem .5rem; text-align:left; border:1px solid #ddd;") for c in show_cols],
            ui.tags.th("Action", style="padding:.25rem .5rem; text-align:left; border:1px solid #ddd;")
        )

        body_rows_unverified = []
        for _, r in df_alike_unverified.iterrows():
            pid = r.get("id")
            
            # Checkbox cell (prevent row click when toggled)
            is_checked = any(p == pid for p in clicked_list)
            
            if current_product_active == 0:
                checkbox_input = ui.tags.input(
                    type="checkbox", 
                    id=f"alike_select_unverified_{pid}", 
                    checked="checked" if is_checked else None,
                    onclick=f"event.stopPropagation(); Shiny.setInputValue('toggle_checked_product', {{'pid': {repr(pid)}, 'checked': event.target.checked}}, {{priority: 'event'}})"
                )
            else:
                checkbox_input = ""

            checkbox_td = ui.tags.td(
                checkbox_input,
                style="padding:.25rem .5rem; vertical-align:top; border:1px solid #ddd; text-align:center;"
            )

            if current_product_active == 0 and not is_checked:
                link_btn = ui.tags.button(
                    "Link",
                    type="button",
                    onclick=f"event.stopPropagation(); Shiny.setInputValue('link_product', {repr(pid)}, {{priority: 'event'}})",
                    style="padding: 2px 6px; font-size: 0.75rem; cursor: pointer;"
                )
                compare_btn = ui.tags.button(
                    "Compare",
                    type="button",
                    onclick=f"event.stopPropagation(); Shiny.setInputValue('compare_products', {repr(pid)}, {{priority: 'event'}})",
                    style="padding: 2px 6px; font-size: 0.75rem; cursor: pointer;"
                )

            else:
                link_btn = ui.tags.div()
                compare_btn = ui.tags.div()
            
            
            action_td = ui.tags.td(
                link_btn,
                compare_btn,
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
                style="cursor:pointer; height: 20px;"
            )
            )

        table_unverified = ui.tags.table(
            ui.tags.thead(header_unverified),
            ui.tags.tbody(*body_rows_unverified),
            style="width:100%; border-collapse:collapse; font-size:.75rem; border:1px solid #ddd;"
        )

        compare_selected_btn = ui.tags.div()
        if len(clicked_list) > 1:
            first_pid = clicked_list[0]
            compare_selected_btn = ui.tags.button(
                "Compare the selected products",
                type="button",
                onclick=f"event.stopPropagation(); Shiny.setInputValue('compare_products', {repr(first_pid)}, {{priority: 'event'}})",
                class_="btn btn-primary",
                style="margin-top: 10px; margin-bottom: 10px;"
            )

        return ui.tags.div(
            ui.tags.h5(f"Alike products"),
            compare_selected_btn,
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
        pid = data['pid']
        is_checked = data['checked']
        if is_checked:
            clicked_products.append(pid)
        else:
            clicked_products.remove(pid)

    @reactive.effect
    @reactive.event(input.toggle_all_products)
    def _on_toggle_all_products():
        data = input.toggle_all_products()
        ids = data['ids']
        is_checked = data['checked']
        
        current_clicked = list(clicked_products.get() or [])
        
        if is_checked:
            # Add all ids that are not already in clicked_products
            for pid in ids:
                if pid not in current_clicked:
                    current_clicked.append(pid)
        else:
            # Remove all ids from clicked_products
            current_clicked = [p for p in current_clicked if p not in ids]
            
        clicked_products.set(current_clicked)
            
    @render.ui
    def link_confirmation_dialog():
        pid = target_link_id.get()
        if pid is None:
            return ui.tags.div()
        
        clicked_list = clicked_products.get() or []
        message = f"{', '.join(map(str, clicked_list))} ➡️➡️➡️ {pid}"
        
        return ui.tags.div(
            ui.tags.div(
                ui.tags.h5("Link these products?"),
                ui.tags.h5(message),
                ui.tags.div(
                    ui.input_action_button("confirm_link", "Confirm", class_="btn btn-primary"),
                    ui.input_action_button("cancel_link", "Cancel", class_="btn btn-secondary"),
                    style="display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px;"
                ),
                style="background: white; padding: 20px; border-radius: 5px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: 400px; max-width: 90%;"
            ),
            style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); display: flex; justify-content: center; align-items: center; z-index: 10000;"
        )

    @reactive.effect
    @reactive.event(input.link_product)
    def _on_link_product():
        pid = input.link_product()
        target_link_id.set(pid)

    @reactive.effect
    @reactive.event(input.confirm_link)
    def _on_confirm_link():
        link_to_product_id = target_link_id.get()
        if link_to_product_id is not None:
            for pid in clicked_products.get():
                response = link_product(pid, link_to_product_id)
                get_updated_product(pid)
        target_link_id.set(None)

    @reactive.effect
    @reactive.event(input.cancel_link)
    def _on_cancel_link():
        target_link_id.set(None)

    def get_updated_product(pid):
        product_to_modify_id = product_to_modify.get().iloc[0]['id']
        
        if pid == product_to_modify_id:
            response = get_product_info(pid)
            updated_product_pd = pd.json_normalize(response)
            product_to_modify.set(updated_product_pd)
            
            response_2 = get_alike_products(pid, updated_product_pd.iloc[0]['cluster_id'])
            updated_alike_products_pd = pd.json_normalize(response_2)
            alike_products.set(updated_alike_products_pd)
            

        response = get_incomplete_products_with_alike_products()
        products = pd.json_normalize(response)
        incomplete_products_with_alike_products.set(products)

    @reactive.effect
    @reactive.event(input.compare_products)
    def _on_compare_products():
        product_to_compare_with_pid = input.compare_products()
        
        # Get the list of clicked product IDs
        clicked_pids = clicked_products.get() or []
        
        # Combine all IDs: clicked products + the one triggered by the compare button
        all_pids = list(set(clicked_pids + [product_to_compare_with_pid]))
        
        # Fetch product info for each ID and collect into a list
        products_list = []
        for pid in all_pids:
            p_info = get_product_info(pid)
            # If get_product_info returns a dict (single product), append it
            if isinstance(p_info, dict) and "error" not in p_info:
                products_list.append(p_info)
        
        # Convert list of dicts to DataFrame
        if products_list:
            df_compare = pd.DataFrame(products_list)
        else:
            df_compare = pd.DataFrame()
            
        products_to_compare.set(df_compare)

    @reactive.effect
    @reactive.event(input.show_radar)
    def _on_show_radar():
        chart_type.set("radar")

    @reactive.effect
    @reactive.event(input.show_bar)
    def _on_show_bar():
        chart_type.set("bar")
            
    @render.ui
    def compare_dialog():
        
        df = products_to_compare.get()
        if df is None or df.empty:
            return ui.tags.div()

        # Choose an identifier column to label rows in the chart
        if "id" in df.columns:
            id_col = "id"
        elif "name" in df.columns:
            id_col = "name"
        else:
            df = df.reset_index().rename(columns={"index": "row"})
            id_col = "row"

        # Select numeric columns
        numeric_cols = ["energy", "protein", "fat", "saturated_fatty_acid", "carbohydrates", "sugar", "starch", "dietary_fiber", "salt", "sodium", "k", "ca", "p", "fe", "polyols", "cholesterol", "omega3", "omega6", "mov", "eov", "vit_a", "vit_b12", "vit_b6", "vit_b1", "vit_b2", "vit_c", "vit_d", "mg", "water", "remarks_carbohydrates", "glucose", "fructose", "excess_fructose", "lactose", "sorbitol", "mannitol", "fructans", "gos"]
        
        # Filter numeric_cols to only those present in df and not all NaNs
        numeric_cols = [c for c in numeric_cols if c in df.columns and df[c].notna().any()]
        
        # Prepare data for grouped bar chart: one group per metric, one bar per row (product)
        if numeric_cols:
            df_plot = df[[id_col] + numeric_cols].copy()
            df_plot[id_col] = df_plot[id_col].astype(str)
            
            # Replace remaining NaNs with 0
            df_plot = df_plot.fillna(0)
            
            df_melt = df_plot.melt(id_vars=id_col, value_vars=numeric_cols, var_name="metric", value_name="value")
        else:
            df_melt = pd.DataFrame()

        # Render the plotly chart into a widget output
        @render_plotly
        def compare_plot_bar():
            if df_melt.empty:
                return None
            fig = px.bar(
                df_melt,
                x="metric",
                y="value",
                color=id_col,
                barmode="group",
            )
            fig.update_layout(height=650, legend_title_text=id_col, xaxis_title="Metric", yaxis_title="Value")
            return fig

        @render_plotly
        def compare_plot_radar():
            if df_melt.empty:
                return None
            fig = px.line_polar(
                df_melt,
                r="value",
                theta="metric",
                color=id_col,
                line_close=True
            )
            fig.update_traces(fill='toself', mode='lines+markers')
            fig.update_layout(height=650, legend_title_text=id_col)
            return fig
            
        close_btn = ui.input_action_button("close_compare", "Close")

        # Metadata table
        meta_cols = ["id", "name", "link_to", "name_search", "active", "unit", "synonyms", "brands", "brands_search", "categories", "barcode", "bron"]
        meta_cols = [c for c in meta_cols if c in df.columns]
        
        if meta_cols:
            header_row = ui.tags.tr(
                *[ui.tags.th(c, style="padding: 5px; border: 1px solid #ddd; background-color: #f9f9f9;") for c in meta_cols]
            )
            
            body_rows = []
            for _, row in df.iterrows():
                cells = [ui.tags.td(str(row[c]), style="padding: 5px; border: 1px solid #ddd;") for c in meta_cols]
                body_rows.append(ui.tags.tr(*cells))
            
            meta_table = ui.tags.table(
                ui.tags.thead(header_row),
                ui.tags.tbody(*body_rows),
                style="width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 0.85rem;"
            )
        else:
            meta_table = ui.tags.div("No metadata available.")

        # Calculate difference scores
        diff_scores_ui = ui.tags.div()
        if numeric_cols and "active" in df.columns:
            # Use df_plot which has NaNs filled with 0
            df_calc = df_plot.copy()
            df_calc['active'] = df['active'].values
            
            verified_df = df_calc[df_calc['active'] == 1]
            unverified_df = df_calc[df_calc['active'] == 0]
            
            if not verified_df.empty and not unverified_df.empty:
                if len(verified_df) > 1:
                    # Matrix: Unverified vs Each Verified
                    verified_ids = verified_df[id_col].astype(str).tolist()
                    header_cells = [ui.tags.th("Unverified Product", style="padding: 5px; border: 1px solid #ddd; background-color: #f9f9f9;")]
                    for vid in verified_ids:
                        header_cells.append(ui.tags.th(f"{vid}", style="padding: 5px; border: 1px solid #ddd; background-color: #f9f9f9;"))
                    
                    header_row = ui.tags.tr(*header_cells)
                    
                    body_rows = []
                    for _, u_row in unverified_df.iterrows():
                        u_id = str(u_row[id_col])
                        row_cells = [ui.tags.td(u_id, style="padding: 5px; border: 1px solid #ddd; font-weight: bold;")]
                        
                        # Calculate distances first to find min
                        dists = []
                        for _, v_row in verified_df.iterrows():
                            diff = u_row[numeric_cols] - v_row[numeric_cols]
                            dist = (diff ** 2).sum() ** 0.5
                            dists.append(dist)
                        
                        min_dist = min(dists) if dists else -1

                        for dist in dists:
                            style = "padding: 5px; border: 1px solid #ddd;"
                            if dist == min_dist:
                                style += " color: red; font-weight: bold;"
                            row_cells.append(ui.tags.td(f"{dist:.2f}", style=style))
                        
                        body_rows.append(ui.tags.tr(*row_cells))
                    
                    diff_scores_ui = ui.tags.div(
                        ui.tags.h5("Similarity score"),
                        ui.tags.p("* lower = more similar", style="margin-top: 10px; color: red"),
                        ui.tags.table(
                            ui.tags.thead(header_row),
                            ui.tags.tbody(*body_rows),
                            style="width: auto; border-collapse: collapse; margin-bottom: 20px; font-size: 0.85rem;"
                        ),
                        style="margin-top: 20px;"
                    )
                else:
                    # Single verified product (centroid logic is same as distance to single point)
                    centroid = verified_df[numeric_cols].mean()
                    results = []
                    for _, row in unverified_df.iterrows():
                        diff = row[numeric_cols] - centroid
                        dist = (diff ** 2).sum() ** 0.5
                        results.append((row[id_col], dist))
                    
                    min_dist = min(r[1] for r in results) if results else -1
                    
                    scores_ui = []
                    for r_id, dist in results:
                        style = "color: red; font-weight: bold;" if dist == min_dist else ""
                        scores_ui.append(ui.tags.li(f"{r_id}: {dist:.2f}", style=style))
                    
                    diff_scores_ui = ui.tags.div(
                        ui.tags.h5("Similarity score"),
                        ui.tags.p("* lower = more similar", style="margin-top: 10px; color: red"),
                        ui.tags.ul(*scores_ui),
                        style="margin-top: 20px;"
                    )

        return ui.tags.div(
            ui.tags.div(
                ui.tags.div(
                    ui.tags.h5("Product details"),
                    close_btn,
                    style="display: flex; justify-content: space-between; margin-bottom: 10px;"
                ),
                ui.tags.div(meta_table),
                ui.tags.hr(),
                diff_scores_ui,
                ui.tags.hr(),
                ui.tags.div(
                    ui.tags.div(output_widget("compare_plot_bar"), style="width: 50%;"),
                    ui.tags.div(output_widget("compare_plot_radar"), style="width: 50%;"),
                    style="display: flex; flex-direction: row; width: 100%;"
                ),
                style="background: white; padding: 20px; border-radius: 5px; width: 90%; height: 90%; overflow: auto; position: relative;"
            ),
            style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); display: flex; justify-content: center; align-items: center; z-index: 10000;"
        )
        
    @reactive.effect
    @reactive.event(input.close_compare)
    def _on_close_compare():
        products_to_compare.set(pd.DataFrame())
        
        

    @reactive.effect
    @reactive.event(input.save_product)
    def _on_save_product():
        df = product_to_modify.get()
        if df is None or df.empty:
            return
        
        product_id = int(df.iloc[0]['id'])
        cols = list(df.columns)
        data_to_update = {}
        
        for col in cols:
            # Skip read-only columns
            if col in ["id", "link_to", "cluster_id", "cluster_count", "app_ver", "created", "updated", "token"]:
                continue
                
            input_id = f"edit_{_sanitize_id(col)}"
            try:
                val = input[input_id]()
                if val == "" or val == "nan":
                    val = None
                data_to_update[col] = val
            except Exception:
                pass
        
        print(f"Saving product {product_id} with data: {data_to_update}") # Debug print

        if not data_to_update:
            ui.notification_show("No changes to save.", type="warning")
            return

        # Call service
        result = update_product_info(product_id, data_to_update)
        
        if "error" in result:
            ui.notification_show(f"Error saving: {result['error']}", type="error")
        else:
            ui.notification_show("Product saved successfully!", type="message")
            get_updated_product(product_id)
            response = get_incomplete_products_with_alike_products()
            products = pd.json_normalize(response)
            incomplete_products_with_alike_products.set(products)
            

app = App(app_ui, server)
