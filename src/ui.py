from nicegui import ui, events, context
import pandas as pd
import cv2
import base64
import numpy as np
from datetime import datetime, timedelta
import asyncio
from src.translations import TRANSLATIONS

def normalize_date(date_str):
    """Converts YYYY-MM-DD to DD-MM-YYYY if detected, otherwise returns original."""
    if not date_str:
        return ""
    date_str = str(date_str).strip()
    
    # Check if it's in YYYY-MM-DD format (e.g. 2026-03-06)
    if len(date_str) == 10 and date_str[4] == '-' and date_str[7] == '-':
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.strftime("%d-%m-%Y")
        except:
            pass
    return date_str

def create_ui(products, inventory, internal_inventory, customers, orders, recipes, qr_gen, alerts, scanner):
    # Add CSS for zebra striping in tables
    ui.add_head_html('''
        <style>
            .q-table tbody tr:nth-child(even) {
                background-color: #f2f2f2;
            }
        </style>
    ''')

    # --- State Management ---
    state = {
        'scanner_running': False,
        'main_view': 'sale',
        'orders_tab': 'orders_list',
        'current_tab': 'product_setup',
        'selected_recipe_ean': None,
        'sales_basket': [],
        'order_basket': [],
        'selected_order_customer_id': None,
        'selected_filter_customer_id': None,
        'order_search_query': '',
        'video_capture': None,
        'last_qr_path': None,
        'lang': 'en'
    }

    def t(key):
        return TRANSLATIONS[state['lang']].get(key, key)

    def get_product_options():
        return {ean: f"{details['name']} ({ean})" for ean, details in products.products.items()}

    def get_inventory_product_options():
        # Only show products that are actually in the regular inventory
        in_stock_eans = {str(item['ean']) for item in inventory.inventory if item['qty'] > 0}
        options = {}
        for ean in in_stock_eans:
            details = products.get_product_details(ean)
            name = details['name'] if details else "Unknown"
            options[ean] = f"{name} ({ean})"
        return options

    def get_customer_options():
        return {cid: f"{d['name']} ({d['company']})" if d['company'] else d['name'] for cid, d in customers.customers.items()}

    def get_internal_product_options():
        # Ingredients come from the internal inventory (ingredients list)
        options = {}
        # We can also get all products if we want to allow anything as an ingredient, 
        # but usually it's from the ingredients list. 
        # For simplicity, let's allow all products to be ingredients.
        for ean, details in products.products.items():
            options[ean] = f"{details['name']} ({ean})"
        return options

    # Global UI elements that need to be accessed across refreshes
    ui_elements = {}

    @ui.refreshable
    def render_header():
        def handle_lang_change(e):
            state['lang'] = e.value
            render_header.refresh()
            render_content.refresh()

        with ui.row().classes('items-center'):
            ui.label(t('title')).classes('text-2xl font-bold text-primary mr-8')
            ui.switch(t('camera'), on_change=toggle_scanner).bind_value(state, 'scanner_running')
            ui.select({'en': 'English', 'no': 'Norsk'}, label=t('language'), 
                      value=state['lang'], on_change=handle_lang_change).classes('w-32 ml-4')
        
        with ui.row().classes('items-center gap-4'):
            ui_elements['scanner_view'] = ui.image().classes('w-48 h-24 bg-black border rounded shadow-sm')
            ui_elements['scanner_log'] = ui.label(t('ready')).classes('text-xs font-mono w-48 overflow-hidden')

    def toggle_scanner(e):
        state['scanner_running'] = e.value
        if e.value:
            if state['video_capture'] is None:
                try:
                    state['video_capture'] = cv2.VideoCapture(0)
                    if not state['video_capture'].isOpened():
                        state['video_capture'] = cv2.VideoCapture(1)
                    
                    if not state['video_capture'].isOpened():
                        ui.notify("Could not open camera.", type='negative')
                        state['scanner_running'] = False
                        state['video_capture'] = None
                except Exception as ex:
                    ui.notify(f"Camera error: {ex}", type='negative')
                    state['scanner_running'] = False
                    state['video_capture'] = None
        else:
            if 'scanner_view' in ui_elements:
                ui_elements['scanner_view'].source = ''
            if 'scanner_log' in ui_elements:
                ui_elements['scanner_log'].text = t('scanner_stopped')
            if state['video_capture']:
                state['video_capture'].release()
                state['video_capture'] = None
        camera_timer.active = state['scanner_running']

    async def update_camera_frame():
        if not state['scanner_running'] or state['video_capture'] is None:
            return
        
        ret, frame = state['video_capture'].read()
        if not ret:
            return
        
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        ean, date, msg, debug_img = scanner.scan_image(rgb_frame)
        
        if ean:
            date = normalize_date(date)
            if state['main_view'] == 'sale':
                await handle_sale_scan_global(ean, date)
            else:
                current_tab_text = state['current_tab']
                if current_tab_text == 'inventory':
                    if 'reg_ean_input' in ui_elements: ui_elements['reg_ean_input'].value = ean
                    if 'reg_date_input' in ui_elements: ui_elements['reg_date_input'].value = date if date else ''
                elif current_tab_text == 'internal_inventory':
                    if 'internal_ean_input' in ui_elements: ui_elements['internal_ean_input'].value = ean
                    if 'internal_date_input' in ui_elements: ui_elements['internal_date_input'].value = date if date else ''
            ui.notify(f"Scanned: {ean}")

        if debug_img is not None and 'scanner_view' in ui_elements:
            _, buffer = cv2.imencode('.jpg', cv2.cvtColor(debug_img, cv2.COLOR_RGB2BGR))
            b64_img = base64.b64encode(buffer).decode()
            ui_elements['scanner_view'].source = f'data:image/jpeg;base64,{b64_img}'
            ui_elements['scanner_log'].text = msg

    camera_timer = ui.timer(0.1, update_camera_frame, active=state['scanner_running'])

    # --- Shared Logic Functions ---
    def refresh_all_tables():
        product_options = get_product_options()
        inventory_options = get_inventory_product_options()
        customer_options = get_customer_options()
        
        for key in ['reg_ean_input', 'internal_ean_input', 'qr_ean_input', 'order_product_input']:
            if key in ui_elements:
                ui_elements[key].options = product_options
                ui_elements[key].update()
        
        if 'sales_ean_input' in ui_elements:
            ui_elements['sales_ean_input'].options = inventory_options
            ui_elements['sales_ean_input'].update()

        if 'customer_selection' in ui_elements:
            ui_elements['customer_selection'].options = customer_options
            ui_elements['customer_selection'].update()

        if 'product_table' in ui_elements:
            ui_elements['product_table'].rows[:] = products.get_products_df().to_dict('records')
            ui_elements['product_table'].update()
        if 'inventory_table' in ui_elements:
            ui_elements['inventory_table'].rows[:] = inventory.get_inventory_df().to_dict('records')
            ui_elements['inventory_table'].update()
        if 'internal_table' in ui_elements:
            df_internal = internal_inventory.get_inventory_df()
            # Format Qty to 2 decimal places string for display
            df_internal['Qty'] = df_internal['Qty'].apply(lambda x: f"{float(x):.2f}")
            ui_elements['internal_table'].rows[:] = df_internal.to_dict('records')
            ui_elements['internal_table'].update()
        
        if 'customer_table' in ui_elements:
            ui_elements['customer_table'].rows[:] = customers.get_customers_df().to_dict('records')
            ui_elements['customer_table'].update()

        if 'orders_table' in ui_elements:
            df = orders.get_orders_df()
            # Active orders only (Received or Making)
            df_active = df[df['Status'] != 'Finished']
            
            # Apply Customer Filter
            if state['selected_filter_customer_id'] and state['selected_filter_customer_id'] != 'all':
                df_active = df_active[df_active['Customer ID'] == state['selected_filter_customer_id']]
            
            # Apply Search Filter (ID, Name, or Customer ID)
            query = state['order_search_query'].lower().strip()
            if query:
                df_active = df_active[
                    df_active['Order ID'].str.lower().str.contains(query) |
                    df_active['Customer Name'].str.lower().str.contains(query) |
                    df_active['Customer ID'].str.lower().str.contains(query)
                ]
            
            ui_elements['orders_table'].rows[:] = df_active.to_dict('records')
            ui_elements['orders_table'].update()

        if 'order_history_table' in ui_elements:
            df = orders.get_orders_df()
            # History only (Finished)
            df_history = df[df['Status'] == 'Finished']
            
            # Apply Customer Filter
            if state['selected_filter_customer_id'] and state['selected_filter_customer_id'] != 'all':
                df_history = df_history[df_history['Customer ID'] == state['selected_filter_customer_id']]
            
            # Apply Search Filter
            query = state['order_search_query'].lower().strip()
            if query:
                df_history = df_history[
                    df_history['Order ID'].str.lower().str.contains(query) |
                    df_history['Customer Name'].str.lower().str.contains(query) |
                    df_history['Customer ID'].str.lower().str.contains(query)
                ]
                
            ui_elements['order_history_table'].rows[:] = df_history.to_dict('records')
            ui_elements['order_history_table'].update()

        # --- Recipes Refresh ---
        if 'recipe_product_selection' in ui_elements:
            ui_elements['recipe_product_selection'].options = product_options
            ui_elements['recipe_product_selection'].update()
        
        if 'recipe_ingredient_selection' in ui_elements:
            ui_elements['recipe_ingredient_selection'].options = get_internal_product_options()
            ui_elements['recipe_ingredient_selection'].update()

        if 'recipe_table' in ui_elements:
            if state['selected_recipe_ean']:
                recipe_items = recipes.get_recipe(state['selected_recipe_ean'])
                display_items = []
                for item in recipe_items:
                    details = products.get_product_details(item['ingredient_ean'])
                    name = details['name'] if details else "Unknown"
                    display_items.append({
                        'Ingredient EAN': item['ingredient_ean'],
                        'Name': name,
                        'Qty': item['qty']
                    })
                ui_elements['recipe_table'].rows[:] = display_items
                
                if 'recipe_header_label' in ui_elements:
                    details = products.get_product_details(state['selected_recipe_ean'])
                    pname = details['name'] if details else '...'
                    ui_elements['recipe_header_label'].text = f"{t('recipe_for')}: {pname}"
            else:
                ui_elements['recipe_table'].rows[:] = []
                if 'recipe_header_label' in ui_elements:
                    ui_elements['recipe_header_label'].text = f"{t('recipe_for')}: ..."
            ui_elements['recipe_table'].update()
        
        if 'filter_customer_selection' in ui_elements:
            opts = {'all': t('all')}
            opts.update(customer_options)
            ui_elements['filter_customer_selection'].options = opts
            ui_elements['filter_customer_selection'].update()

        if 'basket_table' in ui_elements:
            basket_rows = []
            grand_total = 0.0
            for item in state['sales_basket']:
                row_total = item['Price'] * item['Qty']
                grand_total += row_total
                basket_rows.append({**item, 'Total': f"{row_total:.2f}"})
            ui_elements['basket_table'].rows[:] = basket_rows
            ui_elements['basket_table'].update()
            if 'grand_total_label' in ui_elements:
                ui_elements['grand_total_label'].text = f"{t('grand_total')}: {grand_total:.2f}"

        if 'order_basket_table' in ui_elements:
            order_rows = []
            order_total = 0.0
            for item in state['order_basket']:
                row_total = item['Price'] * item['Qty']
                order_total += row_total
                order_rows.append({**item, 'Total': f"{row_total:.2f}"})
            ui_elements['order_basket_table'].rows[:] = order_rows
            ui_elements['order_basket_table'].update()
            if 'order_total_label' in ui_elements:
                ui_elements['order_total_label'].text = f"{t('grand_total')}: {order_total:.2f}"

    async def handle_sale_scan_global(ean, date):
        date = normalize_date(date)
        details = products.get_product_details(ean)
        name = details['name'] if details else "Unknown"
        price = details['price_out'] if details else 0.0
        if date:
            add_to_basket_global(ean, name, date, price)
        else:
            batches = [b for b in inventory.get_raw_inventory() if str(b['ean']) == str(ean)]
            if not batches:
                ui.notify(f"{t('no_inventory_found')}: {ean}", type='warning')
            elif len(batches) == 1:
                add_to_basket_global(batches[0]['ean'], batches[0]['name'], batches[0]['exp_date'], price)
            else:
                show_batch_selection_global(batches, price)

    def add_to_basket_global(ean, name, date, price):
        date = normalize_date(date)
        for item in state['sales_basket']:
            if item['EAN'] == ean and item['Exp Date'] == date:
                item['Qty'] += 1
                refresh_all_tables()
                return
        state['sales_basket'].append({'EAN': ean, 'Name': name, 'Exp Date': date, 'Qty': 1, 'Price': price})
        refresh_all_tables()

    def show_batch_selection_global(batches, price):
        with ui.dialog() as dialog, ui.card():
            ui.label(t('select_batch')).classes('text-lg font-bold')
            for b in batches:
                with ui.row().classes('w-full items-center justify-between border-b py-2'):
                    ui.label(f"Exp: {b['exp_date']} (Stock: {b['qty']})")
                    ui.button(t('select'), on_click=lambda b=b: [add_to_basket_global(b['ean'], b['name'], b['exp_date'], price), dialog.close()])
            ui.button(t('cancel'), on_click=dialog.close).props('flat')
        dialog.open()

    async def complete_sale():
        if not state['sales_basket']:
            ui.notify(t('basket_empty'), type='warning')
            return
        success_count = 0
        for item in state['sales_basket']:
            msg, _ = inventory.update_stock(item['EAN'], item['Name'], item['Exp Date'], item['Qty'], "Remove")
            if "Remove:" in msg: success_count += 1
        if success_count > 0:
            ui.notify(t('sale_completed'))
            state['sales_basket'] = []
            refresh_all_tables()

    def add_to_order_basket(ean, qty):
        details = products.get_product_details(ean)
        if not details:
            ui.notify(t('ean_unknown'), type='negative')
            return
        
        name = details['name']
        price = details['price_out']
        
        for item in state['order_basket']:
            if item['EAN'] == ean:
                item['Qty'] += qty
                refresh_all_tables()
                return
        
        state['order_basket'].append({
            'EAN': ean, 
            'Name': name, 
            'Exp Date': 'N/A', # Orders from products.csv don't have exp date yet
            'Qty': qty, 
            'Price': price
        })
        refresh_all_tables()

    async def complete_order(due_date=""):
        if not state['order_basket']:
            ui.notify(t('basket_empty'), type='warning')
            return
        
        if not state['selected_order_customer_id']:
            ui.notify(t('select_customer'), type='warning')
            return

        customer = customers.get_customer_details(state['selected_order_customer_id'])
        if not customer:
            ui.notify("Customer details not found.", type='negative')
            return

        # Create Order entry
        order_id, msg = orders.create_order(
            state['selected_order_customer_id'], 
            customer['name'] if customer['name'] else customer['company'], 
            state['order_basket'],
            due_date=due_date
        )
        if order_id:
            ui.notify(t('sale_completed'))
            state['order_basket'] = []
            state['selected_order_customer_id'] = None
            if 'customer_selection' in ui_elements:
                ui_elements['customer_selection'].value = None
            # The input field is local to the tab panel, so we refresh the content to clear it
            render_content.refresh()
            refresh_all_tables()
        else:
            ui.notify(msg, type='negative')

    def clear_basket():
        state['sales_basket'] = []
        refresh_all_tables()

    @ui.refreshable
    def render_content():
        # --- UI Logic within refreshable ---
        async def add_product():
            msg, df = products.add_product(ean_input.value, name_input.value, shelf_life_input.value, url_input.value, price_in_input.value, price_out_input.value)
            ui.notify(msg)
            refresh_all_tables()
            ean_input.value = name_input.value = url_input.value = ''
            price_in_input.value = price_out_input.value = 0.0

        async def delete_product(ean):
            msg, df = products.delete_product(ean)
            ui.notify(msg)
            refresh_all_tables()

        async def add_customer():
            msg, df = customers.add_customer(
                cname_input.value, comp_input.value, 
                org_nr_input.value, vat_nr_input.value,
                phone_input.value, email_input.value, 
                addr_input.value, web_input.value, notes_input.value
            )
            ui.notify(msg)
            refresh_all_tables()
            # Clear all inputs
            for inp in [cname_input, comp_input, org_nr_input, vat_nr_input, phone_input, email_input, addr_input, web_input, notes_input]:
                inp.value = ''

        async def delete_customer(cid):
            msg, df = customers.delete_customer(cid)
            ui.notify(msg)
            refresh_all_tables()

        def open_edit_customer_dialog(cid):
            details = customers.get_customer_details(cid)
            if not details: return
            with ui.dialog() as dialog, ui.card().classes('w-[500px] p-4'):
                ui.label(t('edit_customer')).classes('text-xl font-bold mb-2')
                with ui.column().classes('w-full gap-2'):
                    edit_name = ui.input(t('name'), value=details['name']).classes('w-full')
                    edit_comp = ui.input(t('company_name'), value=details['company']).classes('w-full')
                    with ui.row().classes('w-full gap-2'):
                        edit_org = ui.input(t('org_nr'), value=details.get('org_nr', '')).classes('flex-grow')
                        edit_vat = ui.input(t('vat_nr'), value=details.get('vat_nr', '')).classes('flex-grow')
                    with ui.row().classes('w-full gap-2'):
                        edit_phone = ui.input(t('phone'), value=details.get('phone', '')).classes('flex-grow')
                        edit_email = ui.input(t('email'), value=details.get('email', '')).classes('flex-grow')
                    edit_addr = ui.input(t('address'), value=details.get('address', '')).classes('w-full')
                    edit_web = ui.input(t('website'), value=details.get('website', '')).classes('w-full')
                    edit_notes = ui.textarea(t('notes'), value=details.get('notes', '')).classes('w-full')
                
                async def save_edit():
                    customers.update_customer(
                        cid, edit_name.value, edit_comp.value, 
                        edit_org.value, edit_vat.value,
                        edit_phone.value, edit_email.value, 
                        edit_addr.value, edit_web.value, edit_notes.value
                    )
                    refresh_all_tables()
                    dialog.close()
                ui.button(t('update_customer'), on_click=save_edit).classes('w-full mt-4')
            dialog.open()

        def open_edit_dialog(ean):
            details = products.get_product_details(ean)
            if not details: return
            with ui.dialog() as dialog, ui.card().classes('w-96 p-4'):
                ui.label(t('edit_product')).classes('text-xl font-bold mb-2')
                edit_name = ui.input(t('product_name'), value=details['name']).classes('w-full')
                edit_shelf = ui.number(t('shelf_life'), value=details['shelf_life']).classes('w-full')
                edit_url = ui.input(t('product_url'), value=details.get('url', '')).classes('w-full')
                with ui.row().classes('w-full gap-2'):
                    edit_price_in = ui.number(t('price_in'), value=details.get('price_in', 0.0), format='%.2f').classes('flex-grow')
                    edit_price_out = ui.number(t('price_out'), value=details.get('price_out', 0.0), format='%.2f').classes('flex-grow')
                async def save_edit():
                    products.update_product(ean, edit_name.value, edit_shelf.value, edit_url.value, edit_price_in.value, edit_price_out.value)
                    refresh_all_tables()
                    dialog.close()
                ui.button(t('update_product'), on_click=save_edit)
            dialog.open()

        def generate_qr():
            ean = qr_ean_input.value if qr_ean_input.value else ""
            img, info, filepath = qr_gen.generate_qr(ean, products.get_product_details(ean), manual_exp_date=qr_exp_input.value)
            if img:
                state['last_qr_path'] = filepath
                import io
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                qr_display.source = f'data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode()}'
                qr_info_label.text = info
                qr_download_group.set_visibility(True)
            else:
                ui.notify(t('ean_unknown'), type='negative')

        async def update_stock(action, is_internal=False):
            manager = internal_inventory if is_internal else inventory
            ean_field = internal_ean_input if is_internal else reg_ean_input
            date_field = internal_date_input if is_internal else reg_date_input
            qty_field = internal_qty_input if is_internal else reg_qty_input
            
            ean = ean_field.value if ean_field.value else ""
            qty = float(qty_field.value) if qty_field.value else 0
            details = products.get_product_details(ean)
            name = details['name'] if details else "Unknown"
            shelf_life = details['shelf_life'] if details else None
            
            # Logic for deducting ingredients from recipes when adding to regular inventory
            if not is_internal and action == 'Add' and ean:
                recipe = recipes.get_recipe(ean)
                if recipe:
                    # Deduct ingredients from internal inventory (FIFO across all batches)
                    insufficient_items = []
                    for ing in recipe:
                        ing_details = products.get_product_details(ing['ingredient_ean'])
                        ing_name = ing_details['name'] if ing_details else "Unknown Ingredient"
                        # Recipe qty is in grams, internal inventory is in kg.
                        total_needed_kg = (float(ing['qty']) * qty) / 1000.0
                        
                        # Use deduct_total on internal_inventory (handles FIFO and negative)
                        is_insufficient, available = internal_inventory.deduct_total(ing['ingredient_ean'], ing_name, total_needed_kg)
                        if is_insufficient:
                            insufficient_items.append(f"{ing_name} ({t('qty')}: {available:.2f}kg)")
                    
                    if insufficient_items:
                        ui.notify(f"Warning: Insufficient ingredients! Missing: {', '.join(insufficient_items)}", type='warning', duration=10)
                    else:
                        ui.notify(t('production_deduction'))

            msg, _ = manager.update_stock(ean, name, normalize_date(date_field.value), qty, action, shelf_life=shelf_life)
            ui.notify(msg)
            refresh_all_tables()

        # --- Main View Tabs ---
        with ui.tabs().classes('w-full') as main_tabs:
            ui.tab('sale', label=t('tab_sale_view'))
            ui.tab('orders', label=t('tab_orders'))
            ui.tab('customers', label=t('tab_customers'))
            ui.tab('inventory_mgmt', label=t('tab_inventory_view'))

        with ui.tab_panels(main_tabs, value='sale').classes('w-full').bind_value(state, 'main_view'):
            # --- Sale View ---
            with ui.tab_panel('sale'):
                with ui.row().classes('w-full no-wrap'):
                    with ui.card().classes('w-1/3 p-4'):
                        sales_ean_input = ui.select(get_inventory_product_options(), label=t('ean'), with_input=True).classes('w-full mb-2')
                        ui_elements['sales_ean_input'] = sales_ean_input
                        
                        async def add_manual_sale():
                            if sales_ean_input.value:
                                await handle_sale_scan_global(sales_ean_input.value, None)
                                sales_ean_input.value = None
                            else:
                                ui.notify(t('ean_required'), type='warning')

                        ui.button(t('add_to_basket'), on_click=add_manual_sale).classes('w-full mb-4')
                        ui.button(t('complete_sale'), on_click=complete_sale).classes('w-full mb-2')
                        ui.button(t('clear_basket'), on_click=clear_basket).classes('w-full')
                    with ui.card().classes('w-2/3 p-4'):
                        cols = [{'name': k, 'label': t(k.lower().replace(' ', '_')), 'field': k} for k in ['Name', 'EAN', 'Exp Date', 'Price', 'Qty', 'Total']]
                        ui_elements['basket_table'] = ui.table(columns=cols, rows=[]).classes('w-full')
                        ui_elements['grand_total_label'] = ui.label(f"{t('grand_total')}: 0.00")
            
            # --- Orders View ---
            with ui.tab_panel('orders'):
                with ui.tabs().classes('w-full') as orders_tabs:
                    ui.tab('orders_list', label=t('tab_orders_list'))
                    ui.tab('order_history', label=t('tab_order_history'))
                    ui.tab('customer_ordering', label=t('tab_customer_ordering'))

                with ui.tab_panels(orders_tabs, value='orders_list').classes('w-full').bind_value(state, 'orders_tab'):
                    with ui.tab_panel('orders_list'):
                        with ui.row().classes('w-full items-center gap-4 mb-4'):
                            ui.label(f"{t('customer')}:").classes('font-bold')
                            filter_customer_selection = ui.select({'all': t('all')}, value='all', on_change=refresh_all_tables).classes('w-64')
                            filter_customer_selection.bind_value(state, 'selected_filter_customer_id')
                            ui_elements['filter_customer_selection'] = filter_customer_selection
                            
                            ui.input(placeholder=t('search_placeholder'), on_change=refresh_all_tables).classes('flex-grow').bind_value(state, 'order_search_query').props('clearable icon=search')

                        def delete_order(order_id):
                            msg = orders.delete_order(order_id)
                            ui.notify(msg)
                            refresh_all_tables()

                        def open_edit_order_dialog(order_id):
                            current_items = list(orders.get_order_items(order_id))
                            # Find the order object to get current due date
                            current_order = next((o for o in orders.orders if o['Order ID'] == order_id), None)
                            current_due_date = current_order.get('Due Date', '') if current_order else ''
                            
                            with ui.dialog() as dialog, ui.card().classes('w-[800px] p-4'):
                                ui.label(f"{t('edit_order')}: {order_id}").classes('text-xl font-bold mb-4')
                                
                                with ui.input(t('Due Date'), value=current_due_date) as edit_due_date_input:
                                    edit_due_date_input.classes('w-full mb-4')
                                    with ui.menu() as menu:
                                        ui.date().bind_value(edit_due_date_input)
                                    with edit_due_date_input.add_slot('append'):
                                        ui.icon('event').on('click', menu.open).classes('cursor-pointer')

                                @ui.refreshable
                                def render_edit_items():
                                    cols = [
                                        {'name': 'Name', 'label': t('name'), 'field': 'Name'},
                                        {'name': 'EAN', 'label': t('ean'), 'field': 'EAN'},
                                        {'name': 'Price', 'label': t('price'), 'field': 'Price'},
                                        {'name': 'Qty', 'label': t('qty'), 'field': 'Qty'},
                                        {'name': 'ACTIONS', 'label': '', 'field': 'ACTIONS'},
                                    ]
                                    table = ui.table(columns=cols, rows=current_items).classes('w-full mb-4')
                                    
                                    # Make Qty editable with QPopupEdit
                                    table.add_slot('body-cell-Qty', '''
                                        <q-td :props="props">
                                            {{ props.value }}
                                            <q-popup-edit v-model.number="props.row.Qty" v-slot="scope" buttons 
                                                @save="(val) => $parent.$emit('update_qty', {ean: props.row.EAN, qty: val})">
                                                <q-input type="number" v-model.number="scope.value" dense autofocus />
                                            </q-popup-edit>
                                        </q-td>
                                    ''')

                                    table.add_slot('body-cell-ACTIONS', '<q-td :props="props"><q-btn size="sm" color="negative" icon="delete" @click="$parent.$emit(\'remove_item\', props.row.EAN)" /></q-td>')
                                    
                                    def update_qty(data):
                                        ean = data['ean']
                                        new_qty = float(data['qty'])
                                        for item in current_items:
                                            if item['EAN'] == ean:
                                                item['Qty'] = new_qty
                                                break
                                        render_edit_items.refresh()

                                    def remove_item(ean):
                                        nonlocal current_items
                                        current_items = [it for it in current_items if it['EAN'] != ean]
                                        render_edit_items.refresh()
                                    
                                    table.on('update_qty', lambda msg: update_qty(msg.args))
                                    table.on('remove_item', lambda msg: remove_item(msg.args))

                                with ui.row().classes('w-full gap-2 items-center mb-4'):
                                    add_ean_input = ui.select(get_product_options(), label=t('product'), with_input=True).classes('flex-grow')
                                    add_qty_input = ui.number(t('qty'), value=1).classes('w-24')
                                    
                                    def add_to_edit_list():
                                        ean = add_ean_input.value
                                        if not ean: return
                                        details = products.get_product_details(ean)
                                        if not details: return
                                        
                                        # Check if already in list
                                        for it in current_items:
                                            if it['EAN'] == ean:
                                                it['Qty'] += add_qty_input.value
                                                render_edit_items.refresh()
                                                return
                                        
                                        current_items.append({
                                            'EAN': ean,
                                            'Name': details['name'],
                                            'Price': details['price_out'],
                                            'Qty': float(add_qty_input.value),
                                            'Exp Date': 'N/A'
                                        })
                                        render_edit_items.refresh()

                                    ui.button(icon='add', on_click=add_to_edit_list).classes('bg-primary text-white')

                                render_edit_items()

                                async def save_changes():
                                    success, msg = orders.update_order(order_id, current_items, due_date=edit_due_date_input.value)
                                    if success:
                                        ui.notify(msg)
                                        refresh_all_tables()
                                        dialog.close()
                                    else:
                                        ui.notify(msg, type='negative')

                                with ui.row().classes('w-full justify-end gap-2'):
                                    ui.button(t('cancel'), on_click=dialog.close).props('flat')
                                    ui.button(t('update_product'), on_click=save_changes)
                            
                            dialog.open()

                        def show_order_details(order_id):
                            items = orders.get_order_items(order_id)
                            with ui.dialog() as dialog, ui.card().classes('w-[600px] p-4'):
                                ui.label(f"{t('order_details')}: {order_id}").classes('text-xl font-bold mb-4')
                                cols = [
                                    {'name': 'Name', 'label': t('name'), 'field': 'Name'},
                                    {'name': 'EAN', 'label': t('ean'), 'field': 'EAN'},
                                    {'name': 'Exp Date', 'label': t('exp_date'), 'field': 'Exp Date'},
                                    {'name': 'Qty', 'label': t('qty'), 'field': 'Qty'},
                                    {'name': 'Price', 'label': t('price'), 'field': 'Price'},
                                ]
                                ui.table(columns=cols, rows=items).classes('w-full mb-4')
                                ui.button(t('cancel'), on_click=dialog.close).props('flat')
                            dialog.open()

                        cols = [
                            {'name': 'Order ID', 'label': t('order_id'), 'field': 'Order ID', 'sortable': True},
                            {'name': 'Customer Name', 'label': t('customer'), 'field': 'Customer Name', 'sortable': True},
                            {'name': 'Date', 'label': t('date'), 'field': 'Date', 'sortable': True},
                            {'name': 'Due Date', 'label': t('Due Date'), 'field': 'Due Date', 'sortable': True},
                            {'name': 'Total', 'label': t('total'), 'field': 'Total', 'sortable': True},
                            {'name': 'Items', 'label': t('items'), 'field': 'Items', 'sortable': True, 'align': 'left'},
                            {'name': 'Status', 'label': t('status'), 'field': 'Status', 'sortable': True},
                            {'name': 'ACTIONS', 'label': '', 'field': 'ACTIONS'}
                        ]

                        ui_elements['orders_table'] = ui.table(columns=cols, rows=[], row_key='Order ID').classes('w-full')
                        
                        # Add custom slot for Status with colored chips
                        ui_elements['orders_table'].add_slot('body-cell-Status', '''
                            <q-td :props="props">
                                <q-chip :color="props.value === 'Received' ? 'blue' : (props.value === 'Making' ? 'orange' : 'green')" 
                                        text-color="white" clickable @click="$parent.$emit('toggle_status', props.row)">
                                    {{ props.value }}
                                </q-chip>
                            </q-td>
                        ''')

                        def toggle_status(row):
                            order_id = row['Order ID']
                            current_status = row['Status']
                            next_status = "Making" if current_status == "Received" else ("Finished" if current_status == "Making" else "Received")
                            orders.update_order_status(order_id, next_status)
                            refresh_all_tables()

                        ui_elements['orders_table'].on('toggle_status', lambda msg: toggle_status(msg.args))
                        
                        ui_elements['orders_table'].add_slot('body-cell-ACTIONS', '<q-td :props="props"><q-btn size="sm" color="primary" icon="visibility" @click="$parent.$emit(\'view\', props.row[\'Order ID\'])" /><q-btn size="sm" color="orange" icon="edit" @click="$parent.$emit(\'edit\', props.row[\'Order ID\'])" /><q-btn size="sm" color="negative" icon="delete" @click="$parent.$emit(\'delete\', props.row[\'Order ID\'])" /></q-td>')
                        ui_elements['orders_table'].on('view', lambda msg: show_order_details(msg.args))
                        ui_elements['orders_table'].on('edit', lambda msg: open_edit_order_dialog(msg.args))
                        ui_elements['orders_table'].on('delete', lambda msg: delete_order(msg.args))
                    
                    with ui.tab_panel('order_history'):
                        with ui.row().classes('w-full items-center gap-4 mb-4'):
                            ui.label(f"{t('customer')}:").classes('font-bold')
                            # We don't need to store this separately as they share the same state
                            ui.select({'all': t('all')}, value='all', on_change=refresh_all_tables).classes('w-64').bind_value(state, 'selected_filter_customer_id')
                            
                            ui.input(placeholder=t('search_placeholder'), on_change=refresh_all_tables).classes('flex-grow').bind_value(state, 'order_search_query').props('clearable icon=search')

                        cols_history = [
                            {'name': 'Order ID', 'label': t('order_id'), 'field': 'Order ID', 'sortable': True},
                            {'name': 'Customer Name', 'label': t('customer'), 'field': 'Customer Name', 'sortable': True},
                            {'name': 'Date', 'label': t('date'), 'field': 'Date', 'sortable': True},
                            {'name': 'Due Date', 'label': t('Due Date'), 'field': 'Due Date', 'sortable': True},
                            {'name': 'Total', 'label': t('total'), 'field': 'Total', 'sortable': True},
                            {'name': 'Items', 'label': t('items'), 'field': 'Items', 'sortable': True, 'align': 'left'},
                            {'name': 'Status', 'label': t('status'), 'field': 'Status', 'sortable': True},
                            {'name': 'ACTIONS', 'label': '', 'field': 'ACTIONS'}
                        ]
                        ui_elements['order_history_table'] = ui.table(columns=cols_history, rows=[], row_key='Order ID').classes('w-full')
                        ui_elements['order_history_table'].add_slot('body-cell-Status', '''
                            <q-td :props="props">
                                <q-chip color="green" text-color="white" clickable @click="$parent.$emit('toggle_status', props.row)">
                                    {{ props.value }}
                                </q-chip>
                            </q-td>
                        ''')
                        ui_elements['order_history_table'].on('toggle_status', lambda msg: toggle_status(msg.args))
                        ui_elements['order_history_table'].add_slot('body-cell-ACTIONS', '<q-td :props="props"><q-btn size="sm" color="primary" icon="visibility" @click="$parent.$emit(\'view\', props.row[\'Order ID\'])" /><q-btn size="sm" color="orange" icon="edit" @click="$parent.$emit(\'edit\', props.row[\'Order ID\'])" /><q-btn size="sm" color="negative" icon="delete" @click="$parent.$emit(\'delete\', props.row[\'Order ID\'])" /></q-td>')
                        ui_elements['order_history_table'].on('view', lambda msg: show_order_details(msg.args))
                        ui_elements['order_history_table'].on('edit', lambda msg: open_edit_order_dialog(msg.args))
                        ui_elements['order_history_table'].on('delete', lambda msg: delete_order(msg.args))

                    with ui.tab_panel('order_search'):
                        with ui.row().classes('w-full items-center gap-4 mb-4'):
                            ui.input(t('tab_order_search'), placeholder=t('search_placeholder'), on_change=refresh_all_tables).classes('w-full').bind_value(state, 'order_search_query').props('clearable icon=search')

                        cols_search = [
                            {'name': 'Order ID', 'label': t('order_id'), 'field': 'Order ID', 'sortable': True},
                            {'name': 'Customer Name', 'label': t('customer'), 'field': 'Customer Name', 'sortable': True},
                            {'name': 'Date', 'label': t('date'), 'field': 'Date', 'sortable': True},
                            {'name': 'Due Date', 'label': t('Due Date'), 'field': 'Due Date', 'sortable': True},
                            {'name': 'Total', 'label': t('total'), 'field': 'Total', 'sortable': True},
                            {'name': 'Items', 'label': t('items'), 'field': 'Items', 'sortable': True, 'align': 'left'},
                            {'name': 'Status', 'label': t('status'), 'field': 'Status', 'sortable': True},
                            {'name': 'ACTIONS', 'label': '', 'field': 'ACTIONS'}
                        ]
                        ui_elements['orders_search_table'] = ui.table(columns=cols_search, rows=[], row_key='Order ID').classes('w-full')
                        ui_elements['orders_search_table'].add_slot('body-cell-Status', '''
                            <q-td :props="props">
                                <q-chip :color="props.value === 'Received' ? 'blue' : (props.value === 'Making' ? 'orange' : 'green')" 
                                        text-color="white" clickable @click="$parent.$emit('toggle_status', props.row)">
                                    {{ props.value }}
                                </q-chip>
                            </q-td>
                        ''')
                        ui_elements['orders_search_table'].on('toggle_status', lambda msg: toggle_status(msg.args))
                        ui_elements['orders_search_table'].add_slot('body-cell-ACTIONS', '<q-td :props="props"><q-btn size="sm" color="primary" icon="visibility" @click="$parent.$emit(\'view\', props.row[\'Order ID\'])" /><q-btn size="sm" color="orange" icon="edit" @click="$parent.$emit(\'edit\', props.row[\'Order ID\'])" /><q-btn size="sm" color="negative" icon="delete" @click="$parent.$emit(\'delete\', props.row[\'Order ID\'])" /></q-td>')
                        ui_elements['orders_search_table'].on('view', lambda msg: show_order_details(msg.args))
                        ui_elements['orders_search_table'].on('edit', lambda msg: open_edit_order_dialog(msg.args))
                        ui_elements['orders_search_table'].on('delete', lambda msg: delete_order(msg.args))

                    with ui.tab_panel('customer_ordering'):
                        with ui.row().classes('w-full no-wrap'):
                            with ui.card().classes('w-1/3 p-4'):
                                ui.label(t('tab_customer_ordering')).classes('text-lg font-bold mb-4')
                                customer_selection = ui.select(get_customer_options(), label=t('select_customer'), with_input=True).classes('w-full mb-4')
                                customer_selection.bind_value(state, 'selected_order_customer_id')
                                ui_elements['customer_selection'] = customer_selection

                                with ui.input(t('Due Date')) as order_due_date_input:
                                    order_due_date_input.classes('w-full mb-4')
                                    with ui.menu() as menu:
                                        ui.date().bind_value(order_due_date_input)
                                    with order_due_date_input.add_slot('append'):
                                        ui.icon('event').on('click', menu.open).classes('cursor-pointer')

                                order_product_input = ui.select(get_product_options(), label=t('product'), with_input=True).classes('w-full mb-2')
                                ui_elements['order_product_input'] = order_product_input
                                order_qty_input = ui.number(t('qty'), value=1, step=0.01, format='%.2f').classes('w-full mb-4')

                                ui.button(t('add_to_basket'), on_click=lambda: add_to_order_basket(order_product_input.value, order_qty_input.value)).classes('w-full mb-4')
                                ui.button(t('save_as_order'), on_click=lambda: complete_order(order_due_date_input.value)).classes('w-full')
                            
                            with ui.card().classes('w-2/3 p-4'):
                                basket_cols = [
                                    {'name': 'Name', 'label': t('name'), 'field': 'Name'},
                                    {'name': 'EAN', 'label': t('ean'), 'field': 'EAN'},
                                    {'name': 'Price', 'label': t('price'), 'field': 'Price'},
                                    {'name': 'Qty', 'label': t('qty'), 'field': 'Qty', 'format': '(val) => val.toFixed(2)'},
                                    {'name': 'Total', 'label': t('total'), 'field': 'Total', 'format': '(val) => val.toFixed(2)'}
                                ]
                                ui_elements['order_basket_table'] = ui.table(columns=basket_cols, rows=[]).classes('w-full')
                                ui_elements['order_total_label'] = ui.label(f"{t('grand_total')}: 0.00").classes('text-lg font-bold mt-4')

            # --- Customers View ---
            with ui.tab_panel('customers'):
                with ui.row().classes('w-full no-wrap gap-4'):
                    # Left: Entry Form
                    with ui.card().classes('w-1/3 p-4'):
                        ui.label(t('add_customers')).classes('text-lg font-bold mb-2')
                        with ui.column().classes('w-full gap-2'):
                            cname_input = ui.input(t('name')).classes('w-full')
                            comp_input = ui.input(t('company_name')).classes('w-full')
                            
                            with ui.row().classes('w-full gap-2'):
                                org_nr_input = ui.input(t('org_nr')).classes('flex-grow')
                                vat_nr_input = ui.input(t('vat_nr')).classes('flex-grow')
                            
                            with ui.row().classes('w-full gap-2'):
                                phone_input = ui.input(t('phone')).classes('flex-grow')
                                email_input = ui.input(t('email')).classes('flex-grow')
                            
                            addr_input = ui.input(t('address')).classes('w-full')
                            web_input = ui.input(t('website')).classes('w-full')
                            notes_input = ui.textarea(t('notes')).classes('w-full')
                            
                            ui.button(t('save_customer'), on_click=add_customer).classes('w-full mt-2')

                    # Right: Customer List
                    with ui.card().classes('w-2/3 p-4'):
                        cols = [
                            {'name': 'Customer ID', 'label': t('customer_id'), 'field': 'Customer ID', 'sortable': True},
                            {'name': 'Name', 'label': t('name'), 'field': 'Name', 'sortable': True},
                            {'name': 'Company Name', 'label': t('company_name'), 'field': 'Company Name', 'sortable': True},
                            {'name': 'Org Number', 'label': t('org_nr'), 'field': 'Org Number', 'sortable': True},
                            {'name': 'Phone', 'label': t('phone'), 'field': 'Phone'},
                            {'name': 'Email', 'label': t('email'), 'field': 'Email'},
                            {'name': 'ACTIONS', 'label': '', 'field': 'ACTIONS'}
                        ]
                        ui_elements['customer_table'] = ui.table(columns=cols, rows=customers.get_customers_df().to_dict('records'), row_key='Customer ID').classes('w-full')
                        ui_elements['customer_table'].add_slot('body-cell-ACTIONS', '<q-td :props="props"><q-btn size="sm" color="primary" icon="edit" @click="$parent.$emit(\'edit\', props.row[\'Customer ID\'])" /><q-btn size="sm" color="negative" icon="delete" @click="$parent.$emit(\'delete\', props.row[\'Customer ID\'])" /></q-td>')
                        ui_elements['customer_table'].on('edit', lambda msg: open_edit_customer_dialog(msg.args))
                        ui_elements['customer_table'].on('delete', lambda msg: delete_customer(msg.args))

            # --- Inventory Management View ---
            with ui.tab_panel('inventory_mgmt'):
                with ui.tabs().classes('w-full') as tabs:
                    ui.tab('product_setup', label=t('tab_product_setup'))
                    ui.tab('qr_labels', label=t('tab_qr_labels'))
                    ui.tab('inventory', label=t('tab_inventory'))
                    ui.tab('internal_inventory', label=t('tab_internal_inventory'))
                    ui.tab('recipes', label=t('tab_recipes'))
                    ui.tab('alerts', label=t('tab_alerts'))

                with ui.tab_panels(tabs, value='product_setup').classes('w-full').bind_value(state, 'current_tab'):
                    # Tab 1: Product Setup
                    with ui.tab_panel('product_setup'):
                        with ui.row().classes('w-full no-wrap'):
                            with ui.card().classes('w-1/3 p-4'):
                                ean_input, name_input, shelf_life_input, url_input = ui.input(t('ean_code')), ui.input(t('product_name')), ui.number(t('shelf_life'), value=7), ui.input(t('product_url'))
                                with ui.row().classes('w-full gap-2'):
                                    price_in_input, price_out_input = ui.number(t('price_in'), value=0.0), ui.number(t('price_out'), value=0.0)
                                ui.button(t('save_product'), on_click=add_product)
                            with ui.card().classes('w-2/3 p-4'):
                                cols = [{'name': k, 'label': t(k.lower().replace(' ', '_')), 'field': k} for k in ['EAN', 'Name', 'Shelf Life', 'Price In', 'Price Out', 'URL', 'ACTIONS']]
                                ui_elements['product_table'] = ui.table(columns=cols, rows=products.get_products_df().to_dict('records'), row_key='EAN').classes('w-full')
                                ui_elements['product_table'].add_slot('body-cell-ACTIONS', '<q-td :props="props"><q-btn size="sm" color="primary" icon="edit" @click="$parent.$emit(\'edit\', props.row.EAN)" /><q-btn size="sm" color="negative" icon="delete" @click="$parent.$emit(\'delete\', props.row.EAN)" /></q-td>')
                                ui_elements['product_table'].on('edit', lambda msg: open_edit_dialog(msg.args))
                                ui_elements['product_table'].on('delete', lambda msg: delete_product(msg.args))

                    # Tab 2: QR Labels
                    with ui.tab_panel('qr_labels'):
                        with ui.column().classes('items-center w-full'):
                            qr_ean_input = ui.select(get_product_options(), label=t('scan_type_ean'), with_input=True).classes('w-full max-w-sm')
                            ui_elements['qr_ean_input'] = qr_ean_input
                            qr_exp_input = ui.input(t('exp_date'))
                            ui.button(t('generate_product_qr'), on_click=generate_qr)
                            qr_display, qr_info_label = ui.image().classes('w-64 h-64 border'), ui.label()
                            with ui.column().classes('items-center') as qr_download_group:
                                qr_download_group.set_visibility(False)
                                qr_qty_input = ui.number(t('quantity_labels'), value=1)
                                ui.button(t('download_pdf'), on_click=lambda: ui.notify("PDF!"))

                    # Tab 3: Inventory
                    with ui.tab_panel('inventory'):
                        with ui.row().classes('w-full no-wrap'):
                            with ui.card().classes('w-1/3 p-4'):
                                reg_ean_input = ui.select(get_product_options(), label=t('ean'), with_input=True).classes('w-full')
                                reg_date_input, reg_qty_input = ui.input(t('exp_date')), ui.number(t('qty'), value=1)
                                ui_elements['reg_ean_input'], ui_elements['reg_date_input'] = reg_ean_input, reg_date_input
                                ui.button(t('add_stock'), on_click=lambda: update_stock('Add'))
                                ui.button(t('remove_stock'), on_click=lambda: update_stock('Remove'))
                            with ui.card().classes('w-2/3 p-4'):
                                cols = [{'name': k, 'label': t(k.lower().replace(' ', '_')), 'field': k} for k in ['EAN', 'Name', 'Exp Date', 'Qty']]
                                ui_elements['inventory_table'] = ui.table(columns=cols, rows=inventory.get_inventory_df().to_dict('records')).classes('w-full')

                    # Tab 4: Internal Inventory
                    with ui.tab_panel('internal_inventory'):
                        with ui.row().classes('w-full no-wrap'):
                            with ui.card().classes('w-1/3 p-4'):
                                internal_ean_input = ui.select(get_product_options(), label=t('ean'), with_input=True).classes('w-full')
                                internal_date_input, internal_qty_input = ui.input(t('exp_date')), ui.number(t('qty_kg'), value=1, step=0.01, format='%.2f')
                                ui_elements['internal_ean_input'], ui_elements['internal_date_input'] = internal_ean_input, internal_date_input
                                ui.button(t('add_stock'), on_click=lambda: update_stock('Add', is_internal=True))
                                ui.button(t('remove_stock'), on_click=lambda: update_stock('Remove', is_internal=True))
                            with ui.card().classes('w-2/3 p-4'):
                                internal_cols = [
                                    {'name': 'EAN', 'label': t('ean'), 'field': 'EAN'},
                                    {'name': 'Name', 'label': t('name'), 'field': 'Name'},
                                    {'name': 'Exp Date', 'label': t('exp_date'), 'field': 'Exp Date'},
                                    {'name': 'Qty', 'label': t('qty_kg'), 'field': 'Qty'}
                                ]
                                ui_elements['internal_table'] = ui.table(columns=internal_cols, rows=[]).classes('w-full')

                    # Tab 5: Recipes
                    with ui.tab_panel('recipes'):
                        with ui.row().classes('w-full no-wrap gap-4'):
                            with ui.card().classes('w-1/3 p-4'):
                                ui.label(t('tab_recipes')).classes('text-lg font-bold mb-4')
                                recipe_product_selection = ui.select(get_product_options(), label=t('product'), with_input=True, on_change=refresh_all_tables).classes('w-full mb-4')
                                recipe_product_selection.bind_value(state, 'selected_recipe_ean')
                                ui_elements['recipe_product_selection'] = recipe_product_selection

                                ui.separator().classes('mb-4')
                                
                                recipe_ingredient_selection = ui.select(get_internal_product_options(), label=t('ingredient'), with_input=True).classes('w-full mb-2')
                                ui_elements['recipe_ingredient_selection'] = recipe_ingredient_selection
                                recipe_qty_input = ui.number(t('grams'), value=0).classes('w-full mb-4')

                                def add_ingredient_to_recipe():
                                    if not state['selected_recipe_ean']:
                                        ui.notify(t('ean_required'), type='warning')
                                        return
                                    if not recipe_ingredient_selection.value:
                                        ui.notify(t('ean_required'), type='warning')
                                        return
                                    
                                    recipes.add_ingredient_to_recipe(state['selected_recipe_ean'], recipe_ingredient_selection.value, recipe_qty_input.value)
                                    ui.notify(t('sale_completed'))
                                    refresh_all_tables()

                                ui.button(t('add_ingredient'), on_click=add_ingredient_to_recipe).classes('w-full')

                            with ui.card().classes('w-2/3 p-4'):
                                ui_elements['recipe_header_label'] = ui.label(f"{t('recipe_for')}: ...").classes('text-lg font-bold mb-4')
                                
                                cols_recipe = [
                                    {'name': 'Name', 'label': t('name'), 'field': 'Name'},
                                    {'name': 'Ingredient EAN', 'label': t('ean'), 'field': 'Ingredient EAN'},
                                    {'name': 'Qty', 'label': t('grams'), 'field': 'Qty'},
                                    {'name': 'ACTIONS', 'label': '', 'field': 'ACTIONS'},
                                ]
                                ui_elements['recipe_table'] = ui.table(columns=cols_recipe, rows=[]).classes('w-full')
                                ui_elements['recipe_table'].add_slot('body-cell-ACTIONS', '<q-td :props="props"><q-btn size="sm" color="negative" icon="delete" @click="$parent.$emit(\'remove_ing\', props.row[\'Ingredient EAN\'])" /></q-td>')
                                
                                def remove_ing(ing_ean):
                                    recipes.remove_ingredient_from_recipe(state['selected_recipe_ean'], ing_ean)
                                    refresh_all_tables()
                                
                                ui_elements['recipe_table'].on('remove_ing', lambda msg: remove_ing(msg.args))

                    # Tab 6: Alerts
                    with ui.tab_panel('alerts'):
                        ui.label(t('expiration_alerts')).classes('text-xl font-bold')
                        alert_msg_label = ui.label(t('no_alerts')).classes('text-lg')
                        
                        alert_cols = [
                            {'name': 'EAN', 'label': t('ean'), 'field': 'EAN', 'sortable': True},
                            {'name': 'Name', 'label': t('name'), 'field': 'Name', 'sortable': True},
                            {'name': 'Exp Date', 'label': t('exp_date'), 'field': 'Exp Date', 'sortable': True},
                            {'name': 'Qty', 'label': t('qty'), 'field': 'Qty', 'sortable': True},
                            {'name': 'Status', 'label': t('status'), 'field': 'Status', 'sortable': True},
                        ]
                        alert_table = ui.table(columns=alert_cols, rows=[]).classes('w-full mt-4')
                        
                        def check_alerts():
                            # Combine regular and internal inventory for checking
                            msg, df = alerts.check_alerts(inventory.get_raw_inventory(), internal_inventory.get_raw_inventory())
                            alert_msg_label.text = msg
                            alert_table.rows[:] = df.to_dict('records')
                            alert_table.update()

                        ui.button(t('check_now'), on_click=check_alerts).classes('mt-4')

    render_header()
    render_content()
    refresh_all_tables()
    return ui
