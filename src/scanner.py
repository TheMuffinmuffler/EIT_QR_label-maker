from pyzbar.pyzbar import decode
from PIL import Image, ImageOps
import numpy as np


class QRScanner:
    def scan_image(self, image_array):
        """
        Scans an image for QR codes and returns (EAN, Date, Status, Debug_Image).
        Includes thresholding to fix overexposure issues.
        """
        if image_array is None:
            return None, None, "❌ No image provided", None

        try:
            # 1. Normalize image data
            if image_array.dtype != np.uint8:
                if image_array.max() <= 1.0:
                    image_array = (image_array * 255).astype(np.uint8)
                else:
                    image_array = image_array.astype(np.uint8)

            # 2. Convert to Grayscale and enhance contrast
            # Bright phone screens (from your screenshot) often need high contrast to be readable
            img = Image.fromarray(image_array).convert('L')
            img = ImageOps.autocontrast(img)

            # 3. Apply Hard Thresholding (The Visual Debugger Image)
            # This turns every pixel either purely black or purely white
            img_thresh = img.point(lambda p: 255 if p > 128 else 0)
            debug_view = np.array(img_thresh)

            # 4. Detect on both normal and thresholded versions
            decoded_objects = decode(img) or decode(img_thresh)

            if not decoded_objects:
                return None, None, "⚠️ Scanning... (Reduce glare if lines look broken in debugger)", debug_view

            # 5. Process Results
            for obj in decoded_objects:
                data = obj.data.decode("utf-8")
                print(f"--- DETECTED: {data} ---")

                if "," in data:
                    parts = data.split(',')
                    if len(parts) >= 2:
                        ean = parts[0].strip()
                        exp_date = parts[1].strip()
                        return ean, exp_date, f"✅ Scanned: {ean}", debug_view

                return data, None, f"⚠️ Scanned '{data}' (Invalid label format)", debug_view

            return None, None, "⚠️ No readable code found", debug_view

        except Exception as e:
            print(f"SCANNER ERROR: {e}")
            return None, None, f"❌ Scan Error: {str(e)}", None