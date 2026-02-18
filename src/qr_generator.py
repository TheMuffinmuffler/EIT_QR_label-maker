import qrcode
from datetime import datetime, timedelta


class QRGenerator:
    def generate_qr(self, ean, product_details):
        ean = str(ean).strip()

        if not product_details:
            return None, f"❌ Error: EAN '{ean}' unknown. Add to Product Setup first."

        name = product_details['name']
        shelf_life = product_details['shelf_life']

        # Calculate Expiration (Today + Shelf Life)
        today = datetime.now()
        exp_date = today + timedelta(days=shelf_life)
        exp_date_str = exp_date.strftime("%Y-%m-%d")

        # QR Content
        qr_content = f"{ean},{exp_date_str}"
        readable_text = f"Item: {name}\nEAN: {ean}\nExp: {exp_date_str} (+{shelf_life} days)"

        # Generate Image
        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(qr_content)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        return img.get_image(), readable_text