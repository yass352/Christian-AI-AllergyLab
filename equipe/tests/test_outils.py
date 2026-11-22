"""Chaque outil de l'équipe, vérifié sur la table inventée : des résultats comptés à la main."""

import re

import pandas as pd
import pytest

from equipe.outils import classer_allergenes as module_classer
from equipe.outils import croiser as module_croiser
from equipe.outils.calendrier_pollinique import calendrier_pollinique
from equipe.outils.chercher_colonnes import chercher_colonnes
from equipe.outils.classer_allergenes import classer_allergenes
from equipe.outils.codes_officiels import codes_officiels
from equipe.outils.colonnes_par_famille import colonnes_par_famille
from equipe.outils.compter_codes import compter_codes
from equipe.outils.croiser import croiser
from equipe.outils.decrire_colonne import decrire_colonne
from equipe.outils.positifs import positifs
from equipe.outils.source_allergene import source_allergene
from kit.donnees import RACINE


def test_chercher_colonnes_sans_majuscules():
    assert chercher_colonnes("act_d") == ["Act_d_1", "Act_d_8"]
    assert chercher_colonnes("introuvable") == []


def test_decrire_une_colonne_codee():
    description = decrire_colonne("Gender")
    assert description["bloc"] == "clinique"
    assert description["renseignees_par_puce"] == {"ALEX": 4, "ISAC_V1": 4, "ISAC_V2": 4}
    assert description["valeurs_frequentes"] == {"1": 6, "0": 6}


def test_decrire_un_dosage_compte_les_non_mesures():
    description = decrire_colonne("Act_d_8")
    assert description["bloc"] == "dosage"
    assert description["renseignees"] == 8  # la puce ALEX ne le mesure pas dans la table inventée
    assert description["renseignees_par_puce"]["ALEX"] == 0


def test_une_colonne_inconnue_donne_une_erreur_qui_aide():
    with pytest.raises(ValueError, match="Act_d_1"):
        decrire_colonne("Act_d1")


def test_compter_codes_separe_les_cellules_a_plusieurs_codes():
    # "0", "1, 3", "0", "1", "0", "2", "1", "0", "1", "0", "0", "1"
    assert compter_codes("Treatment_of_athsma", "") == {
        "patients": 12, "cases_vides": 0, "codes": {"0": 6, "1": 5, "2": 1, "3": 1},
    }
    # ISAC_V1 : "1, 3", "0", "0", "0".
    assert compter_codes("Treatment_of_athsma", "ISAC_V1")["codes"] == {"0": 3, "1": 1, "3": 1}
    with pytest.raises(ValueError, match="Puce inconnue"):
        compter_codes("Gender", "ISAC")


def test_positifs_ignore_les_non_mesures():
    # Aln_g_1 >= 0,3 : 2,15 (ISAC_V1) et 7,25 (ALEX) ; 0,05 ne compte pas.
    resultat = positifs("Aln_g_1", 0.3)
    assert (resultat["mesures"], resultat["positifs"], resultat["pourcentage"]) == (12, 2, 16.7)
    assert resultat["par_puce"]["ISAC_V2"] == {"mesures": 4, "positifs": 0}
    # Act_d_8 n'est pas mesuré sur ALEX : 8 patients mesurés, pas 12.
    assert positifs("Act_d_8", 0.3)["mesures"] == 8
    with pytest.raises(ValueError, match="clinique"):
        positifs("Age", 0.3)


def test_classer_allergenes(monkeypatch):
    par_nombre = classer_allergenes(0.3, "", "nombre", 3)
    assert [ligne["colonne"] for ligne in par_nombre] == ["Act_d_1", "Act_d_8", "Cor_a_14"]
    assert par_nombre[0] == {"colonne": "Act_d_1", "positifs": 5, "mesures": 12, "pourcentage": 41.7}
    # Sur douze lignes, aucune colonne n'atteint 30 mesurés : le classement par pourcentage est vide.
    assert classer_allergenes(0.3, "", "pourcentage", 3) == []
    monkeypatch.setattr(module_classer, "MESURES_MIN", 1)
    assert classer_allergenes(0.3, "ALEX", "pourcentage", 1)[0]["colonne"] == "Aca_m"  # 2 sur 4 : 1,7 et 0,9


def test_croiser(monkeypatch):
    assert croiser("Chip_Type", "Gender") == {
        "ALEX": {"0": 1, "1": 3}, "ISAC_V1": {"0": 3, "1": 1}, "ISAC_V2": {"0": 2, "1": 2},
    }
    monkeypatch.setattr(module_croiser, "VALEURS_MAX", 5)  # douze identifiants : plus que cinq valeurs
    with pytest.raises(ValueError, match="trop"):
        croiser("Patient_ID", "Gender")


def test_codes_officiels_par_colonne_et_par_mot():
    rhinite = codes_officiels("Treatment_of_rhinitis")["tables"]["Traitement rhinite"]
    assert rhinite["9"] == "Non renseigné" and rhinite["0"] == "Aucun"
    assert "lecture à vérifier" in codes_officiels("Sensitization")["remarque"]
    assert "ATCD d'anaphylaxie alimentaire (AA)" in codes_officiels("anaphylaxie")["tables"]
    assert codes_officiels("Genre inexistant")["tables"] == {}


def test_source_allergene():
    kiwi = source_allergene("Act_d_8")
    assert (kiwi["source"], kiwi["famille"], kiwi["colonnes"]) == ("kiwi", "aliment végétal", ["Act_d_1", "Act_d_8"])
    assert source_allergene("Der_p")["source"].startswith("acarien")
    assert source_allergene("Aca_m")["source"] == "inconnue"  # absent de la table de l'équipe


def test_colonnes_par_famille():
    assert colonnes_par_famille("")["aliment végétal"] == 2
    assert colonnes_par_famille("venin") == {"venin d'hyménoptère": ["Api_m_1"]}
    with pytest.raises(ValueError, match="Aucune famille"):
        colonnes_par_famille("minéral")


def test_calendrier_pollinique():
    bouleau = calendrier_pollinique("Bet_v_1")
    assert bouleau["taxon"] == "bouleau" and len(bouleau["moyenne_grains_m3_par_mois"]) == 12
    assert calendrier_pollinique("graminées")["allergenes_acc"].startswith("Phl_p")
    assert "ambroisie" in calendrier_pollinique("")["taxons"]
    with pytest.raises(ValueError, match="Taxon inconnu"):
        calendrier_pollinique("baobab")


def test_les_tables_de_reference_sont_coherentes():
    """Chaque préfixe de la table des allergènes et chaque colonne de la correspondance existent dans le kit."""
    colonnes = pd.read_csv(RACINE / "kit" / "colonnes.csv", encoding="utf-8")["colonne"]
    allergenes = pd.read_csv(RACINE / "equipe" / "analyse" / "allergenes.csv", encoding="utf-8")
    assert allergenes["prefixe"].is_unique
    for prefixe in allergenes["prefixe"]:
        assert any(c == prefixe or c.startswith((prefixe + "_", prefixe + ".")) for c in colonnes), prefixe
    correspondance = pd.read_csv(RACINE / "equipe" / "analyse" / "correspondance_colonnes.csv", encoding="utf-8")
    assert set(correspondance["colonne"]) <= set(colonnes)


def test_aucun_outil_ne_passe_un_texte_a_eval_exec_ou_query():
    """CLAUDE.md : un outil ne passe jamais un texte venu du modèle à eval, exec, query ou une fonction du même genre."""
    for fichier in (RACINE / "equipe" / "outils").glob("*.py"):
        texte = fichier.read_text(encoding="utf-8")
        assert not re.search(r"\b(eval|exec)\s*\(|\.query\s*\(|\.eval\s*\(", texte), fichier.name
