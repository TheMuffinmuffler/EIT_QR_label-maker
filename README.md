# ShelfLife

A modular, web-based inventory management system built with **Python**, **NiceGUI**, and **OpenCV**. This system is designed for small stores or cafes to track product shelf life, generate custom QR labels, and manage stock using live camera scanning.

## 🚀 Key Features

-   **Product Database**: Manage products with custom shelf life.
-   **QR Label Generator**: Create custom QR codes containing EAN and Expiration Date.
-   **Printable PDFs**: Generate A4 PDF sheets with multiple labels for easy printing.
-   **Live Camera Scanner**: Use your webcam to scan QR codes and standard barcodes (EAN-13, etc.).
-   **FIFO Inventory Tracking**: Automatically removes the oldest stock first when specific expiration dates aren't scanned.
-   **Expiration Alerts**: Instant overview of expired and soon-to-expire items in main stock.
-   **Sales Mode**: A simple "basket" workflow to scan multiple items and complete sales in bulk.

## 🛠 Tech Stack

-   **Frontend**: [NiceGUI](https://nicegui.io/) (High-level UI framework based on Quasar/Vue)
-   **Backend**: Python 3.12+
-   **Data Storage**: CSV files (Pandas)
-   **Computer Vision**: OpenCV, PyZbar (QR/Barcode scanning)
-   **PDF Generation**: ReportLab
-   **QR Generation**: `qrcode` library

## 📁 Project Structure

```text
.
├── main.py                 # Application entry point
├── data/
│   ├── inventory/          # CSV "Database" files
│   │   ├── products.csv    # Master product list
│   │   └── inventory.csv   # Current stock levels
│   ├── qrcodes/            # Last 5 generated QR images
│   └── pdfs/               # Last 10 generated printable sheets
└── src/
    ├── ui.py               # NiceGUI Layout and UI logic
    ├── product_manager.py  # CRUD for product definitions
    ├── inventory_manager.py # Stock adjustment and FIFO logic
    ├── qr_generator.py     # QR and PDF generation + cleanup
    ├── scanner.py          # OpenCV/PyZbar scanning engine
    └── alert_system.py     # Expiration date checker
```

## ⚙️ Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/TheMuffinmuffler/EIT_QR_label-maker.git
    cd EIT_QR_label-maker
    ```

2.  **Install dependencies**:
    ```bash
    pip install nicegui pandas opencv-python pyzbar reportlab qrcode pillow
    ```
    *Note: On some systems (like macOS), you may need to install zbar via Homebrew: `brew install zbar`*

## 📖 How to Use

1.  **Start the app**:
    ```bash
    python main.py
    ```
    The UI will be available at `http://localhost:8080`.

2.  **Workflow**:
    -   **Step 1: Setup**: Add your products in the "Product Setup" tab.
    -   **Step 2: Print**: Go to "Print QR Labels", enter an EAN, and generate a printable PDF.
    -   **Step 3: Stock In**: In the "Inventory" tab, scan your printed labels using the webcam to add stock.
    -   **Step 4: Alerts**: Check the "Alerts" tab daily to identify items that need to be removed or sold quickly.
    -   **Step 5: Sales**: Use the "Sales" tab to scan items for customers and update inventory in bulk.

## 🧹 Automatic Cleanup
The system is designed to keep the workspace clean:
-   **QR Codes**: Only the last 5 generated QR images are kept in `data/qrcodes/`.
-   **PDFs**: Only the last 10 generated PDFs are kept in `data/pdfs/`.

## 📄 License
This project is for educational/internal use. See source files for specific logic.
