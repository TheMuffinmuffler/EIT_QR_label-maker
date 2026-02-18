import pandas as pd
import os


class ProductManager:
    def __init__(self):
        # Path to the CSV file
        self.file_path = "data/products.csv"
        # Database: {'12345': {'name': 'Milk', 'shelf_life': 7}}
        self.products = {}
        self.load_data()

    def load_data(self):
        """Loads products from CSV on startup."""
        if os.path.exists(self.file_path):
            try:
                # dtype={'EAN': str} ensures EANs like "00123" don't lose leading zeros
                df = pd.read_csv(self.file_path, dtype={'EAN': str})
                for _, row in df.iterrows():
                    self.products[str(row['EAN'])] = {
                        'name': row['Name'],
                        'shelf_life': int(row['Shelf Life'])
                    }
                print(f"✅ Loaded {len(self.products)} products from {self.file_path}")
            except Exception as e:
                print(f"⚠️ Error loading products: {e}")

    def save_data(self):
        """Saves current products to CSV."""
        data = []
        for ean, details in self.products.items():
            data.append({
                "EAN": ean,
                "Name": details['name'],
                "Shelf Life": details['shelf_life']
            })

        df = pd.DataFrame(data, columns=["EAN", "Name", "Shelf Life"])
        # Create directory if it doesn't exist just in case
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        df.to_csv(self.file_path, index=False)

    def add_product(self, ean, name, shelf_life):
        ean = str(ean).strip()
        if not ean or not name:
            return "❌ Error: EAN and Name are required.", self.get_products_df()

        if ean in self.products:
            return f"❌ Error: EAN '{ean}' already exists.", self.get_products_df()

        self.products[ean] = {
            'name': name,
            'shelf_life': int(shelf_life)
        }

        self.save_data()  # <--- Auto Save
        return f"✅ Saved: {name} (EAN: {ean})", self.get_products_df()

    def delete_product(self, ean):
        ean = str(ean).strip()
        if ean in self.products:
            name = self.products[ean]['name']
            del self.products[ean]
            self.save_data()  # <--- Auto Save
            return f"🗑️ Deleted: {name} (EAN: {ean})", self.get_products_df()
        return f"❌ Error: EAN '{ean}' not found.", self.get_products_df()

    def get_product_details(self, ean):
        return self.products.get(str(ean).strip())

    def get_products_df(self):
        if not self.products:
            return pd.DataFrame(columns=["EAN", "Name", "Shelf Life", "DELETE"])

        data = []
        for ean, details in self.products.items():
            data.append({
                "EAN": ean,
                "Name": details['name'],
                "Shelf Life": details['shelf_life'],
                "DELETE": "❌"
            })
        return pd.DataFrame(data)