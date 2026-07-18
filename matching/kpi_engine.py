import re


class KPIEngine:

    def __init__(self, registry):
        self.registry = registry

    # -------------------------
    # CLEAN NUMBERS
    # -------------------------
    def clean_value(self, val):

        if not val:
            return None

        if isinstance(val, (int, float)):
            return val

        val = str(val)

        # remove spaces
        val = val.replace(" ", "")

        # extract number
        match = re.findall(r"[\d,.]+", val)

        if match:
            return match[0]

        return val

    # -------------------------
    # SEARCH IN TEXT + TABLES
    # -------------------------
    def search_kpi(self, kpi, structured):

        kpi_lower = kpi.lower()

        # 1. SEARCH IN TEXT
        for txt in structured["TEXT"]:

            if kpi_lower in txt.lower():
                return txt

        # 2. SEARCH IN TABLES (IMPORTANT PART)
        for table_block in structured.get("RAW_TABLES", []):

            tables = table_block.get("tables", [])

            for table in tables:

                for row in table:

                    if not row:
                        continue

                    row_str = " ".join([str(x) for x in row if x])

                    if kpi_lower in row_str.lower():
                        return row_str

        return None

    # -------------------------
    # MAIN PROCESS
    # -------------------------
    def run(self, structured):

        results = {}

        for use_case, kpis in self.registry.items():

            results[use_case] = {}

            for kpi in kpis:

                value = self.search_kpi(kpi, structured)

                results[use_case][kpi] = {
                    "value": self.clean_value(value),
                    "raw": value
                }

        return results