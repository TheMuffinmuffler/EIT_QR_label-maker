import qrcode
import os
from datetime import datetime, timedelta
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm

class QRGenerator:
    def __init__(self):
        # Path to folders for saving labels and PDFs
        self.output_dir = "data/qrcodes"
        self.pdf_dir = "data/pdfs"
        self.qr_limit = 5
        self.pdf_limit = 10
        for d in [self.output_dir, self.pdf_dir]:
            if not os.path.exists(d):
                os.makedirs(d)

    def _cleanup_old_files(self, directory, limit):
        """Removes the oldest files in the directory if the count exceeds the limit."""
        try:
            # Get list of files in directory with full paths
            files = [os.path.join(directory, f) for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
            # Sort files by modification time (oldest first)
            files.sort(key=os.path.getmtime)
            
            # Deletion logic
            if len(files) > limit:
                files_to_delete = files[:len(files) - limit]
                for f in files_to_delete:
                    os.remove(f)
                    print(f"Cleaned up old file: {f}")
        except Exception as e:
            print(f"Error during file cleanup: {e}")

    def generate_qr(self, ean, product_details, manual_exp_date=None):
        ean = str(ean).strip()

        if not product_details:
            return None, f"Error: EAN '{ean}' unknown. Add to Product Setup first."

        name = product_details['name']
        shelf_life = product_details['shelf_life']
        url = product_details.get('url', '')

        # Determine Expiration Date
        if manual_exp_date:
            exp_date_str = manual_exp_date
        else:
            today = datetime.now()
            exp_date = today + timedelta(days=shelf_life)
            exp_date_str = exp_date.strftime("%d-%m-%Y")

        # QR Content
        data_string = f"{ean},{exp_date_str}"
        if url:
            url = url.strip()
            if not url.startswith("http"):
                url = "https://" + url
            
            # Ensure URL format
            separator = "&data=" if "?" in url else "?data="
            qr_content = f"{url}{separator}{data_string}"
        else:
            qr_content = data_string

        readable_text = f"Item: {name}\nEAN: {ean}\nExp: {exp_date_str}"

        # Generate Image
        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(qr_content)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        # Save with Name and Date in filename
        clean_name = "".join([c for c in name if c.isalnum() or c in (' ', '_')]).rstrip().replace(' ', '_')
        filename = f"{ean}_{clean_name}_{exp_date_str}.png"
        filepath = os.path.join(self.output_dir, filename)
        img.save(filepath)

        # Cleanup old QR codes
        self._cleanup_old_files(self.output_dir, self.qr_limit)

        return img.get_image(), f"{readable_text}\n\nSaved to: {filepath}", filepath

    def generate_pdf(self, ean, product_details, exp_date_str, quantity, qr_image_path):
        """Generates a PDF sheet with the specified quantity of QR labels."""
        if not product_details:
            return None
        
        name = product_details['name']
        clean_name = "".join([c for c in name if c.isalnum() or c in (' ', '_')]).rstrip().replace(' ', '_')
        pdf_filename = f"Print_{ean}_{clean_name}_{exp_date_str}.pdf"
        pdf_path = os.path.join(self.pdf_dir, pdf_filename)
        
        c = canvas.Canvas(pdf_path, pagesize=A4)
        width, height = A4
        
        # Label size (roughly 5cm x 5cm)
        label_w = 5 * cm
        label_h = 5 * cm
        margin = 1 * cm
        
        x = margin
        y = height - margin - label_h
        
        for i in range(int(quantity)):
            # Draw QR Image
            c.drawImage(qr_image_path, x, y, width=label_w, height=label_h)
            
            # Draw Text Label identifying the item, EAN, and Expiration
            c.setFont("Helvetica", 7)
            c.drawCentredString(x + label_w/2, y - 10, f"{name}")
            c.drawCentredString(x + label_w/2, y - 20, f"EAN: {ean} | Exp: {exp_date_str}")
            
            # Move to next position
            x += label_w + 1*cm
            if x + label_w > width - margin:
                x = margin
                y -= label_h + 2.5*cm # extra space for two lines of text
                
            if y < margin:
                c.showPage() # New page
                x = margin
                y = height - margin - label_h

        c.save()

        # Cleanup old PDFs
        self._cleanup_old_files(self.pdf_dir, self.pdf_limit)

        return pdf_path
