import gradio as gr


def create_app(products, inventory, qr_gen, alerts, scanner):
    # --- Wrapper Functions ---
    def wrapper_generate_qr(ean):
        details = products.get_product_details(ean)
        return qr_gen.generate_qr(ean, details)

    def wrapper_update_stock(ean, exp_date, qty, action):
        details = products.get_product_details(ean)
        name = details['name'] if details else "Unknown"
        return inventory.update_stock(ean, name, exp_date, qty, action)

    def wrapper_check_alerts():
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
            return gr.update(), gr.update(), ""
        print(".", end="", flush=True)
        ean, date, msg = scanner.scan_image(image)
        if ean:
            print(f"\n✅ FOUND: EAN={ean}, Date={date}, Msg={msg}")

        if ean and date:
            return ean, date, msg
        elif ean:
            return ean, gr.update(), msg
        else:
            return gr.update(), gr.update(), msg

    # --- THE FIX: Functions to Hide/Show Camera ---
    def stop_webcam():
        # This clears the image AND hides the component
        return gr.update(value=None, visible=False)

    def start_webcam():
        # This brings the component back
        return gr.update(visible=True)

    # --- Visual Layout ---
    with gr.Blocks(title="Modular Inventory System") as app:
        gr.Markdown("# 🏢 Store Inventory System")

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
                        product_df = gr.Dataframe(value=products.get_products_df(), interactive=False)

                btn_add.click(products.add_product, [add_ean, add_name, add_days], [msg_box, product_df])
                product_df.select(wrapper_table_select, [product_df], [msg_box, product_df])

            # TAB 2: QR GENERATOR
            with gr.TabItem("2. Print QR Labels"):
                qr_ean = gr.Textbox(label="Scan/Type EAN")
                btn_qr = gr.Button("Generate Label", variant="primary")
                out_img = gr.Image(label="Label")
                btn_qr.click(wrapper_generate_qr, [qr_ean], [out_img, gr.State()])

            # TAB 3: CASH REGISTER
            with gr.TabItem("3. Cash Register"):
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### 📷 Scan Item")

                        cam_input = gr.Image(sources=["webcam"], type="numpy", streaming=True)

                        with gr.Row():
                            btn_start_cam = gr.Button("▶️ Open Camera", variant="primary")
                            btn_stop_cam = gr.Button("❌ Stop Camera", variant="stop")

                        reg_ean = gr.Textbox(label="EAN")
                        reg_date = gr.Textbox(label="Exp Date")
                        reg_qty = gr.Number(label="Qty", value=1)
                        btn_in = gr.Button("Stock IN (+)")
                        reg_log = gr.Textbox(label="Log")

                    with gr.Column():
                        reg_table = gr.Dataframe(value=inventory.get_inventory_df())

                # --- WIRING FOR TAB 3 ---
                cam_input.change(wrapper_scan, inputs=[cam_input], outputs=[reg_ean, reg_date, reg_log])

                # These buttons hide and show the camera feed
                btn_stop_cam.click(fn=stop_webcam, outputs=cam_input)
                btn_start_cam.click(fn=start_webcam, outputs=cam_input)

                btn_in.click(wrapper_update_stock, [reg_ean, reg_date, reg_qty, gr.State("Add")], [reg_log, reg_table])

            # TAB 4: ALERTS
            with gr.TabItem("4. Alerts"):
                btn_alert = gr.Button("Check Expirations")
                alert_tbl = gr.Dataframe()
                btn_alert.click(wrapper_check_alerts, None, [gr.State(), alert_tbl])

    return app