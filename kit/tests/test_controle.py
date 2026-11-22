"""Contrôle : RÉUSSITE sur le dépôt tel quel, ÉCHEC nommé dès qu'un point casse."""

import pytest

from kit import cli, controle
from kit.donnees import NOM_FICHIER, charger

from conftest import copier_kit, lancer_kit


@pytest.fixture
def copie(tmp_path):
    return copier_kit(tmp_path / "copie")


def derniere_ligne(texte):
    return texte.strip().splitlines()[-1]


def test_controle_hors_ligne_reussit(capsys):
    assert cli.main(["controle", "--hors-ligne"]) == 0
    assert derniere_ligne(capsys.readouterr().out) == "RÉUSSITE"


def test_donnees_alterees(copie):
    fichier = copie / "donnees" / NOM_FICHIER
    octets = bytearray(fichier.read_bytes())
    # Un seul octet change : le premier chiffre après la ligne d'en-tête.
    position = next(i for i in range(octets.index(b"\n"), len(octets)) if chr(octets[i]).isdigit())
    octets[position] = ord("1") if octets[position] != ord("1") else ord("2")
    fichier.write_bytes(bytes(octets))

    code, sortie = lancer_kit(copie, "controle", "--hors-ligne")

    assert code == 1
    assert derniere_ligne(sortie) == "ÉCHEC"
    assert f"donnees/{NOM_FICHIER} n'a pas l'empreinte publiée" in sortie
    assert "Que faire : restaure le dossier" in sortie


def test_fins_de_ligne_converties(copie, capsys):
    fichier = copie / "donnees" / NOM_FICHIER
    fichier.write_bytes(fichier.read_bytes().replace(b"\r\n", b"\n"))
    assert controle.controler(copie, hors_ligne=True) == 1
    assert f"donnees/{NOM_FICHIER} n'a pas l'empreinte publiée" in capsys.readouterr().out


def test_donnees_absentes(copie, capsys):
    (copie / "donnees" / NOM_FICHIER).unlink()
    assert controle.controler(copie, hors_ligne=True) == 1
    sortie = capsys.readouterr().out
    assert f"donnees/{NOM_FICHIER} est absent" in sortie
    assert derniere_ligne(sortie) == "ÉCHEC"


def test_dictionnaire_incoherent(copie):
    dico = copie / "kit" / "colonnes.csv"
    lignes = dico.read_text(encoding="utf-8").splitlines(keepends=True)
    numero = next(i for i, ligne in enumerate(lignes) if ",nombre," in ligne)
    nom = lignes[numero].split(",")[0]
    lignes[numero] = lignes[numero].replace(",nombre,", ",texte,")
    dico.write_text("".join(lignes), encoding="utf-8")

    bon, texte, que_faire = controle.verifier_dictionnaire(copie, charger(copie / "donnees" / NOM_FICHIER))

    assert not bon
    assert f"colonne {nom}" in texte
    assert "kit/" in que_faire


@pytest.mark.parametrize("equipe", ["accueil", "equipe-1", "equipe-9"])
def test_equipe_valide(tmp_path, equipe):
    (tmp_path / "equipe.toml").write_text(f'equipe = "{equipe}"\n', encoding="utf-8")
    assert controle.verifier_equipe(tmp_path)[0]


@pytest.mark.parametrize("contenu", [
    'equipe = "equipe-0"', 'equipe = "equipe-10"', 'equipe = "Equipe-1"', 'equipe = "les-meilleurs"',
    'equipe = ""', "equipe = 3", 'nom = "accueil"', "equipe = ",
])
def test_equipe_non_valide(tmp_path, contenu):
    (tmp_path / "equipe.toml").write_text(contenu + "\n", encoding="utf-8")
    bon, texte, que_faire = controle.verifier_equipe(tmp_path)
    assert not bon
    assert texte.startswith("équipe :") and "equipe.toml" in que_faire


def test_equipe_absente(tmp_path):
    bon, texte, _ = controle.verifier_equipe(tmp_path)
    assert not bon and "equipe.toml est absent" in texte


def test_installer_reussit(capsys):
    assert cli.main(["installer"]) == 0
    assert "Étape suivante : uv run kit controle" in capsys.readouterr().out


def test_aide_et_codes_de_sortie(capsys):
    assert cli.main([]) == 0
    aide = capsys.readouterr().out
    assert all(verbe in aide for verbe in ("installer", "cle", "controle", "agent"))
    assert cli.main(["inconnu"]) == 1
    assert cli.main(["controle", "--inconnue"]) == 1


def test_erreur_inattendue_sans_trace_python(monkeypatch, capsys):
    def panne(**_):
        raise RuntimeError("panne simulée")

    monkeypatch.setattr(controle, "controler", panne)
    assert cli.main(["controle"]) == 1
    sortie = capsys.readouterr()
    assert "Erreur inattendue : panne simulée" in sortie.out
    assert "Traceback" not in sortie.out + sortie.err

    assert cli.main(["controle", "--detail"]) == 1
    assert "Traceback" in capsys.readouterr().err


def test_traces_non_inscriptibles(copie, capsys):
    # Un fichier à la place du dossier : le cas se reproduit sur les trois systèmes.
    (copie / "traces").write_text("pas un dossier", encoding="utf-8")
    assert controle.controler(copie, hors_ligne=True) == 1
    sortie = capsys.readouterr().out
    assert "traces : le kit ne peut pas écrire dans le dossier traces/." in sortie
    assert "Que faire : vérifie que traces/ est un dossier" in sortie
    assert derniere_ligne(sortie) == "ÉCHEC"


def test_controle_ne_laisse_aucun_fichier(copie, capsys):
    assert controle.controler(copie, hors_ligne=True) == 0
    assert "traces : dossier traces/ inscriptible" in capsys.readouterr().out
    assert list((copie / "traces").iterdir()) == []
