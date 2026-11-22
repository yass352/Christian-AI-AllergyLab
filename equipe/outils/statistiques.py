
"""Outils statistiques pour l'analyse des allergènes."""

import pandas as pd
from smolagents import tool

from kit.donnees import charger


@tool
def resume_allergene(nom_colonne: str) -> str:
    """Calcule les statistiques descriptives d'un allergène.

    Args:
        nom_colonne: nom exact de la colonne allergénique, par exemple Ara_h_1.
    """
    tableau = charger()

    # Seules les colonnes à partir du premier allergène sont autorisées.
    debut_allergenes = tableau.columns.get_loc("Act_d_1")
    colonnes_allergenes = set(tableau.columns[debut_allergenes:])

    if nom_colonne not in colonnes_allergenes:
        return (
            f"Colonne non autorisée ou inconnue : {nom_colonne}. "
            "Cet outil analyse uniquement les composants allergéniques."
        )

    valeurs = pd.to_numeric(tableau[nom_colonne], errors="coerce")

    manquantes = int(valeurs.isna().sum())
    negatives = int((valeurs.dropna() < 0).sum())
    mesures = valeurs[valeurs >= 0].dropna()

    if mesures.empty:
        return (
            f"{nom_colonne} : aucune mesure numérique non négative exploitable.\n"
            f"Valeurs manquantes : {manquantes}\n"
            f"Valeurs négatives non interprétées : {negatives}"
        )

    return (
        f"Allergène : {nom_colonne}\n"
        f"Nombre de mesures exploitables : {len(mesures)}\n"
        f"Moyenne : {mesures.mean():.3f}\n"
        f"Médiane : {mesures.median():.3f}\n"
        f"Minimum : {mesures.min():.3f}\n"
        f"Maximum : {mesures.max():.3f}\n"
        f"Valeurs manquantes : {manquantes}\n"
        f"Valeurs négatives non interprétées : {negatives}"
    )