import gradio as gr
import numpy as np


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
            return gr.update(), gr.update(), "🔴 Camera active but no frames received", gr.update()

        # Log that we received a frame
        frame_info = f"📸 Frame received: {image.shape if hasattr(image, 'shape') else 'unknown shape'}"
        
        ean, date, msg, debug_img = scanner.scan_image(image)
        
        # Combine status message with frame info for debugging
        status = f"{msg} | {frame_info}"

        return (
            ean if ean else gr.update(),
            date if date else gr.update(),
            status,
            debug_img if debug_img is not None else gr.update()
        )

    # --- MAIN UI STRUCTURE ---
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
                out_info = gr.Textbox(label="Label Details & Save Path")
                btn_qr.click(wrapper_generate_qr, [qr_ean], [out_img, out_info])

            # TAB 3: CASH REGISTER
            with gr.TabItem("3. Cash Register"):
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### 📷 Live Scanner")
                        # streaming=False often works better for manual capture
                        cam_input = gr.Image(sources=["webcam"], type="numpy", label="Webcam Feed")
                        file_input = gr.Image(sources=["upload"], type="numpy", label="Or Upload QR Image")
                        debug_view = gr.Image(label="Scanner View (B&W Debugger)", interactive=False)

                        reg_ean = gr.Textbox(label="EAN")
                        reg_date = gr.Textbox(label="Exp Date")
                        reg_qty = gr.Number(label="Qty", value=1)
                        btn_in = gr.Button("Stock IN (+)", variant="primary")
                        reg_log = gr.Textbox(label="Scanner Status Log", value="Ready...")
                        btn_scan = gr.Button("📸 Scan Webcam Snapshot", variant="primary")

                    with gr.Column():
                        reg_table = gr.Dataframe(value=inventory.get_inventory_df())

                # Manual Scan button for Webcam
                btn_scan.click(
                    wrapper_scan,
                    inputs=[cam_input],
                    outputs=[reg_ean, reg_date, reg_log, debug_view]
                )

                # Automatic scan on file upload
                file_input.change(
                    wrapper_scan,
                    inputs=[file_input],
                    outputs=[reg_ean, reg_date, reg_log, debug_view]
                )

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
                btn_alert.click(wrapper_check_alerts, None, [alert_msg, alert_tbl])

    return app