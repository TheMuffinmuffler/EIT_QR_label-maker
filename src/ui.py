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

def create_ui(products, inventory, internal_inventory, qr_gen, alerts, scanner):
    # --- State Management ---
    state = {
        'scanner_running': False,
        'current_tab': '1. Product Setup',
        'sales_basket': [],
        'video_capture': None,
        'last_qr_path': None,
        'lang': 'en'
    }

    def t(key):
        return TRANSLATIONS[state['lang']].get(key, key)

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
            current_tab_text = state['current_tab']
            if current_tab_text == t('tab_inventory'):
                if 'reg_ean_input' in ui_elements: ui_elements['reg_ean_input'].value = ean
                if 'reg_date_input' in ui_elements: ui_elements['reg_date_input'].value = date if date else ''
            elif current_tab_text == t('tab_internal_inventory'):
                if 'internal_ean_input' in ui_elements: ui_elements['internal_ean_input'].value = ean
                if 'internal_date_input' in ui_elements: ui_elements['internal_date_input'].value = date if date else ''
            elif current_tab_text == t('tab_sales'):
                await handle_sale_scan_global(ean, date)
            ui.notify(f"Scanned: {ean}")

        if debug_img is not None and 'scanner_view' in ui_elements:
            _, buffer = cv2.imencode('.jpg', cv2.cvtColor(debug_img, cv2.COLOR_RGB2BGR))
            b64_img = base64.b64encode(buffer).decode()
            ui_elements['scanner_view'].source = f'data:image/jpeg;base64,{b64_img}'
            ui_elements['scanner_log'].text = msg

    camera_timer = ui.timer(0.1, update_camera_frame, active=state['scanner_running'])

    # --- Shared Logic Functions ---
    def refresh_all_tables():
        if 'product_table' in ui_elements:
            ui_elements['product_table'].rows[:] = products.get_products_df().to_dict('records')
            ui_elements['product_table'].update()
        if 'inventory_table' in ui_elements:
            ui_elements['inventory_table'].rows[:] = inventory.get_inventory_df().to_dict('records')
            ui_elements['inventory_table'].update()
        if 'internal_table' in ui_elements:
            ui_elements['internal_table'].rows[:] = internal_inventory.get_inventory_df().to_dict('records')
            ui_elements['internal_table'].update()
        
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
            img, info, filepath = qr_gen.generate_qr(qr_ean_input.value, products.get_product_details(qr_ean_input.value), manual_exp_date=qr_exp_input.value)
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
            
            details = products.get_product_details(ean_field.value)
            msg, _ = manager.update_stock(ean_field.value, details['name'] if details else "Unknown", normalize_date(date_field.value), qty_field.value, action)
            ui.notify(msg)
            refresh_all_tables()

        # --- Tabs ---
        with ui.tabs().classes('w-full') as tabs:
            t1, t2, t3, t4, t5, t6 = [ui.tab(t(k)) for k in ['tab_product_setup', 'tab_qr_labels', 'tab_inventory', 'tab_internal_inventory', 'tab_alerts', 'tab_sales']]

        with ui.tab_panels(tabs, value=t1).classes('w-full').bind_value(state, 'current_tab'):
            # Tab 1: Product Setup
            with ui.tab_panel(t1):
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
            with ui.tab_panel(t2):
                with ui.column().classes('items-center w-full'):
                    qr_ean_input = ui.input(t('scan_type_ean'))
                    qr_exp_input = ui.input(t('exp_date'))
                    ui.button(t('generate_product_qr'), on_click=generate_qr)
                    qr_display, qr_info_label = ui.image().classes('w-64 h-64 border'), ui.label()
                    with ui.column().classes('items-center') as qr_download_group:
                        qr_download_group.set_visibility(False)
                        qr_qty_input = ui.number(t('quantity_labels'), value=1)
                        ui.button(t('download_pdf'), on_click=lambda: ui.notify("PDF!"))

            # Tab 3: Inventory
            with ui.tab_panel(t3):
                with ui.row().classes('w-full no-wrap'):
                    with ui.card().classes('w-1/3 p-4'):
                        reg_ean_input, reg_date_input, reg_qty_input = ui.input(t('ean')), ui.input(t('exp_date')), ui.number(t('qty'), value=1)
                        ui_elements['reg_ean_input'], ui_elements['reg_date_input'] = reg_ean_input, reg_date_input
                        ui.button(t('add_stock'), on_click=lambda: update_stock('Add'))
                        ui.button(t('remove_stock'), on_click=lambda: update_stock('Remove'))
                    with ui.card().classes('w-2/3 p-4'):
                        cols = [{'name': k, 'label': t(k.lower().replace(' ', '_')), 'field': k} for k in ['EAN', 'Name', 'Exp Date', 'Qty']]
                        ui_elements['inventory_table'] = ui.table(columns=cols, rows=inventory.get_inventory_df().to_dict('records')).classes('w-full')

            # Tab 4: Internal Inventory
            with ui.tab_panel(t4):
                with ui.row().classes('w-full no-wrap'):
                    with ui.card().classes('w-1/3 p-4'):
                        internal_ean_input, internal_date_input, internal_qty_input = ui.input(t('ean')), ui.input(t('exp_date')), ui.number(t('qty'), value=1)
                        ui_elements['internal_ean_input'], ui_elements['internal_date_input'] = internal_ean_input, internal_date_input
                        ui.button(t('add_stock'), on_click=lambda: update_stock('Add', is_internal=True))
                        ui.button(t('remove_stock'), on_click=lambda: update_stock('Remove', is_internal=True))
                    with ui.card().classes('w-2/3 p-4'):
                        cols = [{'name': k, 'label': t(k.lower().replace(' ', '_')), 'field': k} for k in ['EAN', 'Name', 'Exp Date', 'Qty']]
                        ui_elements['internal_table'] = ui.table(columns=cols, rows=internal_inventory.get_inventory_df().to_dict('records')).classes('w-full')

            # Tab 5: Alerts
            with ui.tab_panel(t5):
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

            # Tab 6: Sales
            with ui.tab_panel(t6):
                with ui.row().classes('w-full no-wrap'):
                    with ui.card().classes('w-1/3 p-4'):
                        ui.button(t('complete_sale'), on_click=complete_sale).classes('w-full mb-2')
                        ui.button(t('clear_basket'), on_click=clear_basket).classes('w-full')
                    with ui.card().classes('w-2/3 p-4'):
                        cols = [{'name': k, 'label': t(k.lower().replace(' ', '_')), 'field': k} for k in ['Name', 'EAN', 'Exp Date', 'Price', 'Qty', 'Total']]
                        ui_elements['basket_table'] = ui.table(columns=cols, rows=[]).classes('w-full')
                        ui_elements['grand_total_label'] = ui.label(f"{t('grand_total')}: 0.00")

    render_header()
    render_content()
    return ui
