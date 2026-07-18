import pdfplumber
import os


class CMFTableExtractor:

    def __init__(self, base_path):
        self.base_path = base_path

    def get_pdfs(self, company):

        folder = f"{self.base_path}/{company}"

        return [
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if f.endswith(".pdf")
        ]

    def extract(self, pdf_path):

        print(f"[READING] {pdf_path}")

        tables = []
        text = []

        try:
            with pdfplumber.open(pdf_path) as pdf:

                for page in pdf.pages:

                    t = page.extract_tables()
                    if t:
                        tables.extend(t)

                    txt = page.extract_text()
                    if txt:
                        text.append(txt)

        except Exception as e:

            print(f"[SKIP INVALID PDF] {pdf_path} -> {e}")
            return {
                "pdf": pdf_path,
                "tables": [],
                "text": []
            }

        return {
            "pdf": pdf_path,
            "tables": tables,
            "text": text
        }

    def process(self, company):

        pdfs = self.get_pdfs(company)

        all_data = {
            "tables": [],
            "text": []
        }

        for pdf in pdfs:

            data = self.extract(pdf)

            all_data["tables"].append({
                "pdf": pdf,
                "tables": data["tables"]
            })

            all_data["text"].append({
                "pdf": pdf,
                "text": data["text"]
            })

        return all_data