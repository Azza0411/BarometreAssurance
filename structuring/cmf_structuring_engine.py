class CMFStructuringEngine:

    def structure(self, data):

        structured = {
            "BILAN": [],
            "RESULTAT": [],
            "ANNEXE_12": [],
            "ANNEXE_13": [],
            "TEXT": []
        }

        # -------------------------
        # HANDLE TEXT BLOCKS
        # -------------------------
        for item in data["text"]:

            # 🔥 FIX: item est un dict
            text_blocks = item.get("text", [])

            for txt in text_blocks:

                if not txt:
                    continue

                t = txt.lower()

                if "bilan" in t:
                    structured["BILAN"].append(txt)

                elif "résultat" in t or "resultat" in t:
                    structured["RESULTAT"].append(txt)

                elif "annexe 12" in t:
                    structured["ANNEXE_12"].append(txt)

                elif "annexe 13" in t:
                    structured["ANNEXE_13"].append(txt)

                else:
                    structured["TEXT"].append(txt)

        # -------------------------
        # ADD TABLES RAW
        # -------------------------
        structured["RAW_TABLES"] = data["tables"]

        return structured