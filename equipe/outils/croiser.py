"""Outil : croiser deux colonnes à peu de valeurs."""

from smolagents import tool

from equipe.outils import acces

VALEURS_MAX = 20  # au-delà, le tableau croisé serait illisible


@tool
def croiser(ligne: str, colonne: str) -> dict:
    """Tableau croisé de deux colonnes à peu de valeurs (codes cliniques, puce) : le nombre de patients par couple de valeurs.

    Les cases vides sont comptées sous la valeur "vide". Une cellule à plusieurs codes ("1, 3") reste telle quelle.
    Le résultat se lit : resultat[valeur de ligne][valeur de colonne] = nombre de patients.

    Args:
        ligne: la colonne dont les valeurs forment les lignes, par exemple "Chip_Type".
        colonne: la colonne dont les valeurs forment les colonnes, par exemple "Gender".
    """
    for nom in (ligne, colonne):
        acces.verifier_colonne(nom)
    t = acces.tableau()
    a = t[ligne].map(acces.en_texte, na_action="ignore").fillna("vide")
    b = t[colonne].map(acces.en_texte, na_action="ignore").fillna("vide")
    for nom, serie in ((ligne, a), (colonne, b)):
        if serie.nunique() > VALEURS_MAX:
            raise ValueError(f"{nom} a {serie.nunique()} valeurs différentes : trop pour un tableau croisé.")
    comptes = a.to_frame("a").assign(b=b).value_counts()
    resultat = {}
    for (valeur_a, valeur_b), n in sorted(comptes.items()):
        resultat.setdefault(valeur_a, {})[valeur_b] = int(n)
    return resultat
