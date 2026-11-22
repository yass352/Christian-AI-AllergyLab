"""Outil : lire le sens des codes d'une colonne clinique dans le dictionnaire officiel."""

import unicodedata

from smolagents import tool

from equipe.outils import acces

DICTIONNAIRE = acces.COMPLEMENTS / "acc-dictionnaire-codes.csv"  # extrait de donnees/acc-dictionnaire-final.xls
CORRESPONDANCE = acces.ANALYSE / "correspondance_colonnes.csv"  # colonne du tableau -> table du dictionnaire


def sans_accent(texte):
    return "".join(c for c in unicodedata.normalize("NFD", texte.lower()) if unicodedata.category(c) != "Mn")


@tool
def codes_officiels(recherche: str) -> dict:
    """Donne le sens des codes d'une colonne clinique, d'après le dictionnaire officiel du jeu de données.

    Accepte un nom de colonne du tableau ("Treatment_of_rhinitis") ou un mot du nom d'une table du
    dictionnaire ("rhinite", "GINA", "anaphylaxie"). Dans la plupart des tables, le code 9 veut dire « non renseigné ».

    Args:
        recherche: un nom de colonne du tableau, ou un mot à chercher dans les noms des tables du dictionnaire.
    """
    dictionnaire = acces.reference(DICTIONNAIRE)
    correspondance = acces.reference(CORRESPONDANCE)
    resultat = {"recherche": recherche}
    ligne = correspondance[correspondance["colonne"] == recherche]
    if not ligne.empty:
        variables = [ligne["variable_dictionnaire"].iloc[0]] if ligne["variable_dictionnaire"].iloc[0] else []
        if ligne["remarque"].iloc[0]:
            resultat["remarque"] = ligne["remarque"].iloc[0]
    else:
        mot = sans_accent(recherche)
        variables = [v for v in dictionnaire["variable"].unique() if mot in sans_accent(v)][:3]
    resultat["tables"] = {
        variable: dict(zip(groupe["code"], groupe["libelle"]))
        for variable, groupe in dictionnaire[dictionnaire["variable"].isin(variables)].groupby("variable", sort=False)
    }
    if not resultat["tables"] and "remarque" not in resultat:
        resultat["remarque"] = "Aucune table trouvée. Essaie un autre mot, ou un nom de colonne clinique."
    return resultat
