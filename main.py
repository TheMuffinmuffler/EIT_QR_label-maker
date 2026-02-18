from src.product_manager import ProductManager
from src.inventory_manager import InventoryManager
from src.qr_generator import QRGenerator
from src.alert_system import AlertSystem
from src.ui import create_app

# 1. Initialize Backend Systems
products = ProductManager()
inventory = InventoryManager()
qr_gen = QRGenerator()
alerts = AlertSystem()

# 2. Build the UI (Injecting the backend systems into it)
app = create_app(products, inventory, qr_gen, alerts)

# 3. Run
if __name__ == "__main__":
    app.launch()