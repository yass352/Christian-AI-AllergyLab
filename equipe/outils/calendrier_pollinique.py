"""Outil : le calendrier pollinique moyen de la France métropolitaine (données complémentaires du RNSA)."""

from smolagents import tool

from equipe.outils import acces

CALENDRIER = acces.COMPLEMENTS / "rnsa-pollens-mensuels-france.csv"  # préparé par equipe/analyse/preparer_pollens.py


@tool
def calendrier_pollinique(taxon: str) -> dict:
    """Calendrier pollinique moyen de la France métropolitaine : concentration moyenne par mois, en grains par m³ d'air et par jour.

    Ce sont des relevés de l'air (Réseau National de Surveillance Aérobiologique, 1987-2024), pas des patients du
    tableau : seul le mois (Blood_Month_sample) permet de les rapprocher. Source : Ministère chargé de la santé, Licence Ouverte 2.0.

    Args:
        taxon: un nom français ("bouleau", "graminées", "ambroisie") ou un préfixe d'allergène du tableau ("Bet_v", "Phl_p") ; "" donne la liste des taxons.
    """
    calendrier = acces.reference(CALENDRIER)
    if not taxon.strip():
        return {"taxons": sorted(calendrier["taxon"].unique())}
    recherche = taxon.strip().lower()

    def correspond(codes):
        # "Bet_v_1" commence par "bet_v" ; "Cor_a" est le début de "cor_a_pollen".
        return any(recherche.startswith(c) or (len(recherche) >= 4 and c.startswith(recherche)) for c in codes.split())

    trouve = calendrier[
        calendrier["taxon"].str.lower().str.contains(recherche, regex=False)
        | calendrier["allergenes_acc"].str.lower().apply(correspond)
    ]
    if trouve.empty:
        raise ValueError(f"Taxon inconnu : {taxon!r}. Appelle calendrier_pollinique(\"\") pour la liste.")
    nom = trouve["taxon"].iloc[0]
    lignes = trouve[trouve["taxon"] == nom]
    moyennes = {int(m): float(v) for m, v in zip(lignes["mois"], lignes["moyenne_grains_m3"])}
    return {
        "taxon": nom,
        "famille": lignes["famille"].iloc[0],
        "allergenes_acc": lignes["allergenes_acc"].iloc[0],
        "moyenne_grains_m3_par_mois": moyennes,
        "mois_le_plus_charge": max(moyennes, key=moyennes.get),
        "capteurs": int(lignes["stations"].astype(int).max()),
    }
