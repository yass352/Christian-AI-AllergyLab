"""La clé d'API : rangée hors du dépôt, jamais affichée, jamais dans l'environnement ni dans une trace.

Aucun test ne lit la vraie clé : conftest.py donne à chacun un dossier
personnel vide pour la clé, et retire la variable ALLERGYLAB_CLE.
"""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from kit import cle, cli, controle, question
from kit.donnees import RACINE

from conftest import FAUSSE_CLE, FICHIER_DE_LA_CLE, copier_kit, lire_trace, reponse_finale

REPONSE = {"statut": "reponse", "valeur": 12, "justification": "Une réponse inventée pour le test."}

# Une autre fausse clé, construite par morceaux elle aussi.
VARIABLE_CLE = "sk-" + "ant-variable-" + "0" * 24


def test_cle_hors_du_depot(tmp_path, monkeypatch):
    maison = tmp_path / "Dossier de l'élève"
    monkeypatch.setattr(cle, "fichier", FICHIER_DE_LA_CLE)  # le vrai calcul du chemin
    monkeypatch.setattr(Path, "home", lambda: maison)

    chemin = cle.enregistrer(f"  {FAUSSE_CLE}\n")

    assert chemin == maison / ".allergylab" / "cle"
    assert not chemin.resolve().is_relative_to(RACINE.resolve())
    assert chemin.read_text(encoding="utf-8") == FAUSSE_CLE + "\n"
    if os.name == "posix":  # sous Windows, les droits ne se règlent pas ainsi
        assert stat.S_IMODE(chemin.stat().st_mode) == 0o600
    for fichier in RACINE.rglob("*"):
        caches = {".git", ".venv", "__pycache__", ".pytest_cache"}  # hors du dépôt publié
        if caches & set(fichier.relative_to(RACINE).parts) or not fichier.is_file():
            continue
        assert FAUSSE_CLE.encode() not in fichier.read_bytes(), fichier

    # Un dossier personnel qui serait le dépôt lui-même : refusé, et rien n'est écrit.
    monkeypatch.setattr(Path, "home", lambda: RACINE)
    with pytest.raises(cle.CleRefusee, match="serait dans le dépôt"):
        cle.enregistrer(FAUSSE_CLE)
    assert not (RACINE / ".allergylab").exists()


def test_fichier_puis_variable(monkeypatch):
    assert cle.trouver() == (None, None)
    monkeypatch.setenv(cle.VARIABLE, f" {VARIABLE_CLE} ")
    assert cle.trouver() == (VARIABLE_CLE, f"variable {cle.VARIABLE}")
    cle.enregistrer(FAUSSE_CLE)
    assert cle.trouver() == (FAUSSE_CLE, "fichier du dossier personnel")  # uv run kit cle a le dernier mot


@pytest.mark.parametrize("texte", ["", "bonjour", "sk-" + "ant-court",f"{FAUSSE_CLE} {FAUSSE_CLE}", "hf_" + "x" * 30])
def test_cle_mal_formee_refusee(texte):
    with pytest.raises(cle.CleRefusee, match="forme d'une clé"):
        cle.enregistrer(texte)
    assert not cle.fichier().exists()


def test_kit_cle_dans_un_terminal(monkeypatch, capsys):
    monkeypatch.setattr(cle, "interactif", lambda: True)
    monkeypatch.setattr(cle.getpass, "getpass", lambda invite: FAUSSE_CLE)
    assert cli.main(["cle"]) == 0
    assert "Clé enregistrée" in capsys.readouterr().out
    assert cli.main(["cle"]) == 0
    sortie = capsys.readouterr().out
    assert "Clé remplacée" in sortie and "Étape suivante : uv run kit controle" in sortie
    assert FAUSSE_CLE not in sortie and FAUSSE_CLE[:12] not in sortie
    assert cle.lire() == FAUSSE_CLE


def test_kit_cle_sans_terminal(monkeypatch, capsys):
    assert cli.main(["cle"]) == 1
    assert f"la variable {cle.VARIABLE} est vide" in capsys.readouterr().out
    monkeypatch.setenv(cle.VARIABLE, FAUSSE_CLE)
    assert cli.main(["cle"]) == 0
    assert FAUSSE_CLE not in capsys.readouterr().out
    assert cle.fichier().read_text(encoding="utf-8").strip() == FAUSSE_CLE


def test_installer_sans_terminal_ni_variable(capsys):
    assert cli.main(["installer"]) == 0
    sortie = capsys.readouterr().out
    assert "clé d'API : absente. Lance uv run kit cle" in sortie
    assert "Installation terminée" in sortie
    assert not cle.fichier().exists()


def test_installer_demande_la_cle(monkeypatch, capsys):
    monkeypatch.setattr(cle, "interactif", lambda: True)
    monkeypatch.setattr(cle.getpass, "getpass", lambda invite: FAUSSE_CLE)
    assert cli.main(["installer"]) == 0
    assert "clé d'API : enregistrée dans" in capsys.readouterr().out
    assert cle.lire() == FAUSSE_CLE
    # Relancé, il ne la redemande pas.
    monkeypatch.setattr(cle.getpass, "getpass", lambda invite: pytest.fail("clé redemandée"))
    assert cli.main(["installer"]) == 0
    assert "clé d'API : présente (fichier du dossier personnel)" in capsys.readouterr().out


def test_installer_cle_collee_refusee(monkeypatch, capsys):
    monkeypatch.setattr(cle, "interactif", lambda: True)
    monkeypatch.setattr(cle.getpass, "getpass", lambda invite: "pas une clé")
    assert cli.main(["installer"]) == 1
    assert "ÉCHEC  clé d'API : ce texte n'a pas la forme" in capsys.readouterr().out


def test_controle_sans_cle(capsys):
    # La contre-épreuve de SPEC § 9 : clé retirée, ÉCHEC, et la cause est nommée.
    assert controle.controler(RACINE) == 1
    sortie = capsys.readouterr().out
    assert "ÉCHEC  clé d'API : absente." in sortie
    assert "Que faire : lance uv run kit cle" in sortie
    assert "appel au modèle : non tenté, faute de clé" in sortie
    assert sortie.strip().splitlines()[-1] == "ÉCHEC"


def test_controle_cle_dans_un_fichier_du_depot(tmp_path, capsys):
    if shutil.which("git") is None:
        pytest.skip("git absent de cette machine")
    copie = copier_kit(tmp_path / "copie")
    subprocess.run(["git", "init", "-q"], cwd=copie, check=True)
    subprocess.run(["git", "add", "kit", "equipe.toml"], cwd=copie, check=True)
    assert controle.verifier_cle_hors_depot(copie)[0]
    # Un fichier pas encore suivi, qu'un « git add . » ajouterait.
    (copie / "notes.txt").write_text(f"ma clé : {FAUSSE_CLE}\n", encoding="utf-8")

    assert controle.controler(copie, hors_ligne=True) == 1
    sortie = capsys.readouterr().out
    assert "ÉCHEC  clé dans le dépôt : notes.txt contient ce qui ressemble à une clé d'API." in sortie
    assert FAUSSE_CLE not in sortie


def test_controle_hors_d_un_depot_git(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    bon, texte, _ = controle.verifier_cle_hors_depot(copier_kit(tmp_path / "archive"))
    assert bon and "pas de dépôt git ici" in texte


@pytest.mark.parametrize("moteur", ["smolagents", "boucle_maison"])
def test_cle_en_parametre(moteur, faux_modele, cle_enregistree, depot, brancher, capsys):
    faux_modele.programmer(reponse_finale(moteur, REPONSE))
    brancher(moteur)

    assert question.poser(f"Ma clé est-elle {FAUSSE_CLE} ?", depot) == 0

    assert faux_modele.cles == [FAUSSE_CLE]  # elle est bien arrivée à l'API, en paramètre du client
    assert all(FAUSSE_CLE not in valeur for valeur in os.environ.values())
    assert FAUSSE_CLE not in capsys.readouterr().out
    texte = next((depot / "traces").rglob("*.json")).read_text(encoding="utf-8")
    assert FAUSSE_CLE not in texte
    assert lire_trace(depot)["question"] == "Ma clé est-elle <clé> ?"
