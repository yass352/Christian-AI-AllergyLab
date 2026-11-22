"""Prépare les fichiers pollens de donnees_complementaires/ à partir des relevés du RNSA.

Source : « Données historiques de surveillance des pollens et des moisissures »,
Ministère chargé de la santé, sur data.gouv.fr, Licence Ouverte 2.0. On en
télécharge l'archive BDD_daily (un fichier Excel par capteur et par année), on
la décompresse, puis, depuis la racine du dépôt :

    uv run --with xlrd --with openpyxl python equipe/analyse/preparer_pollens.py <dossier BDD_daily>

xlrd et openpyxl ne servent qu'ici, pour lire les fichiers Excel : --with les
prête le temps de la commande, sans les ajouter aux dépendances du projet.

Règles de calcul, écrites aussi dans donnees_complementaires/README.md :
- un mois compte comme mesuré si la colonne « Total Taxons » y dépasse 0 ;
- un mois mesuré, une case vide de pollen vaut 0 grain (aucun grain compté) ;
- une moisissure absente toute l'année d'un capteur n'y a pas été comptée :
  ce capteur-année est écarté pour elle ;
- les moyennes nationales ne portent que sur la métropole (Corse comprise).
"""

import sys
import warnings
from pathlib import Path

import pandas as pd

SORTIE = Path(__file__).resolve().parents[2] / "donnees_complementaires"

# Colonne du RNSA, nom en français, famille, colonnes du tableau ACC qui lui correspondent (choix de l'équipe).
TAXONS = [
    ("ALNUS", "aulne", "pollen d'arbre", "Aln_g"),
    ("BETULA", "bouleau", "pollen d'arbre", "Bet_v"),
    ("CORYLUS", "noisetier", "pollen d'arbre", "Cor_a_1.0101 Cor_a_1.0103 Cor_a_pollen"),
    ("CUPRESSA", "cupressacées (cyprès)", "pollen d'arbre", "Cup_a Cup_s Cry_j Jun_a"),
    ("FRAXINUS", "frêne", "pollen d'arbre", "Fra_e"),
    ("CARPINUS", "charme", "pollen d'arbre", ""),
    ("QUERCUS", "chêne", "pollen d'arbre", ""),
    ("CASTANEA", "châtaignier", "pollen d'arbre", ""),
    ("FAGUS", "hêtre", "pollen d'arbre", "Fag_s"),
    ("OLEA", "olivier", "pollen d'arbre", "Ole_e"),
    ("PLATANUS", "platane", "pollen d'arbre", "Pla_a"),
    ("POPULUS", "peuplier", "pollen d'arbre", ""),
    ("SALIX", "saule", "pollen d'arbre", ""),
    ("TILIA", "tilleul", "pollen d'arbre", ""),
    ("JUGLANS", "noyer", "pollen d'arbre", "Jug_r_pollen"),
    ("AILANTHU", "ailante", "pollen d'arbre", "Ail_a"),
    ("GRAMINEE", "graminées", "pollen de graminée", "Phl_p Cyn_d Lol_p Lol_spp."),
    ("URTICACE", "urticacées (pariétaire, ortie)", "pollen d'herbacée", "Par_j"),
    ("PLANTAGI", "plantain", "pollen d'herbacée", "Pla_l"),
    ("ARTEMISI", "armoise", "pollen d'herbacée", "Art_v"),
    ("AMBROSIA", "ambroisie", "pollen d'herbacée", "Amb_a"),
    ("CHENOP", "chénopodiacées", "pollen d'herbacée", "Che_a Sal_k"),
    ("MERCURIA", "mercuriale", "pollen d'herbacée", "Mer_a"),
    ("RUMEX", "oseille (rumex)", "pollen d'herbacée", ""),
    ("ALTERNAR", "alternaria", "moisissure", "Alt_a"),
    ("CLADOSPO", "cladosporium", "moisissure", "Cla_h"),
    ("ASPERGIL", "aspergillus", "moisissure", "Asp_f"),
]
FAMILLE = {taxon: famille for _, taxon, famille, _ in TAXONS}

# Capteurs hors de la métropole : gardés dans le fichier par capteur, écartés des moyennes nationales.
ZONES = {
    "ANDORRA": "etranger", "BRUSSBUR": "etranger", "BRUSSLAN": "etranger",
    "NOUMEA": "outre-mer", "SDREUNIO": "outre-mer", "SPREUNIO": "outre-mer",
}


def lire_un_fichier(chemin):
    """Les sommes et nombres de jours mesurés, par mois et par taxon, d'un fichier capteur-année."""
    feuille = pd.read_excel(chemin)
    station = str(feuille.columns[0]).strip()
    dates = pd.to_datetime(feuille.iloc[:, 0], errors="coerce")
    total = pd.to_numeric(feuille["Total Taxons"], errors="coerce").fillna(0)
    mois_mesures = total.groupby(dates.dt.month).sum().loc[lambda s: s > 0].index
    jours = dates.dt.month.isin(mois_mesures)
    lignes = []
    for colonne, taxon, _, _ in TAXONS:
        if colonne not in feuille:
            continue
        valeurs = pd.to_numeric(feuille[colonne], errors="coerce")
        if FAMILLE[taxon] == "moisissure" and valeurs.isna().all():
            continue  # moisissure non comptée par ce capteur cette année-là
        valeurs = valeurs.fillna(0)[jours]
        par_mois = valeurs.groupby(dates[jours].dt.month).agg(["sum", "count"])
        for mois, (somme, nombre) in par_mois.iterrows():
            lignes.append((station, dates.dt.year.mode()[0], int(mois), taxon, float(somme), int(nombre)))
    return lignes


def main(dossier):
    warnings.filterwarnings("ignore")  # avertissements de style des fichiers Excel, sans effet sur les valeurs
    fichiers = sorted(Path(dossier).glob("Particle_Extract_*.xls*"))
    if not fichiers:
        print(f"Aucun fichier Particle_Extract_* dans {dossier}. Donne le dossier BDD_daily décompressé.")
        return 1
    lignes = []
    for rang, chemin in enumerate(fichiers, 1):
        lignes += lire_un_fichier(chemin)
        if rang % 200 == 0:
            print(f"{rang} fichiers lus sur {len(fichiers)}")
    mesures = pd.DataFrame(lignes, columns=["station", "annee", "mois", "taxon", "somme", "jours"])
    mesures["zone"] = mesures["station"].map(ZONES).fillna("metropole")
    infos = pd.DataFrame(TAXONS, columns=["colonne_rnsa", "taxon", "famille", "allergenes_acc"]).drop(columns="colonne_rnsa")
    SORTIE.mkdir(exist_ok=True)

    # 1. Par capteur et par mois, toutes années confondues.
    stations = mesures.groupby(["station", "zone", "taxon", "mois"]).agg(
        somme=("somme", "sum"), jours=("jours", "sum"),
        annees=("annee", "nunique"), premiere_annee=("annee", "min"), derniere_annee=("annee", "max"),
    ).reset_index()
    stations["moyenne_grains_m3"] = (stations["somme"] / stations["jours"]).round(2)
    stations = stations.drop(columns="somme")
    ecrire(stations, "rnsa-pollens-mensuels-stations.csv",
           ["station", "zone", "taxon", "mois", "moyenne_grains_m3", "jours", "annees", "premiere_annee", "derniere_annee"])

    # 2. France métropolitaine, par mois : moyenne journalière sur tous les jours mesurés.
    metropole = mesures[mesures["zone"] == "metropole"]
    france = metropole.groupby(["taxon", "mois"]).agg(
        somme=("somme", "sum"), jours=("jours", "sum"), stations=("station", "nunique"),
    ).reset_index()
    france["moyenne_grains_m3"] = (france["somme"] / france["jours"]).round(2)
    france = france.merge(infos, on="taxon")
    ecrire(france, "rnsa-pollens-mensuels-france.csv",
           ["taxon", "famille", "allergenes_acc", "mois", "moyenne_grains_m3", "jours", "stations"])

    # 3. France métropolitaine, par année : indice pollinique annuel (somme des concentrations
    #    journalières d'un capteur), médiane des capteurs mesurés au moins six mois dans l'année.
    capteurs_annees = metropole.groupby(["station", "annee", "taxon"]).agg(
        indice=("somme", "sum"), mois=("mois", "nunique"),
    ).reset_index()
    capteurs_annees = capteurs_annees[capteurs_annees["mois"] >= 6]
    annuel = capteurs_annees.groupby(["taxon", "annee"]).agg(
        indice_pollinique_median=("indice", "median"), stations=("station", "nunique"),
    ).reset_index()
    annuel["indice_pollinique_median"] = annuel["indice_pollinique_median"].round(1)
    ecrire(annuel.merge(infos, on="taxon"), "rnsa-pollens-annuels-france.csv",
           ["taxon", "famille", "allergenes_acc", "annee", "indice_pollinique_median", "stations"])
    return 0


def ecrire(tableau, nom, colonnes):
    """Écrit un CSV en UTF-8, virgule comme séparateur, point décimal, fins de ligne LF."""
    chemin = SORTIE / nom
    tableau[colonnes].sort_values(colonnes[:4]).to_csv(chemin, index=False, encoding="utf-8", lineterminator="\n")
    print(f"{chemin.name} : {len(tableau)} lignes")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage : uv run --with xlrd --with openpyxl python equipe/analyse/preparer_pollens.py <dossier BDD_daily>")
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
