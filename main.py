import gradio as gr  # Added this to access themes
from src.product_manager import ProductManager
from src.inventory_manager import InventoryManager
from src.qr_generator import QRGenerator
from src.alert_system import AlertSystem
from src.scanner import QRScanner
from src.ui import create_app

# 1. Initialize Backend Systems
products = ProductManager()
inventory = InventoryManager()
qr_gen = QRGenerator()
alerts = AlertSystem()
scanner = QRScanner()

# 2. Build the UI
app = create_app(products, inventory, qr_gen, alerts, scanner)

# 3. Run
if __name__ == "__main__":
    # The theme is moved here to satisfy the Gradio 6.0 requirement
    app.launch(theme=gr.themes.Soft())