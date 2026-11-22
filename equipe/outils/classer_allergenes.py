"""Outil : classer les dosages selon leurs patients positifs."""

from smolagents import tool

from equipe.outils import acces

# Un pourcentage calculé sur trop peu de patients mesurés ne veut rien dire :
# ces colonnes sortent du classement par pourcentage.
MESURES_MIN = 30


@tool
def classer_allergenes(seuil: float, puce: str, critere: str, nombre: int) -> list:
    """Classe les colonnes de dosage selon leurs patients positifs (valeur >= seuil), parmi les patients mesurés.

    Avec critere "pourcentage", une colonne mesurée chez moins de 30 patients est écartée du classement.

    Args:
        seuil: le seuil de positivité, par exemple 0.3.
        puce: "ALEX", "ISAC_V1" ou "ISAC_V2" pour une seule puce ; "" pour toutes.
        critere: "nombre" pour classer par nombre de positifs, "pourcentage" pour classer par part des mesurés.
        nombre: combien de colonnes rendre, de 1 à 30.
    """
    if critere not in ("nombre", "pourcentage"):
        raise ValueError('critere vaut "nombre" ou "pourcentage".')
    t = acces.filtrer_puce(puce)
    lignes = []
    for colonne in acces.colonnes_dosage():
        mesures = int(t[colonne].notna().sum())
        if mesures == 0 or (critere == "pourcentage" and mesures < MESURES_MIN):
            continue
        nb_positifs = int((t[colonne] >= seuil).sum())
        lignes.append({
            "colonne": colonne, "positifs": nb_positifs, "mesures": mesures,
            "pourcentage": round(100 * nb_positifs / mesures, 1),
        })
    cle = "positifs" if critere == "nombre" else "pourcentage"
    lignes.sort(key=lambda ligne: (-ligne[cle], ligne["colonne"]))
    return lignes[: max(1, min(int(nombre), 30))]
