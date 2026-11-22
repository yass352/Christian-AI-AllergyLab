"""Outil : trouver les colonnes dont le nom contient un motif."""

from smolagents import tool

from equipe.outils import acces

MAXIMUM = 60  # au-delà, la liste serait trop longue à lire pour le modèle


@tool
def chercher_colonnes(motif: str) -> list:
    """Liste les colonnes du tableau dont le nom contient un motif, sans tenir compte des majuscules.

    Exemples : "Ara_h" donne les dosages de l'arachide, "Der_p" ceux d'un acarien, "treatment" les traitements.

    Args:
        motif: un morceau de nom de colonne. Un texte simple, pas une expression régulière.
    """
    motif = motif.strip().lower()
    noms = [nom for nom in acces.tableau().columns if motif in nom.lower()]
    if len(noms) > MAXIMUM:
        return noms[:MAXIMUM] + [f"… et {len(noms) - MAXIMUM} autres : précise le motif."]
    return noms
