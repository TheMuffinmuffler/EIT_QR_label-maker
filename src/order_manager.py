import pandas as pd
import os
from datetime import datetime
import json

class OrderManager:
    def __init__(self, orders_file="data/orders/orders.csv", items_file="data/orders/order_items.csv"):
        self.orders_file = orders_file
        self.items_file = items_file
        self.orders = []
        self.order_items = []
        self.load_data()

    def load_data(self):
        """Loads orders and items from CSV."""
        if os.path.exists(self.orders_file):
            try:
                df = pd.read_csv(self.orders_file)
                self.orders = df.to_dict('records')
                print(f"Loaded {len(self.orders)} orders from {self.orders_file}")
            except Exception as e:
                print(f"Error loading orders: {e}")

        if os.path.exists(self.items_file):
            try:
                df = pd.read_csv(self.items_file, dtype={'EAN': str})
                self.order_items = df.to_dict('records')
                print(f"Loaded {len(self.order_items)} order items from {self.items_file}")
            except Exception as e:
                print(f"Error loading order items: {e}")

    def save_data(self):
        """Saves orders and items to CSV."""
        os.makedirs(os.path.dirname(self.orders_file), exist_ok=True)
        
        df_orders = pd.DataFrame(self.orders)
        if df_orders.empty:
            df_orders = pd.DataFrame(columns=["Order ID", "Customer ID", "Customer Name", "Date", "Due Date", "Total", "Status"])
        df_orders.to_csv(self.orders_file, index=False)

        df_items = pd.DataFrame(self.order_items)
        if df_items.empty:
            df_items = pd.DataFrame(columns=["Order ID", "EAN", "Name", "Exp Date", "Qty", "Price"])
        df_items.to_csv(self.items_file, index=False)

    def _generate_order_id(self):
        if not self.orders:
            return "ORD-001"
        try:
            ids = []
            for order in self.orders:
                oid = order['Order ID']
                if oid.startswith('ORD-'):
                    num_part = oid.split('-')[1]
                    if num_part.isdigit():
                        ids.append(int(num_part))
            if not ids: return "ORD-001"
            next_num = max(ids) + 1
            return f"ORD-{next_num:03d}"
        except:
            return f"ORD-{len(self.orders) + 1:03d}"

    def create_order(self, customer_id, customer_name, items, due_date=""):
        """
        Creates a new order.
        items: List of dicts [{'EAN', 'Name', 'Exp Date', 'Qty', 'Price'}]
        """
        if not items:
            return None, "Error: No items in order."

        order_id = self._generate_order_id()
        date_str = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        
        total = 0.0
        for item in items:
            item_total = float(item['Price']) * float(item['Qty'])
            total += item_total
            self.order_items.append({
                "Order ID": order_id,
                "EAN": str(item['EAN']),
                "Name": item['Name'],
                "Exp Date": item.get('Exp Date', 'N/A'),
                "Qty": float(item['Qty']),
                "Price": float(item['Price'])
            })

        new_order = {
            "Order ID": order_id,
            "Customer ID": customer_id,
            "Customer Name": customer_name,
            "Date": date_str,
            "Due Date": due_date,
            "Total": round(total, 2),
            "Status": "Received"
        }
        self.orders.append(new_order)
        self.save_data()
        return order_id, f"Order {order_id} created for {customer_name}. Total: {total:.2f}"

    def update_order_status(self, order_id, new_status):
        for o in self.orders:
            if o['Order ID'] == order_id:
                o['Status'] = new_status
                self.save_data()
                return True
        return False

    def get_orders_df(self):
        if not self.orders:
            return pd.DataFrame(columns=["Order ID", "Customer Name", "Date", "Due Date", "Total", "Status", "Items", "ACTIONS"])
        
        df = pd.DataFrame(self.orders)
        # Ensure Status column exists for older data
        if 'Status' not in df.columns:
            df['Status'] = "Received"
            for o in self.orders:
                if 'Status' not in o:
                    o['Status'] = "Received"

        # Add Items summary
        item_summaries = []
        for order_id in df['Order ID']:
            items = [f"{it['Qty']}x {it['Name']}" for it in self.order_items if it['Order ID'] == order_id]
            item_summaries.append(", ".join(items))
        df['Items'] = item_summaries

        df['ACTIONS'] = ""
        # Sort by ID descending (newest first)
        return df.sort_values(by="Order ID", ascending=False)

    def get_order_items(self, order_id):
        return [item for item in self.order_items if item['Order ID'] == order_id]

    def delete_order(self, order_id):
        self.orders = [o for o in self.orders if o['Order ID'] != order_id]
        self.order_items = [i for i in self.order_items if i['Order ID'] != order_id]
        self.save_data()
        return f"Deleted Order: {order_id}"

    def update_order(self, order_id, items, due_date=None):
        """
        Updates an existing order with a new set of items and optionally a new due date.
        """
        # Find the order
        order_index = -1
        for i, o in enumerate(self.orders):
            if o['Order ID'] == order_id:
                order_index = i
                break
        
        if order_index == -1:
            return False, f"Error: Order {order_id} not found."

        # Update due date if provided
        if due_date is not None:
            self.orders[order_index]['Due Date'] = due_date

        # Remove old items
        self.order_items = [item for item in self.order_items if item['Order ID'] != order_id]

        # Add new items and calculate total
        total = 0.0
        for item in items:
            item_total = float(item['Price']) * float(item['Qty'])
            total += item_total
            self.order_items.append({
                "Order ID": order_id,
                "EAN": str(item['EAN']),
                "Name": item['Name'],
                "Exp Date": item.get('Exp Date', 'N/A'),
                "Qty": float(item['Qty']),
                "Price": float(item['Price'])
            })

        # Update order header
        self.orders[order_index]['Total'] = round(total, 2)
        
        self.save_data()
        return True, f"Order {order_id} updated successfully."
