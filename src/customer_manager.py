import pandas as pd
import os

class CustomerManager:
    def __init__(self, file_path="data/customers/customers.csv"):
        self.file_path = file_path
        # Database: {'CUST-001': {'name': 'John Doe', ...}}
        self.customers = {}
        self.load_data()

    def load_data(self):
        """Loads customers from CSV on startup."""
        if os.path.exists(self.file_path):
            try:
                df = pd.read_csv(self.file_path, dtype={'Customer ID': str})
                for _, row in df.iterrows():
                    cid = str(row['Customer ID'])
                    self.customers[cid] = {
                        'name': str(row.get('Name', '')),
                        'company': str(row.get('Company Name', '')),
                        'org_nr': str(row.get('Org Number', '')),
                        'vat_nr': str(row.get('VAT Number', '')),
                        'phone': str(row.get('Phone', '')),
                        'email': str(row.get('Email', '')),
                        'address': str(row.get('Address', '')),
                        'website': str(row.get('Website', '')),
                        'notes': str(row.get('Notes', ''))
                    }
                print(f"Loaded {len(self.customers)} customers from {self.file_path}")
            except Exception as e:
                print(f"Error loading customers: {e}")

    def save_data(self):
        """Saves current customers to CSV."""
        data = []
        for cid, d in self.customers.items():
            data.append({
                "Customer ID": cid,
                "Name": d['name'],
                "Company Name": d['company'],
                "Org Number": d['org_nr'],
                "VAT Number": d['vat_nr'],
                "Phone": d['phone'],
                "Email": d['email'],
                "Address": d['address'],
                "Website": d['website'],
                "Notes": d['notes']
            })

        df = pd.DataFrame(data, columns=["Customer ID", "Name", "Company Name", "Org Number", "VAT Number", "Phone", "Email", "Address", "Website", "Notes"])
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        df.to_csv(self.file_path, index=False)

    def _generate_next_id(self):
        if not self.customers:
            return "CUST-001"
        try:
            ids = []
            for cid in self.customers.keys():
                if cid.startswith('CUST-'):
                    num_part = cid.split('-')[1]
                    if num_part.isdigit():
                        ids.append(int(num_part))
            if not ids: return "CUST-001"
            next_num = max(ids) + 1
            return f"CUST-{next_num:03d}"
        except:
            return f"CUST-{len(self.customers) + 1:03d}"

    def add_customer(self, name, company="", org_nr="", vat_nr="", phone="", email="", address="", website="", notes=""):
        name = str(name).strip()
        if not name and not company:
            return "Error: Name or Company is required.", self.get_customers_df()

        cid = self._generate_next_id()
        self.customers[cid] = {
            'name': name,
            'company': str(company).strip(),
            'org_nr': str(org_nr).strip(),
            'vat_nr': str(vat_nr).strip(),
            'phone': str(phone).strip(),
            'email': str(email).strip(),
            'address': str(address).strip(),
            'website': str(website).strip(),
            'notes': str(notes).strip()
        }

        self.save_data()
        return f"Saved: {name if name else company} (ID: {cid})", self.get_customers_df()

    def update_customer(self, cid, name, company="", org_nr="", vat_nr="", phone="", email="", address="", website="", notes=""):
        cid = str(cid).strip()
        if cid in self.customers:
            self.customers[cid] = {
                'name': str(name).strip(),
                'company': str(company).strip(),
                'org_nr': str(org_nr).strip(),
                'vat_nr': str(vat_nr).strip(),
                'phone': str(phone).strip(),
                'email': str(email).strip(),
                'address': str(address).strip(),
                'website': str(website).strip(),
                'notes': str(notes).strip()
            }
            self.save_data()
            return f"Updated: {cid}", self.get_customers_df()
        return f"Error: Customer ID '{cid}' not found.", self.get_customers_df()

    def delete_customer(self, cid):
        cid = str(cid).strip()
        if cid in self.customers:
            del self.customers[cid]
            self.save_data()
            return f"Deleted: {cid}", self.get_customers_df()
        return f"Error: Customer ID '{cid}' not found.", self.get_customers_df()

    def get_customer_details(self, cid):
        return self.customers.get(str(cid).strip())

    def get_customers_df(self):
        if not self.customers:
            return pd.DataFrame(columns=["Customer ID", "Name", "Company Name", "Org Number", "Phone", "Email", "ACTIONS"])

        data = []
        for cid, d in self.customers.items():
            data.append({
                "Customer ID": cid,
                "Name": d['name'],
                "Company Name": d['company'],
                "Org Number": d['org_nr'],
                "Phone": d['phone'],
                "Email": d['email'],
                "ACTIONS": ""
            })
        df = pd.DataFrame(data)
        return df.sort_values(by="Customer ID")
