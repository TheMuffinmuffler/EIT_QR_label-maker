import cv2
from pyzbar.pyzbar import decode
from PIL import Image, ImageOps
import numpy as np


class QRScanner:
    def __init__(self):
        self.opencv_detector = cv2.QRCodeDetector()
        self.last_data = None
        self.blank_count = 0

    def scan_image(self, image_array):
        """
        Scans an image for QR codes and returns (EAN, Date, Status, Debug_Image).
        """
        if image_array is None:
            return None, None, "No image provided", None

        try:
            # 1. Ensure it's a numpy array and handle different types
            if not isinstance(image_array, np.ndarray):
                image_array = np.array(image_array)

            # 2. Normalize to uint8
            if image_array.dtype != np.uint8:
                if image_array.max() <= 1.0:
                    image_array = (image_array * 255).astype(np.uint8)
                else:
                    image_array = image_array.astype(np.uint8)

            # 3. Handle Alpha channel (4 channels) - Convert to RGB
            if len(image_array.shape) == 3 and image_array.shape[2] == 4:
                image_array = cv2.cvtColor(image_array, cv2.COLOR_RGBA2RGB)

            original_img = Image.fromarray(image_array)

            # Step 1: Try pyzbar (raw image)
            decoded_objects = decode(original_img)
            debug_view = image_array

            # Step 2: Try pyzbar (contrast enhancement)
            if not decoded_objects:
                gray_img = original_img.convert('L')
                enhanced_img = ImageOps.autocontrast(gray_img)
                decoded_objects = decode(enhanced_img)
                if decoded_objects:
                    debug_view = np.array(enhanced_img)

            # Step 3: Try OpenCV Fallback
            if not decoded_objects:
                # OpenCV likes BGR
                bgr_img = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
                data, points, _ = self.opencv_detector.detectAndDecode(bgr_img)
                if data:
                    # Process OpenCV result with "once" logic
                    if data == self.last_data:
                        return None, None, "Same item detected", image_array
                    self.last_data = data
                    self.blank_count = 0
                    return self._process_data(data, image_array)

            if not decoded_objects:
                self.blank_count += 1
                if self.blank_count > 10:  # Need 10 blank frames to reset
                    self.last_data = None
                return None, None, "Scanning... Keep steady", debug_view

            # Process pyzbar results with "once" logic
            self.blank_count = 0
            for obj in decoded_objects:
                data = obj.data.decode("utf-8")
                code_type = obj.type  # e.g., 'QRCODE', 'EAN13', 'I25'
                
                if data == self.last_data:
                    return None, None, f"Same {code_type} detected", debug_view
                
                self.last_data = data
                return self._process_data(data, debug_view, code_type)

            return None, None, "No readable code found", debug_view

        except Exception as e:
            print(f"DEBUG: Scan Error: {str(e)}")
            return None, None, f"Scan Error: {str(e)}", None

    def _process_data(self, data, debug_view, code_type="CODE"):
        """Helper to parse the CSV format in the QR code or handle raw barcodes"""
        if "," in data:
            parts = data.split(',')
            if len(parts) >= 2:
                return parts[0].strip(), parts[1].strip(), f"Scanned QR ({parts[0].strip()})", debug_view
        
        # If no comma, it's likely a standard barcode (EAN-13, etc)
        return data, None, f"Scanned {code_type}: {data}", debug_view