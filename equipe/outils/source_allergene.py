"""Outil : dire d'où vient un allergène, à partir du nom de sa colonne de dosage."""

from smolagents import tool

from equipe.outils import acces

ALLERGENES = acces.ANALYSE / "allergenes.csv"  # la table de l'équipe : préfixe, source, nom latin, famille


def prefixe_de(code, prefixes):
    """Le plus long préfixe connu par lequel commence code : « Bet_v_1 » commence par « Bet_v »."""
    candidats = [p for p in prefixes if code == p or code.startswith(p + "_") or code.startswith(p + ".")]
    return max(candidats, key=len) if candidats else None


@tool
def source_allergene(code: str) -> dict:
    """Dit d'où vient un allergène à partir du nom de sa colonne de dosage : source, nom latin, famille, et les colonnes du même préfixe.

    Les noms suivent la nomenclature des allergènes : trois lettres du genre, une ou deux de l'espèce, puis le
    numéro de la molécule. "Bet_v_1" : bouleau (Betula verrucosa), molécule 1.

    Args:
        code: un nom de colonne de dosage ("Bet_v_1") ou un préfixe ("Der_p").
    """
    table = acces.reference(ALLERGENES)
    prefixe = prefixe_de(code.strip(), list(table["prefixe"]))
    if prefixe is None:
        return {"code": code, "source": "inconnue", "remarque": "préfixe absent de la table de l'équipe (equipe/analyse/allergenes.csv)."}
    ligne = table[table["prefixe"] == prefixe].iloc[0]
    colonnes = [c for c in acces.colonnes_dosage() if prefixe_de(c, [prefixe])]
    return {
        "code": code, "prefixe": prefixe, "source": ligne["source"], "nom_latin": ligne["nom_latin"],
        "famille": ligne["famille"], "colonnes": colonnes,
    }
