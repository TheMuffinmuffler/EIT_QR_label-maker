import gradio as gr


def create_app(products, inventory, qr_gen, alerts):
    """
    Constructs the Gradio interface.
    Receives the backend instances (products, inventory, etc.) as arguments.
    """

    # --- Wrapper Functions (Internal Logic for UI) ---
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
        # Check if user clicked the "DELETE" column (index 3)
        if col_index == 3:
            ean_to_remove = current_df.iloc[row_index]["EAN"]
            return products.delete_product(ean_to_remove)
        return "Click the ❌ column to delete.", products.get_products_df()

    # --- The Visual Layout ---
    with gr.Blocks(title="Modular Inventory System", theme=gr.themes.Soft()) as app:
        gr.Markdown("# 🏢 Store Inventory System")

        with gr.Tabs():
            # TAB 1: PRODUCT SETUP
            with gr.TabItem("1. Product Setup"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### ➕ Add Product")
                        add_ean = gr.Textbox(label="EAN Code", placeholder="e.g. 12345")
                        add_name = gr.Textbox(label="Name", placeholder="e.g. Milk")
                        add_days = gr.Number(label="Shelf Life (Days)", value=7)
                        btn_add = gr.Button("Save Product", variant="primary")

                        gr.Markdown("---")
                        gr.Markdown("### 🗑️ Remove Product (Manual)")
                        del_ean_input = gr.Textbox(label="Enter EAN to Remove")
                        btn_manual_del = gr.Button("Remove Item", variant="stop")

                        msg_box = gr.Textbox(label="System Log")

                    with gr.Column(scale=2):
                        gr.Markdown("### 📦 Product Database")
                        product_df = gr.Dataframe(
                            value=products.get_products_df(),
                            interactive=False,
                            headers=["EAN", "Name", "Shelf Life", "DELETE"]
                        )

                # Wiring Tab 1
                btn_add.click(products.add_product, [add_ean, add_name, add_days], [msg_box, product_df])
                btn_manual_del.click(products.delete_product, [del_ean_input], [msg_box, product_df])
                product_df.select(wrapper_table_select, [product_df], [msg_box, product_df])

            # TAB 2: QR GENERATOR
            with gr.TabItem("2. Print QR Labels"):
                gr.Markdown("### QR Generator")
                with gr.Row():
                    qr_ean = gr.Textbox(label="Scan/Type EAN")
                    btn_qr = gr.Button("Generate Label", variant="primary")
                with gr.Row():
                    out_img = gr.Image(label="Label")
                    out_txt = gr.Textbox(label="Info")

                btn_qr.click(wrapper_generate_qr, [qr_ean], [out_img, out_txt])

            # TAB 3: CASH REGISTER
            with gr.TabItem("3. Cash Register"):
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### Scan Item")
                        reg_ean = gr.Textbox(label="EAN")
                        reg_date = gr.Textbox(label="Exp Date (YYYY-MM-DD)")
                        reg_qty = gr.Number(label="Qty", value=1)
                        with gr.Row():
                            btn_in = gr.Button("Stock IN (+)", variant="primary")
                            btn_out = gr.Button("Stock OUT (-)", variant="stop")
                        reg_log = gr.Textbox(label="Log")
                    with gr.Column():
                        gr.Markdown("### Inventory")
                        reg_table = gr.Dataframe(value=inventory.get_inventory_df())

                btn_in.click(wrapper_update_stock, [reg_ean, reg_date, reg_qty, gr.State("Add")], [reg_log, reg_table])
                btn_out.click(wrapper_update_stock, [reg_ean, reg_date, reg_qty, gr.State("Remove")],
                              [reg_log, reg_table])

            # TAB 4: ALERTS
            with gr.TabItem("4. Alerts"):
                btn_alert = gr.Button("Check Expirations (Tomorrow)")
                alert_msg = gr.Textbox()
                alert_tbl = gr.Dataframe()
                btn_alert.click(wrapper_check_alerts, None, [alert_msg, alert_tbl])

    return app