import re
from shiny import App, reactive, render, ui
import pandas as pd
from pandas import DataFrame

# Keep alphanumerics and underscore; replace others with underscore
def _sanitize_id(name: str) -> str:
    return re.sub(r"[^0-9A-Za-z_]+", "_", name)

# Render the field in product_to_modify modal
def render_field(df: DataFrame, col_name: str):
    row = df.iloc[0]
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
                style="background:#f5f5f5; border:1px solid #ddd; display:flex; align-items:center; padding: 0.375rem 0.75rem; min-height: 36.5px; height: 100%; width: 300px; border-radius: 3px;"
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

# Render the table to show in product_to_modify
def render_table(df: pd.DataFrame):
    if df is None or df.empty:
        return ui.tags.div(ui.tags.p("No products.", style="color:#666;"))

    # Decide columns to show (use sensible defaults if present)
    base_cols = [c for c in ['id', 'name', 'energy', 'unit', 'synonyms', 'brands', 'categories', 'link_to'] if c in df.columns]

    header = ui.tags.tr(
        *[ui.tags.th(col, style="padding:.25rem .5rem; text-align:left; border:1px solid #ddd;") for col in base_cols]
    )
    body_rows = []
    for _, row in df.iterrows():
        pid = row.get("id")
        cells = [ui.tags.td(str(row.get(
            col, "")), style="padding:.25rem .5rem; vertical-align:center; border: 1px solid #ddd;") for col in base_cols]
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
        table,
        style="margin-bottom:1rem;"
    )
    
def render_alike_products_table(df, title, clicked_products, current_product_active, is_verified):
    """Renders a table of alike products (verified or unverified)."""
    if df.empty:
        return ui.tags.div(ui.tags.p(f"No {title.lower()} products found."), style="margin-top: 1rem;")

    show_cols = [c for c in ['id', 'name', 'energy', 'protein', 'categories'] if c in df.columns]
    
    # Header Checkbox
    product_ids = df['id'].tolist()
    all_products_checked = bool(product_ids) and all(pid in clicked_products for pid in product_ids)
    
    header_checkbox = ""
    if is_verified or current_product_active == 0:
        header_checkbox = ui.tags.input(
            type="checkbox",
            checked="checked" if all_products_checked else None,
            onclick=f"event.stopPropagation(); Shiny.setInputValue('toggle_all_products', {{'ids': {repr(product_ids)}, 'checked': event.target.checked}}, {{priority: 'event'}})",
            class_="alike_product_checkbox"
        )

    header = ui.tags.tr(
        ui.tags.th(header_checkbox, style="padding:.25rem .5rem; text-align:center; border:1px solid #ddd; width:2rem;"),
        *[ui.tags.th(c, style="padding:.25rem .5rem; text-align:center; border:1px solid #ddd;") for c in show_cols],
        ui.tags.th("action", style="padding:.25rem .5rem; text-align:center; border:1px solid #ddd; width: 10rem;"),
        style="height: 32px; background-color: #a5b4fb;"
    )

    body_rows = []
    for _, r in df.iterrows():
        pid = r.get("id")
        is_checked = pid in clicked_products

        # Row Checkbox
        row_checkbox = ""
        if is_verified or current_product_active == 0:
            row_checkbox = ui.tags.input(
                type="checkbox",
                id=f"alike_select_{'verified' if is_verified else 'unverified'}_{pid}",
                checked="checked" if is_checked else None,
                onclick=f"event.stopPropagation(); Shiny.setInputValue('toggle_checked_product', {{'pid': {repr(pid)}, 'checked': event.target.checked}}, {{priority: 'event'}})",
                class_="alike_product_checkbox"
            )
        
        checkbox_td = ui.tags.td(
            row_checkbox,
            style="padding:.25rem .5rem; vertical-align:center; horizontal-align:center; border:1px solid #ddd;"
        )

        # Action Buttons
        link_btn, compare_btn = ui.tags.div(), ui.tags.div()
        if current_product_active == 0 and not is_checked:
            if not is_verified or sum(1 for p in clicked_products if p in df[df['active']==1]['id'].tolist()) <= 1:
                 link_btn = ui.tags.button(
                    "Link",
                    type="button",
                    onclick=f"event.stopPropagation(); Shiny.setInputValue('link_product', {repr(pid)}, {{priority: 'event'}})",
                    # style="padding: 2px 6px; font-size: 0.75rem; cursor: pointer;",
                    class_="link_and_compare_button"
                )
            compare_btn = ui.tags.button(
                "Compare",
                type="button",
                onclick=f"event.stopPropagation(); Shiny.setInputValue('compare_products', {repr(pid)}, {{priority: 'event'}})",
                # style="padding: 2px 6px; font-size: 0.75rem; cursor: pointer;",
                class_="link_and_compare_button"
            )

        action_td = ui.tags.td(
            link_btn,
            compare_btn,
            style="padding:.25rem .5rem; vertical-align:center; border:1px solid #ddd;",
            class_="link_and_compare_button_container"
        )

        cells = [ui.tags.td(str(r.get(c, "")), style="padding:.25rem .5rem; vertical-align: center; border:1px solid #ddd;") for c in show_cols]
        onclick = f"Shiny.setInputValue('modify_product_row', {repr(pid)}, {{priority: 'event'}});"
        
        body_rows.append(
            ui.tags.tr(
                checkbox_td,
                *cells,
                action_td,
                onclick=onclick,
                class_="incompleted_table_rows",
                style="cursor:pointer; height: 32px;"
            )
        )

    table = ui.tags.table(
        ui.tags.thead(header),
        ui.tags.tbody(*body_rows),
        style="width:100%; border-collapse:collapse; font-size:.75rem; border:1px solid #ddd;"
    )

    return ui.tags.div(
        ui.tags.p(f"{title} products:", style="margin-top:2rem;"),
        table
    )