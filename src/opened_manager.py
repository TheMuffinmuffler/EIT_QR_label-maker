import pandas as pd
import os
from datetime import datetime, timedelta

class OpenedManager:
    def __init__(self, product_manager, inventory_manager):
        self.file_path = "data/opened.csv"
        self.product_manager = product_manager
        self.inventory_manager = inventory_manager
        self.opened_list = []
        self.load_data()

    def load_data(self):
        """Loads opened products from CSV."""
        if os.path.exists(self.file_path):
            try:
                df = pd.read_csv(self.file_path, dtype={'ean': str})
                self.opened_list = df.to_dict('records')
            except Exception as e:
                print(f"Error loading opened products: {e}")

    def save_data(self):
        """Saves current opened products to CSV."""
        df = pd.DataFrame(self.opened_list)
        if df.empty:
            df = pd.DataFrame(columns=['ean', 'name', 'open_date', 'exp_date'])
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        df.to_csv(self.file_path, index=False)

    def open_product(self, ean, original_exp_date_str):
        """
        Strict workflow:
        1. Find and remove 1 unit from inventory.csv
        2. If successful, add to opened.csv with new expiration.
        """
        ean = str(ean).strip()
        original_exp_date_str = str(original_exp_date_str).strip() if original_exp_date_str else ""
        
        if not ean:
            return "Error: No EAN provided.", self.get_opened_df(), self.inventory_manager.get_inventory_df()
            
        details = self.product_manager.get_product_details(ean)
        name = details['name'] if details else "Unknown Product"

        # 1. Attempt removal from inventory
        inv_msg, inv_df = self.inventory_manager.update_stock(ean, name, original_exp_date_str, 1, "Remove")
        
        # Check if removal was successful
        # update_stock returns "Remove: Name" on success, or error messages
        if "Remove:" not in inv_msg:
            return f"Failed to open: {inv_msg}", self.get_opened_df(), inv_df

        # 2. If we reach here, inventory removal was successful. Add to opened list.
        shelf_life_opened = details.get('shelf_life_opened', 3) if details else 3

        today = datetime.now()
        open_date_str = today.strftime("%Y-%m-%d")
        
        # New expiration is today + shelf life after opening
        new_exp_date = today + timedelta(days=shelf_life_opened)
        
        # If the original expiration is sooner, use that
        if original_exp_date_str:
            try:
                orig_exp = datetime.strptime(original_exp_date_str, "%Y-%m-%d")
                if orig_exp < new_exp_date:
                    new_exp_date = orig_exp
            except Exception as e:
                print(f"Date parsing error: {e}")

        new_exp_date_str = new_exp_date.strftime("%Y-%m-%d")

        self.opened_list.append({
            'ean': ean,
            'name': name,
            'open_date': open_date_str,
            'exp_date': new_exp_date_str
        })

        self.save_data()
        return f"Success: {name} removed from inventory and added to opened list.", self.get_opened_df(), inv_df

    def remove_opened(self, index):
        """Removes an item from the opened list by index."""
        try:
            if 0 <= index < len(self.opened_list):
                item = self.opened_list.pop(index)
                self.save_data()
                return f"Removed {item['name']} from opened list.", self.get_opened_df()
        except:
            pass
        return "Error removing item.", self.get_opened_df()

    def get_opened_df(self):
        if not self.opened_list:
            return pd.DataFrame(columns=["EAN", "Name", "Opened Date", "New Exp Date", "REMOVE"])
        
        data = []
        for i, item in enumerate(self.opened_list):
            data.append({
                "EAN": item['ean'],
                "Name": item['name'],
                "Opened Date": item['open_date'],
                "New Exp Date": item['exp_date'],
                "REMOVE": "[X]"
            })
        return pd.DataFrame(data)
