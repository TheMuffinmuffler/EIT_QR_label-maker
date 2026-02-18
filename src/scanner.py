from pyzbar.pyzbar import decode
from PIL import Image
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
            # 1. Normalize the image data
            # Ensure we have uint8 data (0-255) because pyzbar can fail on float arrays
            if image_array.dtype != np.uint8:
                # If data is 0-1 float, scale it
                if image_array.max() <= 1.0:
                    image_array = (image_array * 255).astype(np.uint8)
                else:
                    image_array = image_array.astype(np.uint8)

            # 2. Convert to Grayscale using PIL
            # Pyzbar performs significantly better on grayscale (L-mode) images
            img = Image.fromarray(image_array)
            img_gray = img.convert('L')

            # 3. Detect
            decoded_objects = decode(img_gray)

            # Fallback: If grayscale failed, try the original just in case
            if not decoded_objects:
                decoded_objects = decode(image_array)

            if not decoded_objects:
                return None, None, "⚠️ No QR code found. Hold steady/move closer."

            # 4. Process Results
            for obj in decoded_objects:
                data = obj.data.decode("utf-8")

                # --- DEBUGGER: PRINT TO TERMINAL ---
                print(f"--- CAMERA SAW: {data} ---")
                # -----------------------------------

                # Check for our specific format: "EAN,YYYY-MM-DD"
                if "," in data:
                    parts = data.split(',')
                    if len(parts) >= 2:
                        ean = parts[0].strip()
                        exp_date = parts[1].strip()
                        return ean, exp_date, f"✅ Scanned: {ean}"

                # If code is found but it's just a regular barcode (no date)
                return data, None, f"⚠️ Scanned '{data}' (Not a valid label)"

            return None, None, "⚠️ No readable code found"

        except Exception as e:
            # This catches issues like missing 'zbar' library
            print(f"SCANNER ERROR: {e}")
            return None, None, f"❌ Scan Error: {str(e)}"