import re
import unicodedata


class TextNormalizer:

    def clean(self, text: str) -> str:

        if not text:
            return ""

        # unicode normalize
        text = unicodedata.normalize("NFKD", text)

        # lower
        text = text.lower()

        # remove accents
        text = "".join(
            c for c in text if not unicodedata.combining(c)
        )

        # remove weird spaces
        text = re.sub(r"\s+", " ", text)

        # remove special chars noise
        text = re.sub(r"[^a-z0-9%()./-]+", " ", text)

        return text.strip()