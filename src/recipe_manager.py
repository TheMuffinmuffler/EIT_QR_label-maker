import pandas as pd
import os

class RecipeManager:
    def __init__(self, file_path="data/inventory/recipes.csv"):
        self.file_path = file_path
        self.recipes = [] # List of {'product_ean', 'ingredient_ean', 'qty'}
        self.load_data()

    def load_data(self):
        if os.path.exists(self.file_path):
            try:
                df = pd.read_csv(self.file_path, dtype={'product_ean': str, 'ingredient_ean': str})
                self.recipes = df.to_dict('records')
                print(f"Loaded {len(self.recipes)} recipe ingredients from {self.file_path}")
            except Exception as e:
                print(f"Error loading recipes: {e}")

    def save_data(self):
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        df = pd.DataFrame(self.recipes)
        if df.empty:
            df = pd.DataFrame(columns=['product_ean', 'ingredient_ean', 'qty'])
        df.to_csv(self.file_path, index=False)

    def add_ingredient_to_recipe(self, product_ean, ingredient_ean, qty):
        # Remove existing if any (to update)
        self.recipes = [r for r in self.recipes if not (r['product_ean'] == product_ean and r['ingredient_ean'] == ingredient_ean)]
        self.recipes.append({
            'product_ean': str(product_ean),
            'ingredient_ean': str(ingredient_ean),
            'qty': float(qty)
        })
        self.save_data()

    def remove_ingredient_from_recipe(self, product_ean, ingredient_ean):
        self.recipes = [r for r in self.recipes if not (r['product_ean'] == product_ean and r['ingredient_ean'] == ingredient_ean)]
        self.save_data()

    def get_recipe(self, product_ean):
        return [r for r in self.recipes if r['product_ean'] == str(product_ean)]

    def delete_recipe(self, product_ean):
        self.recipes = [r for r in self.recipes if r['product_ean'] != str(product_ean)]
        self.save_data()
