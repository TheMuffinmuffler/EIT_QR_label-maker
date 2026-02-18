import pandas as pd
import os


class InventoryManager:
    def __init__(self):
        self.file_path = "data/inventory.csv"
        # Inventory: [{'ean': '12345', 'exp_date': '2023-12-01', 'qty': 10}]
        self.inventory = []
        self.load_data()

    def load_data(self):
        """Loads inventory from CSV on startup."""
        if os.path.exists(self.file_path):
            try:
                df = pd.read_csv(self.file_path, dtype={'ean': str})
                # Convert DataFrame back to list of dicts
                self.inventory = df.to_dict('records')
                print(f"✅ Loaded {len(self.inventory)} inventory batches from {self.file_path}")
            except Exception as e:
                print(f"⚠️ Error loading inventory: {e}")

    def save_data(self):
        """Saves current inventory to CSV."""
        df = pd.DataFrame(self.inventory)
        if df.empty:
            # Ensure columns exist even if empty
            df = pd.DataFrame(columns=['ean', 'name', 'exp_date', 'qty'])

        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        df.to_csv(self.file_path, index=False)

    def update_stock(self, ean, name, exp_date, qty, action):
        ean = str(ean).strip()

        if not ean or not exp_date:
            return "Scan QR first", self.get_inventory_df()
        try:
            qty = int(qty)
            if qty <= 0: return "Qty must be > 0", self.get_inventory_df()
        except:
            return "Invalid Qty", self.get_inventory_df()

        # Find specific batch
        found = False
        for batch in self.inventory:
            if batch['ean'] == ean and batch['exp_date'] == exp_date:
                if "Add" in action:
                    batch['qty'] += qty
                else:
                    if batch['qty'] < qty:
                        return "❌ Not enough stock!", self.get_inventory_df()
                    batch['qty'] -= qty
                    if batch['qty'] == 0:
                        self.inventory.remove(batch)
                found = True
                break

        if not found:
            if "Remove" in action:
                return "❌ Batch not found.", self.get_inventory_df()
            else:
                self.inventory.append({
                    'ean': ean,
                    'name': name,
                    'exp_date': exp_date,
                    'qty': qty
                })

        self.save_data()  # <--- Auto Save
        return f"✅ {action}: {name}", self.get_inventory_df()

    def get_inventory_df(self):
        if not self.inventory:
            return pd.DataFrame(columns=["EAN", "Name", "Exp Date", "Qty"])
        # Capitalize headers for display
        df = pd.DataFrame(self.inventory)
        return df.rename(columns={"ean": "EAN", "name": "Name", "exp_date": "Exp Date", "qty": "Qty"})

    def get_raw_inventory(self):
        return self.inventory