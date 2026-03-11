import pandas as pd
import os


class ProductManager:
    def __init__(self):
        # Path to the CSV file
        self.file_path = "data/inventory/products.csv"
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
                        'shelf_life': int(row['Shelf Life']),
                        'url': str(row.get('URL', '')),
                        'price_in': float(row.get('Price In', 0.0)),
                        'price_out': float(row.get('Price Out', 0.0))
                    }
                print(f"Loaded {len(self.products)} products from {self.file_path}")
            except Exception as e:
                print(f"Error loading products: {e}")

    def save_data(self):
        """Saves current products to CSV."""
        data = []
        for ean, details in self.products.items():
            data.append({
                "EAN": ean,
                "Name": details['name'],
                "Shelf Life": details['shelf_life'],
                "URL": details.get('url', ''),
                "Price In": details.get('price_in', 0.0),
                "Price Out": details.get('price_out', 0.0)
            })

        df = pd.DataFrame(data, columns=["EAN", "Name", "Shelf Life", "URL", "Price In", "Price Out"])
        df = df.sort_values(by="EAN", key=lambda x: pd.to_numeric(x, errors='coerce'))
        # Create directory if it doesn't exist just in case
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        df.to_csv(self.file_path, index=False)

    def add_product(self, ean, name, shelf_life, url="", price_in=0.0, price_out=0.0):
        ean = str(ean).strip()
        if not ean or not name:
            return "Error: EAN and Name are required.", self.get_products_df()

        if ean in self.products:
            return f"Error: EAN '{ean}' already exists.", self.get_products_df()

        self.products[ean] = {
            'name': name,
            'shelf_life': int(shelf_life),
            'url': url.strip(),
            'price_in': float(price_in),
            'price_out': float(price_out)
        }

        self.save_data()  # <--- Auto Save
        return f"Saved: {name} (EAN: {ean})", self.get_products_df()

    def update_product(self, ean, name, shelf_life, url="", price_in=0.0, price_out=0.0):
        ean = str(ean).strip()
        if ean in self.products:
            self.products[ean] = {
                'name': name,
                'shelf_life': int(shelf_life),
                'url': url.strip(),
                'price_in': float(price_in),
                'price_out': float(price_out)
            }
            self.save_data()
            return f"Updated: {name} (EAN: {ean})", self.get_products_df()
        return f"Error: EAN '{ean}' not found.", self.get_products_df()

    def delete_product(self, ean):
        ean = str(ean).strip()
        if ean in self.products:
            name = self.products[ean]['name']
            del self.products[ean]
            self.save_data()  # <--- Auto Save
            return f"Deleted: {name} (EAN: {ean})", self.get_products_df()
        return f"Error: EAN '{ean}' not found.", self.get_products_df()

    def get_product_details(self, ean):
        return self.products.get(str(ean).strip())

    def get_products_df(self):
        if not self.products:
            return pd.DataFrame(columns=["EAN", "Name", "Shelf Life", "URL", "Price In", "Price Out", "ACTIONS"])

        data = []
        for ean, details in self.products.items():
            data.append({
                "EAN": ean,
                "Name": details['name'],
                "Shelf Life": details['shelf_life'],
                "URL": details.get('url', ''),
                "Price In": details.get('price_in', 0.0),
                "Price Out": details.get('price_out', 0.0),
                "ACTIONS": ""
            })
        df = pd.DataFrame(data)
        return df.sort_values(by="EAN", key=lambda x: pd.to_numeric(x, errors='coerce'))
