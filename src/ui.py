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

def create_ui(products, inventory, opened, qr_gen, alerts, scanner):
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
        # The timer is started/stopped via state, handled in the render_content refresh
        if not e.value:
            if 'scanner_view' in ui_elements:
                ui_elements['scanner_view'].source = ''
            if 'scanner_log' in ui_elements:
                ui_elements['scanner_log'].text = t('scanner_stopped')
            if state['video_capture']:
                state['video_capture'].release()
                state['video_capture'] = None

    @ui.refreshable
    def render_content():
        # --- Helper: Update Tables ---
        def refresh_tables():
            product_table.rows[:] = products.get_products_df().to_dict('records')
            product_table.update()
            inventory_table.rows[:] = inventory.get_inventory_df().to_dict('records')
            inventory_table.update()
            opened_table.rows[:] = opened.get_opened_df().to_dict('records')
            opened_table.update()
            
            # Update Basket and Calculate Grand Total
            basket_rows = []
            grand_total = 0.0
            for item in state['sales_basket']:
                row_total = item['Price'] * item['Qty']
                grand_total += row_total
                basket_rows.append({
                    **item,
                    'Total': f"{row_total:.2f}"
                })
            basket_table.rows[:] = basket_rows
            basket_table.update()
            if 'grand_total_label' in ui_elements:
                ui_elements['grand_total_label'].text = f"{t('grand_total')}: {grand_total:.2f}"

        # --- Tab 1: Product Setup Logic ---
        async def add_product():
            msg, df = products.add_product(
                ean_input.value, 
                name_input.value, 
                shelf_life_input.value, 
                shelf_life_opened_input.value, 
                url_input.value,
                price_in_input.value,
                price_out_input.value
            )
            ui.notify(msg)
            refresh_tables()
            ean_input.value = ''
            name_input.value = ''
            url_input.value = ''
            price_in_input.value = 0.0
            price_out_input.value = 0.0

        async def delete_product(ean):
            msg, df = products.delete_product(ean)
            ui.notify(msg)
            refresh_tables()

        def open_edit_dialog(ean):
            details = products.get_product_details(ean)
            if not details:
                return

            with ui.dialog() as dialog, ui.card().classes('w-96 p-4'):
                ui.label(t('edit_product')).classes('text-xl font-bold mb-2')
                ui.label(f"{t('ean')}: {ean}").classes('text-sm text-gray-500 mb-4')
                
                edit_name = ui.input(t('product_name'), value=details['name']).classes('w-full')
                edit_shelf = ui.number(t('shelf_life'), value=details['shelf_life']).classes('w-full')
                edit_shelf_op = ui.number(t('shelf_life_opened'), value=details.get('shelf_life_opened', 3)).classes('w-full')
                edit_url = ui.input(t('product_url'), value=details.get('url', '')).classes('w-full')
                
                with ui.row().classes('w-full gap-2'):
                    edit_price_in = ui.number(t('price_in'), value=details.get('price_in', 0.0), format='%.2f').classes('flex-grow')
                    edit_price_out = ui.number(t('price_out'), value=details.get('price_out', 0.0), format='%.2f').classes('flex-grow')

                async def save_edit():
                    msg, _ = products.update_product(
                        ean, edit_name.value, edit_shelf.value, edit_shelf_op.value, 
                        edit_url.value, edit_price_in.value, edit_price_out.value
                    )
                    ui.notify(msg)
                    refresh_tables()
                    dialog.close()

                with ui.row().classes('w-full justify-end mt-4'):
                    ui.button(t('cancel'), on_click=dialog.close).props('flat')
                    ui.button(t('update_product'), on_click=save_edit)
            
            dialog.open()

        # --- Tab 2: QR Generator Logic ---
        def generate_qr():
            img, info, filepath = qr_gen.generate_qr(
                qr_ean_input.value, 
                products.get_product_details(qr_ean_input.value), 
                manual_exp_date=qr_exp_input.value
            )
            if img:
                state['last_qr_path'] = filepath
                import io
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode()
                qr_display.source = f'data:image/png;base64,{img_str}'
                qr_info_label.text = info
                qr_download_group.set_visibility(True)
            else:
                ui.notify(t('ean_unknown'), type='negative')

        def download_pdf():
            if not state['last_qr_path']:
                ui.notify("Generate a QR code first.", type='warning')
                return
            
            pdf_path = qr_gen.generate_pdf(
                qr_ean_input.value, 
                products.get_product_details(qr_ean_input.value),
                qr_exp_input.value or normalize_date(datetime.now().strftime("%d-%m-%Y")),
                qr_qty_input.value,
                state['last_qr_path']
            )
            if pdf_path:
                ui.download(pdf_path)
                ui.notify(f"PDF generated with {qr_qty_input.value} labels.")

        def set_suggested_date():
            details = products.get_product_details(qr_ean_input.value)
            if details:
                today = datetime.now()
                exp_date = today + timedelta(days=details['shelf_life'])
                qr_exp_input.value = exp_date.strftime("%d-%m-%Y")
            else:
                ui.notify(t('ean_unknown'), type='warning')

        # --- Scanner Logic ---
        async def update_camera_frame():
            if not state['scanner_running']:
                return
                
            if state['video_capture'] is None:
                state['video_capture'] = cv2.VideoCapture(0)
            
            ret, frame = state['video_capture'].read()
            if not ret:
                return
            
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            ean, date, msg, debug_img = scanner.scan_image(rgb_frame)
            
            if ean:
                date = normalize_date(date)
                
                if state['current_tab'] == t('tab_inventory'):
                    reg_ean_input.value = ean
                    reg_date_input.value = date if date else ''
                elif state['current_tab'] == t('tab_opened'):
                    opened_ean_input.value = ean
                    opened_date_input.value = date if date else ''
                elif state['current_tab'] == t('tab_sales'):
                    await handle_sale_scan(ean, date)
                ui.notify(f"Scanned: {ean}")

            if debug_img is not None and 'scanner_view' in ui_elements:
                _, buffer = cv2.imencode('.jpg', cv2.cvtColor(debug_img, cv2.COLOR_RGB2BGR))
                b64_img = base64.b64encode(buffer).decode()
                ui_elements['scanner_view'].source = f'data:image/jpeg;base64,{b64_img}'
                ui_elements['scanner_log'].text = msg

        # We keep the timer here so it's always running when content is rendered
        camera_timer = ui.timer(0.1, update_camera_frame, active=state['scanner_running'])

        # --- Sales Logic ---
        async def handle_sale_scan(ean, date):
            date = normalize_date(date)
            details = products.get_product_details(ean)
            name = details['name'] if details else "Unknown"
            price = details['price_out'] if details else 0.0
            
            if date:
                add_to_basket(ean, name, date, price)
            else:
                batches = [b for b in inventory.get_raw_inventory() if str(b['ean']) == str(ean)]
                if not batches:
                    ui.notify(f"{t('no_inventory_found')}: {ean}", type='warning')
                elif len(batches) == 1:
                    add_to_basket(batches[0]['ean'], batches[0]['name'], batches[0]['exp_date'], price)
                else:
                    show_batch_selection(batches, price)

        def show_batch_selection(batches, price):
            with ui.dialog() as dialog, ui.card():
                ui.label(t('select_batch')).classes('text-lg font-bold')
                ui.label(t('multiple_dates_found')).classes('text-sm text-gray-600')
                
                for b in batches:
                    with ui.row().classes('w-full items-center justify-between border-b py-2'):
                        ui.label(f"Exp: {b['exp_date']} (Stock: {b['qty']})")
                        ui.button(t('select'), on_click=lambda b=b: [add_to_basket(b['ean'], b['name'], b['exp_date'], price), dialog.close()])
                
                ui.button(t('cancel'), on_click=dialog.close).props('flat')
            dialog.open()

        def add_to_basket(ean, name, date, price):
            date = normalize_date(date)
            for item in state['sales_basket']:
                if item['EAN'] == ean and item['Exp Date'] == date:
                    item['Qty'] += 1
                    refresh_tables()
                    return
            
            state['sales_basket'].append({
                'EAN': ean,
                'Name': name,
                'Exp Date': date,
                'Qty': 1,
                'Price': price
            })
            refresh_tables()

        async def complete_sale():
            if not state['sales_basket']:
                ui.notify(t('basket_empty'), type='warning')
                return
            
            success_count = 0
            for item in state['sales_basket']:
                msg, _ = inventory.update_stock(item['EAN'], item['Name'], item['Exp Date'], item['Qty'], "Remove")
                if "Remove:" in msg:
                    success_count += 1
            
            if success_count > 0:
                ui.notify(t('sale_completed'))
                state['sales_basket'] = []
                refresh_tables()

        def clear_basket():
            state['sales_basket'] = []
            refresh_tables()

        with ui.tabs().classes('w-full') as tabs:
            t1 = ui.tab(t('tab_product_setup'))
            t2 = ui.tab(t('tab_qr_labels'))
            t3 = ui.tab(t('tab_inventory'))
            t4 = ui.tab(t('tab_opened'))
            t5 = ui.tab(t('tab_alerts'))
            t6 = ui.tab(t('tab_sales'))

        with ui.tab_panels(tabs, value=t1).classes('w-full').bind_value(state, 'current_tab'):
            
            # PANEL 1: PRODUCT SETUP
            with ui.tab_panel(t1):
                with ui.row().classes('w-full no-wrap'):
                    with ui.card().classes('w-1/3 p-4'):
                        ui.label(t('add_new_product')).classes('text-xl font-bold')
                        ean_input = ui.input(t('ean_code')).classes('w-full')
                        name_input = ui.input(t('product_name')).classes('w-full')
                        shelf_life_input = ui.number(t('shelf_life'), value=7).classes('w-full')
                        shelf_life_opened_input = ui.number(t('shelf_life_opened'), value=3).classes('w-full')
                        url_input = ui.input(t('product_url'), placeholder='e.g. mystore.com/info').classes('w-full')
                        
                        with ui.row().classes('w-full gap-2'):
                            price_in_input = ui.number(t('price_in'), value=0.0, format='%.2f').classes('flex-grow')
                            price_out_input = ui.number(t('price_out'), value=0.0, format='%.2f').classes('flex-grow')
                            
                        ui.button(t('save_product'), on_click=add_product).classes('w-full mt-4')

                    with ui.card().classes('w-2/3 p-4'):
                        ui.label(t('product_database')).classes('text-xl font-bold')
                        columns = [
                            {'name': 'EAN', 'label': t('ean'), 'field': 'EAN', 'sortable': True},
                            {'name': 'Name', 'label': t('name'), 'field': 'Name', 'sortable': True},
                            {'name': 'Shelf Life', 'label': t('shelf_life'), 'field': 'Shelf Life'},
                            {'name': 'Shelf Life (Opened)', 'label': t('shelf_life_opened'), 'field': 'Shelf Life (Opened)'},
                            {'name': 'Price In', 'label': t('price_in'), 'field': 'Price In', 'sortable': True},
                            {'name': 'Price Out', 'label': t('price_out'), 'field': 'Price Out', 'sortable': True},
                            {'name': 'URL', 'label': t('url'), 'field': 'URL'},
                            {'name': 'ACTIONS', 'label': '', 'field': 'ACTIONS'},
                        ]
                        product_table = ui.table(columns=columns, rows=products.get_products_df().to_dict('records'), row_key='EAN').classes('w-full')
                        product_table.add_slot('body-cell-ACTIONS', '''
                            <q-td :props="props">
                                <q-btn size="sm" color="primary" round dense icon="edit" @click="$parent.$emit('edit', props.row.EAN)" class="q-mr-xs" />
                                <q-btn size="sm" color="negative" round dense icon="delete" @click="$parent.$emit('delete', props.row.EAN)" />
                            </q-td>
                        ''')
                        product_table.on('edit', lambda msg: open_edit_dialog(msg.args))
                        product_table.on('delete', lambda msg: delete_product(msg.args))

            # PANEL 2: QR GENERATOR
            with ui.tab_panel(t2):
                with ui.column().classes('items-center w-full'):
                    ui.label(t('generate_qr_label')).classes('text-xl font-bold')
                    
                    with ui.card().classes('p-4'):
                        with ui.row().classes('items-center gap-2'):
                            qr_ean_input = ui.input(t('scan_type_ean')).classes('w-64')
                            ui.button(icon='auto_fix_high', on_click=set_suggested_date).props('flat').tooltip(t('suggest_tooltip'))
                        
                        with ui.input(t('exp_date')) as qr_exp_input:
                            with qr_exp_input.add_slot('append'):
                                ui.icon('edit_calendar').on('click', lambda: qr_menu.open()).classes('cursor-pointer')
                            with ui.menu() as qr_menu:
                                ui.date(mask='DD-MM-YYYY').bind_value(qr_exp_input)
                        
                        ui.button(t('generate_product_qr'), on_click=generate_qr).classes('w-full mt-2')
                    
                    qr_display = ui.image().classes('w-64 h-64 mt-4 border')
                    qr_info_label = ui.label('').classes('mt-2 text-center text-gray-600 whitespace-pre-line')
                    
                    with ui.column().classes('items-center mt-4') as qr_download_group:
                        qr_download_group.set_visibility(False)
                        qr_qty_input = ui.number(t('quantity_labels'), value=1, min=1, step=1).classes('w-48')
                        ui.button(t('download_pdf'), on_click=download_pdf, icon='download', color='secondary').classes('w-64 mt-2')

            # PANEL 3: INVENTORY (STOCK ADJUSTMENT)
            with ui.tab_panel(t3):
                with ui.row().classes('w-full no-wrap'):
                    with ui.card().classes('w-1/3 p-4'):
                        ui.label(t('stock_adjustment')).classes('text-xl font-bold')
                        reg_ean_input = ui.input(t('ean')).classes('w-full mt-2')
                        
                        with ui.input(t('exp_date')) as reg_date_input:
                            with reg_date_input.add_slot('append'):
                                ui.icon('edit_calendar').on('click', lambda: menu.open()).classes('cursor-pointer')
                            with ui.menu() as menu:
                                ui.date(mask='DD-MM-YYYY').bind_value(reg_date_input)
                        
                        reg_qty_input = ui.number(t('qty'), value=1).classes('w-full')
                        
                        with ui.row().classes('w-full gap-2 mt-4'):
                            ui.button(t('add_stock'), on_click=lambda: update_stock('Add')).classes('flex-grow')
                            ui.button(t('remove_stock'), on_click=lambda: update_stock('Remove'), color='orange').classes('flex-grow')

                    with ui.card().classes('w-2/3 p-4'):
                        ui.label(t('current_stock')).classes('text-xl font-bold')
                        inv_cols = [
                            {'name': 'EAN', 'label': t('ean'), 'field': 'EAN', 'sortable': True},
                            {'name': 'Name', 'label': t('name'), 'field': 'Name', 'sortable': True},
                            {'name': 'Exp Date', 'label': t('exp_date'), 'field': 'Exp Date', 'sortable': True},
                            {'name': 'Qty', 'label': t('qty'), 'field': 'Qty', 'sortable': True},
                        ]
                        inventory_table = ui.table(columns=inv_cols, rows=inventory.get_inventory_df().to_dict('records')).classes('w-full')

                async def update_stock(action):
                    ean = reg_ean_input.value
                    date = normalize_date(reg_date_input.value)
                    details = products.get_product_details(ean)
                    name = details['name'] if details else "Unknown"
                    msg, df = inventory.update_stock(ean, name, date, reg_qty_input.value, action)
                    ui.notify(msg)
                    refresh_tables()

            # PANEL 4: OPENED PRODUCTS
            with ui.tab_panel(t4):
                with ui.row().classes('w-full no-wrap'):
                    with ui.column().classes('w-1/3'):
                        ui.label(t('mark_as_opened')).classes('text-xl font-bold')
                        opened_ean_input = ui.input(t('ean')).classes('w-full mt-2')
                        
                        with ui.input(t('orig_exp_date')) as opened_date_input:
                            with opened_date_input.add_slot('append'):
                                ui.icon('edit_calendar').on('click', lambda: opened_menu.open()).classes('cursor-pointer')
                            with ui.menu() as opened_menu:
                                ui.date(mask='DD-MM-YYYY').bind_value(opened_date_input)
                                
                        ui.button(t('open_product'), on_click=lambda: open_product()).classes('w-full mt-4')
                    
                    with ui.card().classes('w-2/3 p-4'):
                        ui.label(t('opened_items')).classes('text-xl font-bold')
                        open_cols = [
                            {'name': 'EAN', 'label': t('ean'), 'field': 'EAN'},
                            {'name': 'Name', 'label': t('name'), 'field': 'Name'},
                            {'name': 'Opened Date', 'label': t('opened_date'), 'field': 'Opened Date'},
                            {'name': 'New Exp Date', 'label': t('new_exp_date'), 'field': 'New Exp Date'},
                            {'name': 'REMOVE', 'label': t('remove'), 'field': 'REMOVE'},
                        ]
                        opened_table = ui.table(columns=open_cols, rows=opened.get_opened_df().to_dict('records')).classes('w-full')
                        opened_table.add_slot('body-cell-REMOVE', '''
                            <q-td :props="props">
                                <q-btn size="sm" color="negative" round dense icon="close" @click="$parent.$emit('remove_opened', props.rowIndex)" />
                            </q-td>
                        ''')
                        opened_table.on('remove_opened', lambda msg: remove_opened(msg.args))

                async def open_product():
                    ean = opened_ean_input.value
                    date = normalize_date(opened_date_input.value)
                    msg, op_df, inv_df = opened.open_product(ean, date)
                    ui.notify(msg)
                    refresh_tables()

                async def remove_opened(index):
                    msg, df = opened.remove_opened(index)
                    ui.notify(msg)
                    refresh_tables()

            # PANEL 5: ALERTS
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
                    msg, df = alerts.check_alerts(inventory.get_raw_inventory(), opened.get_raw_opened())
                    alert_msg_label.text = msg
                    alert_table.rows[:] = df.to_dict('records')
                    alert_table.update()

                ui.button(t('check_now'), on_click=check_alerts).classes('mt-4')

            # PANEL 6: SALES
            with ui.tab_panel(t6):
                with ui.row().classes('w-full no-wrap'):
                    with ui.card().classes('w-1/3 p-4'):
                        ui.label(t('scan_to_basket')).classes('text-xl font-bold')
                        ui.label(t('step1')).classes('text-xs text-gray-500')
                        ui.label(t('step2')).classes('text-xs text-gray-500')
                        ui.label(t('step3')).classes('text-xs text-gray-500')
                        
                        ui.separator().classes('my-4')
                        
                        ui.button(t('complete_sale'), on_click=complete_sale, color='primary').classes('w-full text-lg h-16')
                        ui.button(t('clear_basket'), on_click=clear_basket, color='grey').classes('w-full mt-2')

                    with ui.card().classes('w-2/3 p-4'):
                        ui.label(t('current_basket')).classes('text-xl font-bold')
                        basket_cols = [
                            {'name': 'Name', 'label': t('product'), 'field': 'Name'},
                            {'name': 'EAN', 'label': t('ean'), 'field': 'EAN'},
                            {'name': 'Exp Date', 'label': t('exp_date'), 'field': 'Exp Date'},
                            {'name': 'Price', 'label': t('price'), 'field': 'Price'},
                            {'name': 'Qty', 'label': t('qty'), 'field': 'Qty'},
                            {'name': 'Total', 'label': t('total'), 'field': 'Total'},
                        ]
                        basket_table = ui.table(columns=basket_cols, rows=[]).classes('w-full')
                        
                        ui.separator().classes('my-4')
                        with ui.row().classes('w-full justify-end'):
                            ui_elements['grand_total_label'] = ui.label(f"{t('grand_total')}: 0.00").classes('text-2xl font-bold text-primary')

    # Main Layout
    ui.colors(primary='#38b000', secondary='#008000', accent='#ccff33')
    
    with ui.header().classes('items-center justify-between bg-white text-black border-b p-2'):
        render_header()
        
    render_content()
    
    return ui
