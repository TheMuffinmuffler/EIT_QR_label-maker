import pandas as pd


class ProductManager:
    def __init__(self):
        # Database: {'12345': {'name': 'Milk', 'shelf_life': 7}}
        self.products = {}

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
        return f"✅ Saved: {name} (EAN: {ean})", self.get_products_df()

    def delete_product(self, ean):
        ean = str(ean).strip()
        if ean in self.products:
            name = self.products[ean]['name']
            del self.products[ean]
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