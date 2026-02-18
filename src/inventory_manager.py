import pandas as pd


class InventoryManager:
    def __init__(self):
        # Inventory: [{'ean': '12345', 'exp_date': '2023-12-01', 'qty': 10}]
        self.inventory = []

    def update_stock(self, ean, name, exp_date, qty, action):
        ean = str(ean).strip()

        # Validation
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

        return f"✅ {action}: {name}", self.get_inventory_df()

    def get_inventory_df(self):
        if not self.inventory:
            return pd.DataFrame(columns=["EAN", "Name", "Exp Date", "Qty"])
        return pd.DataFrame(self.inventory)

    def get_raw_inventory(self):
        return self.inventory