
import re


def masquer_identifiants(texte: str, identifiants: list[str]) -> str:
    """
    Masque les identifiants de patients pr├®sents dans un texte.
    """

    if not isinstance(texte, str):
        raise TypeError("Le texte doit ├¬tre une cha├«ne de caract├¿res.")

    if not isinstance(identifiants, list):
        raise TypeError("Les identifiants doivent ├¬tre fournis dans une liste.")

    identifiants_valides = [
        identifiant
        for identifiant in identifiants
        if isinstance(identifiant, str) and identifiant
    ]

    # Les identifiants les plus longs sont trait├®s en premier.
    identifiants_valides.sort(key=len, reverse=True)

    if not identifiants_valides:
        return texte

    # Construire une expression r├®guli├¿re unique.
    motif = r"(?<!\w)(?:" + "|".join(
        re.escape(identifiant) for identifiant in identifiants_valides
    ) + r")(?!\w)"

    return re.sub(motif, "[IDENTIFIANT MASQU├ë]", texte)
