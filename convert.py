import csv
import decimal
import sys
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QWidget,
    QGridLayout,
)

HDR_FIELDS = [
    "record_code",
    "sender_id",
    "receiver_id",
    "creation_date",
    "creation_time",
    "file_id",
    "version",
    "physical_record_length",
]

GRP_FIELDS = [
    "record_code",
    "file_id",
    "group_id",
    "creation_date",
    "creation_time",
    "currency",
]

ACC_FIELDS = [
    "record_code",
    "account_number",
    "currency",
    "type_code_summary",
]

TXN_FIELDS = [
    "record_code",
    "type_code",
    "amount",
    "funds_type",
    "bank_ref",
    "customer_ref",
    "text",
]


def parse_bai2(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            if raw.endswith("/"):
                raw = raw[:-1]
            parts = raw.split(",")
            code = parts[0]
            if code == "01":
                yield dict(zip(HDR_FIELDS, parts[: len(HDR_FIELDS)]))
            elif code == "02":
                yield dict(zip(GRP_FIELDS, parts[: len(GRP_FIELDS)]))
            elif code == "03":
                yield dict(zip(ACC_FIELDS, parts[: len(ACC_FIELDS)]))
            elif code == "16":
                parts += [""] * (len(TXN_FIELDS) - len(parts))
                out = dict(zip(TXN_FIELDS, parts[: len(TXN_FIELDS)]))
                amt = out["amount"]
                if "." not in amt:
                    amt = decimal.Decimal(amt) / decimal.Decimal(100)
                else:
                    amt = decimal.Decimal(amt)
                out["amount"] = f"{amt:.2f}"
                yield out
            else:
                continue


def write_csv(rows, columns, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=columns)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in columns})

class BAI2ConverterGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BAI2 → CSV Converter")
        self.setMinimumSize(620, 400)
        self._build_ui()
        self._apply_dark_theme()

    def _build_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QGridLayout(central)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setVerticalSpacing(12)

        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("Choose a .bai2 file …")
        file_btn = QPushButton("Browse…")
        file_btn.clicked.connect(self.pick_file)
        layout.addWidget(QLabel("BAI2 File:"), 0, 0)
        layout.addWidget(self.file_edit, 0, 1)
        layout.addWidget(file_btn, 0, 2)

        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("Destination folder for CSVs …")
        out_btn = QPushButton("Browse…")
        out_btn.clicked.connect(self.pick_outdir)
        layout.addWidget(QLabel("Output Folder:"), 1, 0)
        layout.addWidget(self.out_edit, 1, 1)
        layout.addWidget(out_btn, 1, 2)

        convert_btn = QPushButton("Convert ➜ CSV")
        convert_btn.clicked.connect(self.convert)
        convert_btn.setFixedHeight(38)
        layout.addWidget(convert_btn, 2, 0, 1, 3)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Logs will appear here …")
        layout.addWidget(self.log, 3, 0, 1, 3)

        layout.setRowStretch(3, 1)

    def _apply_dark_theme(self):
        dark_qss = """
        *                                  { color: #E0E0E0; font-family: \'Segoe UI\', sans-serif; }
        QWidget                           { background-color: #121212; }
        QLineEdit, QTextEdit              { background-color: #1E1E1E; border: 1px solid #333; border-radius: 6px; padding: 4px; }
        QPushButton                       { background-color: #2E2E2E; border: 1px solid #444; border-radius: 6px; padding: 6px 10px; }
        QPushButton:hover                 { background-color: #3A3A3A; }
        QPushButton:pressed               { background-color: #2B2B2B; }
        QLabel                            { font-weight: 500; }
        """
        self.setStyleSheet(dark_qss)

    def append_log(self, line: str):
        self.log.append(line)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def pick_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select BAI2 File", "", "BAI2 Files (*.bai2 *.txt);;All Files (*)")
        if path:
            self.file_edit.setText(path)
            if not self.out_edit.text():
                self.out_edit.setText(str(Path(path).with_suffix("").parent / Path(path).stem))

    def pick_outdir(self):
        path = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if path:
            self.out_edit.setText(path)

    def convert(self):
        try:
            bai2_path = Path(self.file_edit.text()).expanduser().resolve()
            if not bai2_path.is_file():
                raise FileNotFoundError("Please choose a valid BAI2 file.")
            outdir = Path(self.out_edit.text()).expanduser().resolve() if self.out_edit.text() else bai2_path.parent / bai2_path.stem
            self.append_log(f"➡️  Converting: {bai2_path}")
            self.append_log(f"➡️  Output dir : {outdir}\n")

            headers, accounts, txns = [], [], []
            for rec in parse_bai2(bai2_path):
                rcode = rec["record_code"]
                if rcode == "01":
                    headers.append(rec)
                elif rcode == "03":
                    accounts.append(rec)
                elif rcode == "16":
                    txns.append(rec)

            write_csv(headers, HDR_FIELDS, outdir / "file_header.csv")
            write_csv(accounts, ACC_FIELDS, outdir / "accounts.csv")
            write_csv(txns, TXN_FIELDS, outdir / "transactions.csv")

            self.append_log(f"✅ Headers      : {len(headers)} row(s)")
            self.append_log(f"✅ Accounts     : {len(accounts)} row(s)")
            self.append_log(f"✅ Transactions : {len(txns)} row(s)")
            self.append_log("\n🎉 Conversion complete!\n")

            QMessageBox.information(self, "Finished", f"Converted {bai2_path.name} to CSV successfully!\n\nSaved in:\n{outdir}")

        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            self.append_log(f"❌ Error: {exc}\n")
            
def main():
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_EnableHighDpiScaling)
    gui = BAI2ConverterGUI()
    gui.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
