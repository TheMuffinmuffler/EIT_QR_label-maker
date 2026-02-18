from pyzbar.pyzbar import decode
import numpy as np


class QRScanner:
    def scan_image(self, image_array):
        """
        Scans a numpy array (image) for QR codes using pyzbar.
        Returns: EAN, Date, Status Message
        """
        if image_array is None:
            return None, None, "❌ No image provided"

        try:
            # Pyzbar detects all codes in the image
            decoded_objects = decode(image_array)

            if not decoded_objects:
                return None, None, "⚠️ No QR code found. Try moving closer."

            # Loop through detected codes (usually just one)
            for obj in decoded_objects:
                data = obj.data.decode("utf-8")

                # Check for our specific format: "EAN,YYYY-MM-DD"
                if "," in data:
                    parts = data.split(',')
                    if len(parts) >= 2:
                        ean = parts[0].strip()
                        exp_date = parts[1].strip()
                        return ean, exp_date, f"✅ Scanned: {ean}"

                # If code is found but doesn't match our format
                return data, None, f"⚠️ Scanned '{data}' (Not a valid inventory label)"

            return None, None, "⚠️ No readable code found"

        except Exception as e:
            return None, None, f"❌ Error: {str(e)}"