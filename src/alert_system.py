import pandas as pd
from datetime import datetime, timedelta


class AlertSystem:
    def check_alerts(self, inventory_list, internal_list=None):
        if internal_list is None:
            internal_list = []
            
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        
        alerts = []
        expired_count = 0
        soon_count = 0
        
        def process_item(item, source_type):
            nonlocal expired_count, soon_count
            try:
                exp_date = datetime.strptime(item['exp_date'], "%d-%m-%Y").date()
                
                status_suffix = f" ({source_type})"
                if exp_date < today:
                    status = "EXPIRED" + status_suffix
                    expired_count += 1
                elif exp_date == today:
                    status = "Expiring TODAY" + status_suffix
                    soon_count += 1
                elif exp_date == tomorrow:
                    status = "Expiring Tomorrow" + status_suffix
                    soon_count += 1
                else:
                    return None
                    
                return {
                    'EAN': item['ean'],
                    'Name': item['name'],
                    'Exp Date': item['exp_date'],
                    'Qty': item.get('qty', 1),
                    'Status': status
                }
            except:
                return None

        for item in inventory_list:
            res = process_item(item, "In Stock")
            if res: alerts.append(res)
                
        for item in internal_list:
            res = process_item(item, "Ingredient")
            if res: alerts.append(res)

        if not alerts:
            return "No alerts.", pd.DataFrame(columns=['EAN', 'Name', 'Exp Date', 'Qty', 'Status'])

        df = pd.DataFrame(alerts)
        # Convert date strings to actual datetime objects for correct sorting
        df['temp_date'] = pd.to_datetime(df['Exp Date'], format='%d-%m-%Y')
        # Sort by Name (A-Z) and then temp_date (Soonest first)
        df = df.sort_values(by=['Name', 'temp_date'])
        # Remove temp column
        df = df.drop(columns=['temp_date'])

        msg = f"{expired_count} expired, {soon_count} expiring soon."
        return msg, df