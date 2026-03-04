from nicegui import ui, events, context
import pandas as pd
import cv2
import base64
import numpy as np
from datetime import datetime
import asyncio

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
        'last_scan_msg': 'Ready...',
        'current_tab': '1. Product Setup',
        'sales_basket': [],
        'video_capture': None,
        'last_qr_path': None
    }

    # --- Helper: Update Tables ---
    def refresh_tables():
        product_table.rows[:] = products.get_products_df().to_dict('records')
        product_table.update()
        inventory_table.rows[:] = inventory.get_inventory_df().to_dict('records')
        inventory_table.update()
        opened_table.rows[:] = opened.get_opened_df().to_dict('records')
        opened_table.update()
        basket_table.rows[:] = state['sales_basket']
        basket_table.update()

    # --- Tab 1: Product Setup Logic ---
    async def add_product():
        msg, df = products.add_product(ean_input.value, name_input.value, shelf_life_input.value, shelf_life_opened_input.value)
        ui.notify(msg)
        refresh_tables()
        ean_input.value = ''
        name_input.value = ''

    async def delete_product(ean):
        msg, df = products.delete_product(ean)
        ui.notify(msg)
        refresh_tables()

    # --- Tab 2: QR Generator Logic ---
    def generate_qr():
        img, info, filepath = qr_gen.generate_qr(qr_ean_input.value, products.get_product_details(qr_ean_input.value), manual_exp_date=qr_exp_input.value)
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
            ui.notify(info, type='negative')

    def download_pdf():
        if not state['last_qr_path']:
            ui.notify("Generate a QR code first.", type='warning')
            return
        
        pdf_path = qr_gen.generate_pdf(
            qr_ean_input.value, 
            products.get_product_details(qr_ean_input.value),
            qr_exp_input.value or normalize_date(datetime.now().strftime("%d-%m-%Y")), # simplified fallback
            qr_qty_input.value,
            state['last_qr_path']
        )
        if pdf_path:
            ui.download(pdf_path)
            ui.notify(f"PDF generated with {qr_qty_input.value} labels.")

    def set_suggested_date():
        details = products.get_product_details(qr_ean_input.value)
        if details:
            from datetime import datetime, timedelta
            today = datetime.now()
            exp_date = today + timedelta(days=details['shelf_life'])
            qr_exp_input.value = exp_date.strftime("%d-%m-%Y")
        else:
            ui.notify("EAN unknown. Cannot suggest date.", type='warning')

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
            # Normalize date from scanner (handles old QR codes)
            date = normalize_date(date)
            
            if state['current_tab'] == '3. Inventory':
                reg_ean_input.value = ean
                reg_date_input.value = date if date else ''
            elif state['current_tab'] == '4. Opened Products':
                opened_ean_input.value = ean
                opened_date_input.value = date if date else ''
            elif state['current_tab'] == '6. Sales':
                await handle_sale_scan(ean, date)
            ui.notify(f"Scanned: {ean}")

        if debug_img is not None:
            _, buffer = cv2.imencode('.jpg', cv2.cvtColor(debug_img, cv2.COLOR_RGB2BGR))
            b64_img = base64.b64encode(buffer).decode()
            scanner_view.source = f'data:image/jpeg;base64,{b64_img}'
            scanner_log.text = msg

    camera_timer = ui.timer(0.1, update_camera_frame, active=False)

    def toggle_scanner(e):
        state['scanner_running'] = e.value
        camera_timer.active = e.value
        if not e.value:
            scanner_view.source = ''
            scanner_log.text = 'Scanner Stopped'
            if state['video_capture']:
                state['video_capture'].release()
                state['video_capture'] = None

    # --- Sales Logic ---
    async def handle_sale_scan(ean, date):
        date = normalize_date(date) # Normalize here too
        if date:
            details = products.get_product_details(ean)
            name = details['name'] if details else "Unknown"
            add_to_basket(ean, name, date)
        else:
            batches = [b for b in inventory.get_raw_inventory() if str(b['ean']) == str(ean)]
            if not batches:
                ui.notify(f"No inventory found for EAN: {ean}", type='warning')
            elif len(batches) == 1:
                add_to_basket(batches[0]['ean'], batches[0]['name'], batches[0]['exp_date'])
            else:
                show_batch_selection(batches)

    def show_batch_selection(batches):
        with ui.dialog() as dialog, ui.card():
            ui.label(f'Select Batch for {batches[0]["name"]}').classes('text-lg font-bold')
            ui.label('Multiple expiration dates found. Please choose one:').classes('text-sm text-gray-600')
            
            for b in batches:
                with ui.row().classes('w-full items-center justify-between border-b py-2'):
                    ui.label(f"Exp: {b['exp_date']} (Stock: {b['qty']})")
                    ui.button('Select', on_click=lambda b=b: [add_to_basket(b['ean'], b['name'], b['exp_date']), dialog.close()])
            
            ui.button('Cancel', on_click=dialog.close).props('flat')
        dialog.open()

    def add_to_basket(ean, name, date):
        date = normalize_date(date)
        for item in state['sales_basket']:
            if item['EAN'] == ean and item['Exp Date'] == date:
                item['Qty'] += 1
                refresh_tables()
                ui.notify(f"Added another {name} ({date}) to basket")
                return
        
        state['sales_basket'].append({
            'EAN': ean,
            'Name': name,
            'Exp Date': date,
            'Qty': 1
        })
        refresh_tables()
        ui.notify(f"Added {name} ({date}) to basket")

    async def complete_sale():
        if not state['sales_basket']:
            ui.notify("Basket is empty!", type='warning')
            return
        
        success_count = 0
        for item in state['sales_basket']:
            msg, _ = inventory.update_stock(item['EAN'], item['Name'], item['Exp Date'], item['Qty'], "Remove")
            if "Remove:" in msg:
                success_count += 1
            else:
                ui.notify(f"Error for {item['Name']}: {msg}", type='negative')
        
        if success_count > 0:
            ui.notify(f"Sale completed! {success_count} items processed.")
            state['sales_basket'] = []
            refresh_tables()

    def clear_basket():
        state['sales_basket'] = []
        refresh_tables()

    # --- UI Layout ---
    ui.colors(primary='#38b000', secondary='#008000', accent='#ccff33')

    # SHARED HEADER
    with ui.header().classes('items-center justify-between bg-white text-black border-b p-2'):
        with ui.row().classes('items-center'):
            ui.label('Store Inventory System').classes('text-2xl font-bold text-primary mr-8')
            ui.switch('Camera', on_change=toggle_scanner).bind_value(state, 'scanner_running')
        
        with ui.row().classes('items-center gap-4'):
            scanner_view = ui.image().classes('w-48 h-24 bg-black border rounded shadow-sm')
            scanner_log = ui.label('Ready...').classes('text-xs font-mono w-48 overflow-hidden')

    with ui.tabs().classes('w-full') as tabs:
        t1 = ui.tab('1. Product Setup')
        t2 = ui.tab('2. Print QR Labels')
        t3 = ui.tab('3. Inventory')
        t4 = ui.tab('4. Opened Products')
        t5 = ui.tab('5. Alerts')
        t6 = ui.tab('6. Sales')

    with ui.tab_panels(tabs, value=t1).classes('w-full').bind_value(state, 'current_tab'):
        
        # PANEL 1: PRODUCT SETUP
        with ui.tab_panel(t1):
            with ui.row().classes('w-full no-wrap'):
                with ui.card().classes('w-1/3 p-4'):
                    ui.label('Add New Product').classes('text-xl font-bold')
                    ean_input = ui.input('EAN Code').classes('w-full')
                    name_input = ui.input('Product Name').classes('w-full')
                    shelf_life_input = ui.number('Shelf Life (Days)', value=7).classes('w-full')
                    shelf_life_opened_input = ui.number('Shelf Life Opened (Days)', value=3).classes('w-full')
                    ui.button('Save Product', on_click=add_product).classes('w-full mt-4')

                with ui.card().classes('w-2/3 p-4'):
                    ui.label('Product Database').classes('text-xl font-bold')
                    columns = [
                        {'name': 'EAN', 'label': 'EAN', 'field': 'EAN', 'sortable': True},
                        {'name': 'Name', 'label': 'Name', 'field': 'Name', 'sortable': True},
                        {'name': 'Shelf Life', 'label': 'Shelf Life', 'field': 'Shelf Life'},
                        {'name': 'Shelf Life (Opened)', 'label': 'Shelf Life (Opened)', 'field': 'Shelf Life (Opened)'},
                        {'name': 'DELETE', 'label': 'Delete', 'field': 'DELETE'},
                    ]
                    product_table = ui.table(columns=columns, rows=products.get_products_df().to_dict('records'), row_key='EAN').classes('w-full')
                    product_table.add_slot('body-cell-DELETE', '''
                        <q-td :props="props">
                            <q-btn size="sm" color="negative" round dense icon="delete" @click="$parent.$emit('delete', props.row.EAN)" />
                        </q-td>
                    ''')
                    product_table.on('delete', lambda msg: delete_product(msg.args))

        # PANEL 2: QR GENERATOR
        with ui.tab_panel(t2):
            with ui.column().classes('items-center w-full'):
                ui.label('Generate QR Label').classes('text-xl font-bold')
                
                with ui.row().classes('items-center gap-2'):
                    qr_ean_input = ui.input('Scan or Type EAN').classes('w-64')
                    ui.button(icon='auto_fix_high', on_click=set_suggested_date).props('flat').tooltip('Suggest date from shelf life')
                
                with ui.input('Expiration Date (DD-MM-YYYY)') as qr_exp_input:
                    with qr_exp_input.add_slot('append'):
                        ui.icon('edit_calendar').on('click', lambda: qr_menu.open()).classes('cursor-pointer')
                    with ui.menu() as qr_menu:
                        ui.date(mask='DD-MM-YYYY').bind_value(qr_exp_input)
                
                ui.button('Generate Label', on_click=generate_qr).classes('w-64 mt-2')
                qr_display = ui.image().classes('w-64 h-64 mt-4 border')
                qr_info_label = ui.label('').classes('mt-2 text-center text-gray-600 whitespace-pre-line')
                
                with ui.column().classes('items-center mt-4') as qr_download_group:
                    qr_download_group.set_visibility(False)
                    qr_qty_input = ui.number('Quantity of labels', value=1, min=1, step=1).classes('w-48')
                    ui.button('Download Printable PDF', on_click=download_pdf, icon='download', color='secondary').classes('w-64 mt-2')

        # PANEL 3: INVENTORY (STOCK ADJUSTMENT)
        with ui.tab_panel(t3):
            with ui.row().classes('w-full no-wrap'):
                with ui.card().classes('w-1/3 p-4'):
                    ui.label('Stock Adjustment').classes('text-xl font-bold')
                    reg_ean_input = ui.input('EAN').classes('w-full mt-2')
                    
                    with ui.input('Exp Date (DD-MM-YYYY)') as reg_date_input:
                        with reg_date_input.add_slot('append'):
                            ui.icon('edit_calendar').on('click', lambda: menu.open()).classes('cursor-pointer')
                        with ui.menu() as menu:
                            ui.date(mask='DD-MM-YYYY').bind_value(reg_date_input)
                    
                    reg_qty_input = ui.number('Quantity', value=1).classes('w-full')
                    
                    with ui.row().classes('w-full gap-2 mt-4'):
                        ui.button('Add Stock (+)', on_click=lambda: update_stock('Add')).classes('flex-grow')
                        ui.button('Remove Stock (-)', on_click=lambda: update_stock('Remove'), color='orange').classes('flex-grow')

                with ui.card().classes('w-2/3 p-4'):
                    ui.label('Current Stock').classes('text-xl font-bold')
                    inv_cols = [
                        {'name': 'EAN', 'label': 'EAN', 'field': 'EAN', 'sortable': True},
                        {'name': 'Name', 'label': 'Name', 'field': 'Name', 'sortable': True},
                        {'name': 'Exp Date', 'label': 'Exp Date', 'field': 'Exp Date', 'sortable': True},
                        {'name': 'Qty', 'label': 'Qty', 'field': 'Qty', 'sortable': True},
                    ]
                    inventory_table = ui.table(columns=inv_cols, rows=inventory.get_inventory_df().to_dict('records')).classes('w-full')

            async def update_stock(action):
                ean = reg_ean_input.value
                date = normalize_date(reg_date_input.value) # Ensure normalization here too
                details = products.get_product_details(ean)
                name = details['name'] if details else "Unknown"
                msg, df = inventory.update_stock(ean, name, date, reg_qty_input.value, action)
                ui.notify(msg)
                refresh_tables()

        # PANEL 4: OPENED PRODUCTS
        with ui.tab_panel(t4):
            with ui.row().classes('w-full no-wrap'):
                with ui.column().classes('w-1/3'):
                    ui.label('Mark as Opened').classes('text-xl font-bold')
                    opened_ean_input = ui.input('EAN').classes('w-full mt-2')
                    
                    with ui.input('Orig. Exp Date (DD-MM-YYYY)') as opened_date_input:
                        with opened_date_input.add_slot('append'):
                            ui.icon('edit_calendar').on('click', lambda: opened_menu.open()).classes('cursor-pointer')
                        with ui.menu() as opened_menu:
                            ui.date(mask='DD-MM-YYYY').bind_value(opened_date_input)
                            
                    ui.button('Open Product', on_click=lambda: open_product()).classes('w-full mt-4')
                
                with ui.card().classes('w-2/3 p-4'):
                    ui.label('Opened Items').classes('text-xl font-bold')
                    open_cols = [
                        {'name': 'EAN', 'label': 'EAN', 'field': 'EAN'},
                        {'name': 'Name', 'label': 'Name', 'field': 'Name'},
                        {'name': 'Opened Date', 'label': 'Opened Date', 'field': 'Opened Date'},
                        {'name': 'New Exp Date', 'label': 'New Exp Date', 'field': 'New Exp Date'},
                        {'name': 'REMOVE', 'label': 'Remove', 'field': 'REMOVE'},
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
            ui.label('Expiration Alerts').classes('text-xl font-bold')
            alert_msg_label = ui.label('No alerts.').classes('text-lg')
            
            alert_cols = [
                {'name': 'EAN', 'label': 'EAN', 'field': 'EAN', 'sortable': True},
                {'name': 'Name', 'label': 'Name', 'field': 'Name', 'sortable': True},
                {'name': 'Exp Date', 'label': 'Exp Date', 'field': 'Exp Date', 'sortable': True},
                {'name': 'Qty', 'label': 'Qty', 'field': 'Qty', 'sortable': True},
                {'name': 'Status', 'label': 'Status', 'field': 'Status', 'sortable': True},
            ]
            alert_table = ui.table(columns=alert_cols, rows=[]).classes('w-full mt-4')
            
            def check_alerts():
                msg, df = alerts.check_alerts(inventory.get_raw_inventory(), opened.get_raw_opened())
                alert_msg_label.text = msg
                alert_table.rows[:] = df.to_dict('records')
                alert_table.update()

            ui.button('Check Now', on_click=check_alerts).classes('mt-4')

        # PANEL 6: SALES
        with ui.tab_panel(t6):
            with ui.row().classes('w-full no-wrap'):
                with ui.card().classes('w-1/3 p-4'):
                    ui.label('Scan to Add to Basket').classes('text-xl font-bold')
                    ui.label('1. Toggle camera in header').classes('text-xs text-gray-500')
                    ui.label('2. Scan QR or Barcode').classes('text-xs text-gray-500')
                    ui.label('3. If multiple batches exist, select from popup').classes('text-xs text-gray-500')
                    
                    ui.separator().classes('my-4')
                    
                    ui.button('Complete Sale', on_click=complete_sale, color='primary').classes('w-full text-lg h-16')
                    ui.button('Clear Basket', on_click=clear_basket, color='grey').classes('w-full mt-2')

                with ui.card().classes('w-2/3 p-4'):
                    ui.label('Current Sale Basket').classes('text-xl font-bold')
                    basket_cols = [
                        {'name': 'Name', 'label': 'Product', 'field': 'Name'},
                        {'name': 'EAN', 'label': 'EAN', 'field': 'EAN'},
                        {'name': 'Exp Date', 'label': 'Exp Date', 'field': 'Exp Date'},
                        {'name': 'Qty', 'label': 'Qty', 'field': 'Qty'},
                    ]
                    basket_table = ui.table(columns=basket_cols, rows=state['sales_basket']).classes('w-full')

    return ui
