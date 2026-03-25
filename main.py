from nicegui import ui
from src.product_manager import ProductManager
from src.inventory_manager import InventoryManager
from src.qr_generator import QRGenerator
from src.alert_system import AlertSystem
from src.scanner import QRScanner
from src.customer_manager import CustomerManager
from src.order_manager import OrderManager
from src.recipe_manager import RecipeManager
from src.ui import create_ui

# 1. Initialize Backend Systems
products = ProductManager()
inventory = InventoryManager()
internal_inventory = InventoryManager("data/inventory/internal_inventory.csv")
customers = CustomerManager()
orders = OrderManager()
recipes = RecipeManager()
qr_gen = QRGenerator()
alerts = AlertSystem()
scanner = QRScanner()

# 2. Build the UI
create_ui(products, inventory, internal_inventory, customers, orders, recipes, qr_gen, alerts, scanner)

# 3. Run
if __name__ in {"__main__", "__mp_main__", "builtins"}:
    ui.run(title="Modular Inventory System - NiceGUI", port=8080)
