"""Fixtures partagées : mots/pages/pdf factices imitant l'interface pdfplumber
utilisée par les extracteurs (word["text"/"x0"/"x1"/"top"], page.extract_text(),
page.extract_words(), pdf.pages), sans dépendre d'un vrai fichier PDF."""


def W(text, x0, top, width=None):
    """Un "mot" pdfplumber minimal. width par défaut proportionnel à la
    longueur du texte pour rester réaliste sans avoir à le préciser partout."""
    if width is None:
        width = max(len(text) * 6, 8)
    return {"text": text, "x0": x0, "x1": x0 + width, "top": top}


def line_of(words_specs, top):
    """words_specs: liste de (text, x0[, width]) -> liste de mots sur une même ligne."""
    return [W(*spec, top=top) if len(spec) == 2 else W(spec[0], spec[1], top, spec[2])
            for spec in words_specs]


class FakePage:
    def __init__(self, text, words):
        self._text = text
        self._words = words

    def extract_text(self):
        return self._text

    def extract_words(self):
        return self._words


class FakePDF:
    def __init__(self, pages):
        self.pages = pages
