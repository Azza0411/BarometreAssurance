import difflib


class KPIMatchingEngineV2:

    def __init__(self, kpi_master, source_map):
        self.kpi_master = kpi_master
        self.source_map = source_map

    def similarity(self, a, b):
        return difflib.SequenceMatcher(None, str(a).lower(), str(b).lower()).ratio()

    def find_best_source(self, kpi_id, extracted_data):

        candidates = self.source_map.get(kpi_id, [])

        best_score = 0
        best_table = None

        tables = extracted_data.get("tables", [])

        for table in tables:

            table_name = table.get("name", "")
            table_section = table.get("section", "")

            for c in candidates:

                score = self.similarity(table_name, c.get("table", "")) + \
                        self.similarity(table_section, c.get("section", ""))

                if score > best_score:
                    best_score = score
                    best_table = table

        return best_table, best_score

    def extract_kpi_value(self, kpi_id, table):

        if not table:
            return None

        return table.get("data", None)

    def process(self, extracted_data):

        results = {}

        for kpi_id in self.kpi_master.keys():

            table, score = self.find_best_source(kpi_id, extracted_data)

            results[kpi_id] = {
                "value": self.extract_kpi_value(kpi_id, table),
                "score": score,
                "table": table.get("name") if table else None
            }

        return results