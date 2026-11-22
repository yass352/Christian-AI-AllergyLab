"""Recopie en CSV les tables de codes du dictionnaire officiel, donnees/acc-dictionnaire-final.xls.

Le fichier Excel range ses tables côte à côte : pour chaque variable, un titre,
puis une ligne par code (« 9 - Non renseigné », « 0 - Non »…). Ce script les
met l'une sous l'autre, une ligne par code, dans
donnees_complementaires/acc-dictionnaire-codes.csv, sans rien interpréter.
Le fichier de donnees/ est ouvert en lecture seule et n'est jamais modifié.

Depuis la racine du dépôt :

    uv run --with xlrd python equipe/analyse/extraire_dictionnaire.py

xlrd ne sert qu'ici, pour lire le format .xls : --with le prête le temps de la
commande, sans l'ajouter aux dépendances du projet.
"""

import re
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parents[2]
SOURCE = RACINE / "donnees" / "acc-dictionnaire-final.xls"
SORTIE = RACINE / "donnees_complementaires" / "acc-dictionnaire-codes.csv"

# Colonnes des libellés dans la feuille ; le code est juste à droite, sauf pour
# la première table, qui a une colonne « Abrégé » entre les deux.
LIBELLES = [0, 4, 7, 10, 13, 16, 19, 22, 25]


def texte(cellule):
    return "" if pd.isna(cellule) else " ".join(str(cellule).split())


def main():
    feuille = pd.read_excel(SOURCE, header=None)
    lignes = []
    for colonne in LIBELLES:
        colonne_code = colonne + 2 if colonne == 0 else colonne + 1
        variable = None
        for _, rangee in feuille.iterrows():
            libelle, code = texte(rangee[colonne]), texte(rangee[colonne_code])
            if code == "Anonyme":  # le titre d'une nouvelle table
                variable = libelle
                continue
            if not variable or not libelle:
                continue
            if colonne == 0 and not code:
                code = texte(rangee[1])  # « 1 à 12 » : seule la colonne Abrégé le donne
            code = code.removesuffix(".0")
            # « 9 - Non renseigné » devient le libellé « Non renseigné » ; le code est déjà à part.
            libelle = re.sub(r"^\d+\s*-\s*", "", libelle)
            lignes.append({"variable": variable, "code": code, "libelle": libelle})
    tableau = pd.DataFrame(lignes)
    tableau.to_csv(SORTIE, index=False, encoding="utf-8", lineterminator="\n")
    print(f"{SORTIE.name} : {len(tableau)} codes, {tableau['variable'].nunique()} variables")


if __name__ == "__main__":
    main()
