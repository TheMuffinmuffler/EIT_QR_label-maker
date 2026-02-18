from src.product_manager import ProductManager
from src.inventory_manager import InventoryManager
from src.qr_generator import QRGenerator
from src.alert_system import AlertSystem
from src.scanner import QRScanner  # Import the new module
from src.ui import create_app

# 1. Initialize Backend Systems
products = ProductManager()
inventory = InventoryManager()
qr_gen = QRGenerator()
alerts = AlertSystem()
scanner = QRScanner() # Initialize Scanner

# 2. Build the UI (Injecting scanner into it)
app = create_app(products, inventory, qr_gen, alerts, scanner)

# 3. Run
if __name__ == "__main__":
    app.launch()