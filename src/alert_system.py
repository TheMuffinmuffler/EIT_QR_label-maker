import pandas as pd
from datetime import datetime, timedelta


class AlertSystem:
    def check_alerts(self, inventory_list):
        target = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        expiring = [item for item in inventory_list if item['exp_date'] == target]

        if not expiring:
            return "No alerts.", pd.DataFrame()

        return f"⚠️ {len(expiring)} batches expiring!", pd.DataFrame(expiring)