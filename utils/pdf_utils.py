"""Utilitaires partagés pour la validation de contenu PDF téléchargé."""

PDF_MAGIC_BYTES = b"%PDF-"


def is_valid_pdf(content: bytes) -> bool:
    """Vérifie que `content` commence bien par la signature PDF standard.

    Un lien expiré ou une redirection vers une page de login/erreur renvoie
    souvent un statut HTTP 200 avec du HTML au lieu du PDF attendu :
    pdfplumber échoue alors avec une exception peu explicite. Ce contrôle
    permet de rejeter (et journaliser clairement) ce cas dès le
    téléchargement plutôt que de laisser pdfplumber échouer plus loin."""
    return content[:5] == PDF_MAGIC_BYTES
