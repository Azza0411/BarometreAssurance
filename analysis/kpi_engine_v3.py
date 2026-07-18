import re
from difflib import SequenceMatcher
from utils.text_normalizer import TextNormalizer


class KPIEngineV3:

    def __init__(self, registry):
        self.registry = registry
        self.norm = TextNormalizer()

    # -------------------------
    def similarity(self, a, b):
        return SequenceMatcher(None, a, b).ratio()

    # -------------------------
    def match_kpi(self, text, kpi_list):

        text = self.norm.clean(text)

        best = None
        best_score = 0

        for kpi in kpi_list:

            kpi_clean = self.norm.clean(kpi)

            score = self.similarity(text, kpi_clean)

            if score > best_score and score > 0.65:
                best = kpi
                best_score = score

        return best, best_score   # ✅ BIEN DANS LA FONCTION

    # -------------------------
    def extract_from_blocks(self, blocks, use_case_id):

        results = {}

        kpi_list = self.registry[use_case_id]

        for b in blocks:

            if not isinstance(b, dict):
                continue

            text = b.get("text", "")
            value = b.get("value", None)

            if not text:
                continue

            kpi, score = self.match_kpi(text, kpi_list)

            if kpi:
                results[kpi] = {
                    "value": value,
                    "raw": text,
                    "score": score
                }

        return results

    # -------------------------
    def normalize_item(self, item):

        if isinstance(item, dict):
            return item.get("blocks", [])

        if isinstance(item, list):
            return item

        return []

    # -------------------------
    def run(self, structured_data, use_case_id):

        final = {}

        if isinstance(structured_data, list):

            for item in structured_data:

                pdf = item.get("pdf", "unknown.pdf")
                blocks = self.normalize_item(item)

                final[pdf] = self.extract_from_blocks(blocks, use_case_id)

            return final

        if isinstance(structured_data, dict):

            for doc, data in structured_data.items():

                blocks = self.normalize_item(data)

                final[doc] = self.extract_from_blocks(blocks, use_case_id)

            return final

        return final