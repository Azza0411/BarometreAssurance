import os
import pdfplumber


class CMFPDFReader:

    def __init__(self, base_path):
        self.base_path = base_path

    def list_pdfs(self, company):
        folder = f"{self.base_path}/{company}"

        if not os.path.exists(folder):
            print(f"Folder not found: {folder}")
            return []

        return [
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if f.endswith(".pdf")
        ]

    def extract_text(self, pdf_path):
        text_pages = []

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text_pages.append(page.extract_text())
        except Exception as e:
            print(f"Error reading {pdf_path}: {e}")

        return text_pages

    def process_company(self, company):
        pdfs = self.list_pdfs(company)

        all_data = {}

        for pdf in pdfs:
            print(f"Reading: {pdf}")
            all_data[pdf] = self.extract_text(pdf)
        print("PDFs found:", pdfs)
        return all_data

    def preview_tables(self, tables_dict):
        for pdf, pages in tables_dict.items():

            print("\n" + "=" * 80)
            print(f"PDF: {pdf}")
            print("=" * 80)

            for i, page_text in enumerate(pages):
                print(f"\n--- PAGE {i + 1} ---\n")

                if page_text:
                    print(page_text[:1000])  # limiter l'affichage
                else:
                    print("No text detected")


# =========================
# MAIN TEST (HORS CLASSE)
# =========================
if __name__ == "__main__":
    reader = CMFPDFReader("data/cmf")

    data = reader.process_company("STAR")

    reader.preview_tables(data)