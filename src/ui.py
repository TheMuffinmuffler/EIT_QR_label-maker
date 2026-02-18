import gradio as gr


def create_app(products, inventory, qr_gen, alerts, scanner):
    # --- Wrapper Functions ---
    def wrapper_generate_qr(ean):
        details = products.get_product_details(ean)
        # Returns (PIL Image, info_text) from qr_generator.py
        return qr_gen.generate_qr(ean, details)

    def wrapper_update_stock(ean, exp_date, qty, action):
        details = products.get_product_details(ean)
        name = details['name'] if details else "Unknown"
        return inventory.update_stock(ean, name, exp_date, qty, action)

    def wrapper_check_alerts():
        # Returns (message_string, dataframe) from alert_system.py
        return alerts.check_alerts(inventory.get_raw_inventory())

    def wrapper_table_select(evt: gr.SelectData, current_df):
        row_index = evt.index[0]
        col_index = evt.index[1]
        if col_index == 3:
            ean_to_remove = current_df.iloc[row_index]["EAN"]
            return products.delete_product(ean_to_remove)
        return "Click the ❌ column to delete.", products.get_products_df()

    def wrapper_scan(image):
        if image is None:
            return gr.update(), gr.update(), gr.update(), gr.update()

        # Terminal heartbeat to confirm the loop is active
        print(".", end="", flush=True)

        # Scans image and returns (EAN, Date, Status, Debug_Image)
        ean, date, msg, debug_img = scanner.scan_image(image)

        if ean:
            print(f"\n✅ SYSTEM DETECTED: EAN={ean}, Date={date}")

        # Returns updates for EAN, Date, Log, and the Debug Image component
        return (ean or gr.update()), (date or gr.update()), msg, debug_img

    def stop_webcam():
        # Hides camera component and stops the timer loop
        return gr.update(value=None, visible=False), gr.update(active=False)

    def start_webcam():
        # Shows camera component and starts the timer loop
        return gr.update(visible=True), gr.update(active=True)

    # --- Visual Layout ---
    with gr.Blocks(title="Modular Inventory System") as app:
        gr.Markdown("# 🏢 Store Inventory System")

        # Timer to pull frames from the webcam every 0.5 seconds
        scan_timer = gr.Timer(0.5, active=False)

        with gr.Tabs():
            # TAB 1: PRODUCT SETUP
            with gr.TabItem("1. Product Setup"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### ➕ Add Product")
                        add_ean = gr.Textbox(label="EAN Code")
                        add_name = gr.Textbox(label="Name")
                        add_days = gr.Number(label="Shelf Life (Days)", value=7)
                        btn_add = gr.Button("Save Product", variant="primary")
                        msg_box = gr.Textbox(label="System Log")
                    with gr.Column(scale=2):
                        # Displayed dataframe of existing products
                        product_df = gr.Dataframe(value=products.get_products_df(), interactive=False)

                btn_add.click(products.add_product, [add_ean, add_name, add_days], [msg_box, product_df])
                product_df.select(wrapper_table_select, [product_df], [msg_box, product_df])

            # TAB 2: QR GENERATOR
            with gr.TabItem("2. Print QR Labels"):
                qr_ean = gr.Textbox(label="Scan/Type EAN")
                btn_qr = gr.Button("Generate Label", variant="primary")
                out_img = gr.Image(label="Label")
                # NEW: Textbox to show readable label info and the file save path
                out_info = gr.Textbox(label="Label Details & Save Path")

                # Wiring updated to output to both the Image and the Info Textbox
                btn_qr.click(wrapper_generate_qr, [qr_ean], [out_img, out_info])

            # TAB 3: CASH REGISTER
            with gr.TabItem("3. Cash Register"):
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### 📷 Scan Item")
                        cam_input = gr.Image(sources=["webcam"], type="numpy", streaming=True)

                        with gr.Row():
                            btn_start_cam = gr.Button("▶️ Open Camera", variant="primary")
                            btn_stop_cam = gr.Button("❌ Stop Camera", variant="stop")

                        # Manual fallback button in case the timer is throttled by the browser
                        btn_manual_scan = gr.Button("🔍 Manual Scan", variant="secondary")

                        # Displays the high-contrast B&W image used by the scanner
                        debug_view = gr.Image(label="Scanner View (B&W Debugger)", interactive=False)

                        reg_ean = gr.Textbox(label="EAN")
                        reg_date = gr.Textbox(label="Exp Date")
                        reg_qty = gr.Number(label="Qty", value=1)
                        btn_in = gr.Button("Stock IN (+)", variant="primary")
                        reg_log = gr.Textbox(label="Log")

                    with gr.Column():
                        # Current inventory levels
                        reg_table = gr.Dataframe(value=inventory.get_inventory_df())

                # WIRING FOR TAB 3
                # Automatic loop: every timer tick, pull an image and scan it
                scan_timer.tick(
                    wrapper_scan,
                    inputs=[cam_input],
                    outputs=[reg_ean, reg_date, reg_log, debug_view]
                )

                # Manual trigger
                btn_manual_scan.click(
                    wrapper_scan,
                    inputs=[cam_input],
                    outputs=[reg_ean, reg_date, reg_log, debug_view]
                )

                btn_stop_cam.click(fn=stop_webcam, outputs=[cam_input, scan_timer])
                btn_start_cam.click(fn=start_webcam, outputs=[cam_input, scan_timer])

                # Update inventory stock levels
                btn_in.click(
                    wrapper_update_stock,
                    [reg_ean, reg_date, reg_qty, gr.State("Add")],
                    [reg_log, reg_table]
                )

            # TAB 4: ALERTS
            with gr.TabItem("4. Alerts"):
                btn_alert = gr.Button("Check Expirations", variant="primary")
                alert_msg = gr.Textbox(label="Alert Status")
                alert_tbl = gr.Dataframe()

                # Displays expiration alerts in a message box and table
                btn_alert.click(wrapper_check_alerts, None, [alert_msg, alert_tbl])

    return app