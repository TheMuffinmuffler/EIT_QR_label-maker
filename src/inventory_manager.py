import pandas as pd
import os
from datetime import datetime


class InventoryManager:
    def __init__(self):
        self.file_path = "data/inventory/inventory.csv"
        # Inventory: [{'ean': '12345', 'exp_date': '2023-12-01', 'qty': 10}]
        self.inventory = []
        self.load_data()

    def load_data(self):
        """Loads inventory from CSV on startup and converts dates if needed."""
        if os.path.exists(self.file_path):
            try:
                df = pd.read_csv(self.file_path, dtype={'ean': str})
                self.inventory = df.to_dict('records')
                
                # Auto-convert dates from YYYY-MM-DD to DD-MM-YYYY
                converted = False
                for item in self.inventory:
                    date_str = str(item['exp_date'])
                    if "-" in date_str and len(date_str.split('-')[0]) == 4:
                        try:
                            dt = datetime.strptime(date_str, "%Y-%m-%d")
                            item['exp_date'] = dt.strftime("%d-%m-%Y")
                            converted = True
                        except:
                            pass
                
                if converted:
                    print(f"Migrated inventory dates to DD-MM-YYYY")
                    self.save_data()
                    
                print(f"Loaded {len(self.inventory)} inventory batches from {self.file_path}")
            except Exception as e:
                print(f"Error loading inventory: {e}")

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
        exp_date = str(exp_date).strip() if exp_date else ""

        if not ean:
            return "No EAN provided", self.get_inventory_df()

        # If date is missing and we're removing, find the OLDEST batch (FIFO)
        if not exp_date and "Remove" in action:
            matches = [b for b in self.inventory if b['ean'] == ean]
            if not matches:
                return f"No stock found for {ean}", self.get_inventory_df()
            
            # Sort by actual date object
            matches.sort(key=lambda x: datetime.strptime(x['exp_date'], "%d-%m-%Y"))
            target_batch = matches[0]
            exp_date = target_batch['exp_date']
        
        if not exp_date and "Add" in action:
            return "Scan QR first (Date missing)", self.get_inventory_df()

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
                        return "Not enough stock!", self.get_inventory_df()
                    batch['qty'] -= qty
                    if batch['qty'] <= 0:
                        self.inventory.remove(batch)
                found = True
                break

        if not found:
            if "Remove" in action:
                return f"Batch {exp_date} not found for {ean}", self.get_inventory_df()
            else:
                self.inventory.append({
                    'ean': ean,
                    'name': name,
                    'exp_date': exp_date,
                    'qty': qty
                })

        self.save_data()  # <--- Auto Save
        return f"{action}: {name} ({exp_date})", self.get_inventory_df()

    def get_inventory_df(self):
        if not self.inventory:
            return pd.DataFrame(columns=["EAN", "Name", "Exp Date", "Qty"])
        # Capitalize headers for display
        df = pd.DataFrame(self.inventory)
        return df.rename(columns={"ean": "EAN", "name": "Name", "exp_date": "Exp Date", "qty": "Qty"})

    def get_raw_inventory(self):
        return self.inventory