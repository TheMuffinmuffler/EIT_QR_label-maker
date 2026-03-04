import pandas as pd
from datetime import datetime, timedelta


class AlertSystem:
    def check_alerts(self, inventory_list, opened_list=None):
        if opened_list is None:
            opened_list = []
            
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
                
        for item in opened_list:
            res = process_item(item, "Opened")
            if res: alerts.append(res)

        if not alerts:
            return "No alerts.", pd.DataFrame(columns=['EAN', 'Name', 'Exp Date', 'Qty', 'Status'])

        msg = f"{expired_count} expired, {soon_count} expiring soon."
        return msg, pd.DataFrame(alerts)