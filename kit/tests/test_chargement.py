"""Chargement : les règles de lecture, vérifiées sur la table inventée de kit/exemple/."""

import shutil
import subprocess
import tomllib

import pandas as pd
import pytest

from kit.donnees import NB_CLINIQUES, RACINE, charger, colonnes, lecture

MINI = RACINE / "kit" / "exemple" / "mini.csv"


def cellules_brutes():
    """Les cellules du fichier, découpées à la main, sans pandas."""
    texte = MINI.read_text(encoding="utf-8-sig")
    return [ligne.split(";") for ligne in texte.splitlines()]


@pytest.fixture(scope="module")
def mini():
    return charger(MINI)


def test_conventions_de_la_table_inventee():
    octets = MINI.read_bytes()
    assert octets.startswith(b"\xef\xbb\xbf")
    lignes = octets.split(b"\r\n")
    assert lignes[-1] == b"" and all(b"\n" not in ligne for ligne in lignes)
    entete, *patients = cellules_brutes()
    assert len(patients) == 12
    assert all(len(ligne) == len(entete) for ligne in patients)


def test_premiere_colonne_sans_bom(mini):
    assert mini.columns[0] == "Patient_ID"


def test_aucune_colonne_retiree_ni_renommee_aucune_ligne_filtree(mini):
    entete, *patients = cellules_brutes()
    assert list(mini.columns) == entete
    assert len(mini) == len(patients)


def test_virgule_decimale_dans_le_dosage(mini):
    dosage = mini.iloc[:, NB_CLINIQUES:]
    assert all(lecture(dosage[nom]) == "nombre" for nom in dosage.columns)
    assert mini.loc[0, "Act_d_1"] == pytest.approx(0.42)


def test_clinique_avec_virgule_reste_en_texte_tel_quel(mini):
    assert lecture(mini["Treatment_of_rhinitis"]) == "texte"
    assert "1,2" in set(mini["Treatment_of_rhinitis"])
    assert {"2, 5", "1,2,4"} <= set(mini["General_cofactors"])


def test_clinique_avec_lettre_reste_en_texte(mini):
    assert lecture(mini["Patient_ID"]) == "texte"
    assert lecture(mini["French_Residence_Department"]) == "texte"


def test_clinique_sans_virgule_ni_lettre_en_nombre(mini):
    assert lecture(mini["Age"]) == "nombre"
    assert mini.loc[0, "Age"] == 34


def test_seules_les_cellules_vides_manquent(mini):
    entete, *patients = cellules_brutes()
    for position, nom in enumerate(entete):
        vides = sum(ligne[position] == "" for ligne in patients)
        assert mini[nom].isna().sum() == vides, nom


def test_un_texte_na_reste_un_texte(tmp_path):
    fichier = tmp_path / "na.csv"
    texte = MINI.read_text(encoding="utf-8-sig").replace("deptA", "NA", 1)
    fichier.write_text(texte, encoding="utf-8")
    assert charger(fichier).loc[0, "French_Residence_Department"] == "NA"


def test_cellule_illisible_message_clair(tmp_path):
    fichier = tmp_path / "illisible.csv"
    texte = MINI.read_text(encoding="utf-8-sig").replace(";0,42;", ";0,4x;", 1)
    fichier.write_text(texte, encoding="utf-8")
    with pytest.raises(ValueError, match="Colonne Act_d_1"):
        charger(fichier)


def test_trois_types_de_puce(mini):
    assert set(mini["Chip_Type"]) == {"ALEX", "ISAC_V1", "ISAC_V2"}


def test_format_du_dictionnaire():
    dico = colonnes()
    assert list(dico.columns[:3]) == ["colonne", "bloc", "lecture"]
    puces = list(dico.columns[3:])
    assert puces and all(nom.startswith("puce_") for nom in puces)
    assert all(dico[nom].dtype == bool for nom in puces)
    assert list(dico["bloc"]) == ["clinique"] * NB_CLINIQUES + ["dosage"] * (len(dico) - NB_CLINIQUES)
    assert set(dico["lecture"]) <= {"nombre", "texte"}


def test_table_inventee_conforme_au_dictionnaire(mini):
    dico = colonnes().set_index("colonne")
    for nom in mini.columns:
        assert lecture(mini[nom]) == dico.loc[nom, "lecture"], nom
        for puce in ("ALEX", "ISAC_V1", "ISAC_V2"):
            renseignee = mini.loc[mini["Chip_Type"] == puce, nom].notna().any()
            assert renseignee == dico.loc[nom, f"puce_{puce}"], (nom, puce)


def test_attribut_git_des_donnees():
    if shutil.which("git") is None or not (RACINE / ".git").exists():
        pytest.skip("pas de dépôt git ici (archive décompressée)")
    attendu = tomllib.loads((RACINE / "kit" / "empreintes.toml").read_text(encoding="utf-8"))
    for nom in attendu["fichiers"]:
        sortie = subprocess.run(
            ["git", "check-attr", "binary", "text", "--", f"donnees/{nom}"],
            cwd=RACINE, capture_output=True, text=True, encoding="utf-8", check=True,
        ).stdout
        assert f"donnees/{nom}: binary: set" in sortie
        assert f"donnees/{nom}: text: unset" in sortie
