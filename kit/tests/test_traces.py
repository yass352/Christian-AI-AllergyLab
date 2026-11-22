"""Traces : écrites même en cas d'erreur, anonymes, sans collision de noms, liste de champs fermée.

Aucun appel au modèle : une fausse réponse en tient lieu. Chaque test écrit
dans un dépôt minimal, sous un dossier temporaire, jamais dans traces/ du kit.
"""

import getpass
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from kit import traces
from kit.donnees import RACINE

# La liste fermée de SPEC § 7, recopiée ici : un champ ajouté dans le code
# sans passer par la spec fait échouer test_champ_hors_liste_refuse.
CHAMPS_DE_LA_SPEC = (
    "format", "horodatage", "equipe", "kit", "etat", "commit", "modifie", "moteur",
    "modele", "question", "reponse", "etapes", "jetons", "cout_estime", "duree_s", "erreur",
)

REPONSE = {"statut": "reponse", "valeur": 12, "justification": "La table inventée compte douze lignes."}

# Une fausse clé, construite par morceaux : aucun fichier du dépôt ne contient
# le motif d'une clé en toutes lettres.
FAUSSE_CLE = "sk-" + "ant-api03-" + "AbCd1234" * 10

# Un dossier personnel et un nom d'utilisateur inventés, à la façon de Windows.
DOSSIER_FICTIF = "C:\\Users\\Élève Témoin"
UTILISATEUR_FICTIF = "eltemoin"


@pytest.fixture
def racine(tmp_path, monkeypatch):
    """Un dépôt minimal, hors de tout dépôt git : equipe.toml et equipe/."""
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    racine = tmp_path / "depot"
    equipe = racine / "equipe"
    (equipe / "outils").mkdir(parents=True)
    (equipe / "questions").mkdir()
    (racine / "equipe.toml").write_text('equipe = "equipe-3"\n', encoding="utf-8")
    (equipe / "agent.py").write_text("def repondre(question):\n    return None\n", encoding="utf-8")
    (equipe / "consigne.md").write_text("Réponds en une phrase.\n", encoding="utf-8")
    return racine


def poser(racine, question="Combien de lignes compte la table inventée ?"):
    """Un appel tracé, avec une fausse réponse à la place du modèle."""
    with traces.appel(question, "smolagents", "faux-modele", racine) as trace:
        trace.noter(reponse=REPONSE, jetons={"entree": 100, "sortie": 20}, cout_estime=0.0001)


def fichiers_de_traces(racine):
    return sorted((racine / "traces" / "appels").rglob("*.json"))


def lire_unique(racine):
    """La seule trace d'appel écrite : JSON valide, avec exactement les champs de la liste."""
    (chemin,) = fichiers_de_traces(racine)
    trace = json.loads(chemin.read_text(encoding="utf-8"))
    assert tuple(trace) == CHAMPS_DE_LA_SPEC
    return trace


def test_trace_d_un_appel(racine):
    poser(racine)
    trace = lire_unique(racine)
    assert trace["format"] == traces.FORMAT_APPEL
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", trace["horodatage"])
    assert trace["equipe"] == "equipe-3"
    assert trace["kit"] == traces.version_kit()
    assert trace["moteur"] == "smolagents" and trace["modele"] == "faux-modele"
    assert trace["reponse"] == REPONSE
    assert trace["erreur"] is None and trace["duree_s"] >= 0
    (chemin,) = fichiers_de_traces(racine)
    assert chemin.parent.name == trace["horodatage"][:10]


def test_deux_appels_meme_seconde(racine, monkeypatch):
    instant = datetime(2026, 11, 16, 9, 35, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(traces, "maintenant", lambda: instant)
    poser(racine)
    poser(racine)
    # Le pire cas : le deuxième tirage du suffixe retombe sur un nom déjà pris.
    tirages = iter(["0000aaaa", "0000aaaa", "0000bbbb"])
    monkeypatch.setattr(traces.secrets, "token_hex", lambda _: next(tirages))
    traces.ecrire_appel({"question": "première"}, racine, instant)
    traces.ecrire_appel({"question": "deuxième"}, racine, instant)

    chemins = fichiers_de_traces(racine)
    assert len(chemins) == 4
    assert {chemin.parent.name for chemin in chemins} == {"2026-11-16"}
    assert all(chemin.name.startswith("20261116T093512Z-") for chemin in chemins)
    premiere = racine / "traces" / "appels" / "2026-11-16" / "20261116T093512Z-0000aaaa.json"
    assert json.loads(premiere.read_text(encoding="utf-8"))["question"] == "première"


def test_champ_hors_liste_refuse(racine):
    assert traces.CHAMPS_APPEL == CHAMPS_DE_LA_SPEC

    with pytest.raises(ValueError, match="hors liste : utilisateur"):
        traces.ecrire_appel({"question": "q", "utilisateur": "x"}, racine)
    assert fichiers_de_traces(racine) == []

    # Dans un appel, le champ est refusé tout de suite et la trace s'écrit sans lui.
    with pytest.raises(ValueError, match="hors liste : machine"):
        with traces.appel("q", "smolagents", "faux-modele", racine) as trace:
            trace.noter(machine="x")
    trace = lire_unique(racine)
    assert "hors liste : machine" in trace["erreur"]


def test_trace_anonyme(racine, monkeypatch):
    monkeypatch.setattr(traces, "dossier_personnel", lambda: DOSSIER_FICTIF)
    monkeypatch.setattr(traces, "nom_utilisateur", lambda: UTILISATEUR_FICTIF)
    oblique = DOSSIER_FICTIF.replace("\\", "/")
    (racine / "equipe" / "outils" / "chemins.py").write_text(
        f'DOSSIER = r"{DOSSIER_FICTIF}\\kit"\nCLE = "{FAUSSE_CLE}"\n', encoding="utf-8"
    )
    question = f"Ici {UTILISATEUR_FICTIF}, avec la clé {FAUSSE_CLE}, dans {DOSSIER_FICTIF}\\kit"
    with pytest.raises(FileNotFoundError):
        with traces.appel(question, "smolagents", "faux-modele", racine) as trace:
            trace.noter(etapes=[{
                "code": f'open("{oblique}/kit/a.csv")',
                "resultat": f"{UTILISATEUR_FICTIF.upper()} a lu {DOSSIER_FICTIF!r}",
            }])
            raise FileNotFoundError(f"{DOSSIER_FICTIF}\\kit\\a.csv")

    (chemin,) = fichiers_de_traces(racine)
    texte = chemin.read_text(encoding="utf-8")
    # Trois absences : le dossier personnel, le nom d'utilisateur, la clé.
    for forme in (DOSSIER_FICTIF, oblique, DOSSIER_FICTIF.replace("\\", "\\\\"), "Témoin"):
        assert forme not in texte
    assert UTILISATEUR_FICTIF not in texte.lower()
    assert FAUSSE_CLE not in texte and "sk-ant" not in texte
    # Ce qui est remplacé est marqué, pas supprimé.
    trace = lire_unique(racine)
    assert trace["question"] == "Ici <utilisateur>, avec la clé <clé>, dans ~\\kit"
    assert trace["erreur"] == "FileNotFoundError : ~\\kit\\a.csv"

    # La copie de l'état est anonymisée de la même façon.
    copie = racine / "traces" / "etats" / trace["etat"] / "outils" / "chemins.py"
    assert copie.read_text(encoding="utf-8") == 'DOSSIER = r"~\\kit"\nCLE = "<clé>"\n'


def test_anonymiser_sur_cette_machine():
    dossier = Path.home()
    utilisateur = getpass.getuser()
    texte = traces.anonymiser(f"{dossier / 'kit'} {dossier.as_posix()}/kit {utilisateur}")
    assert str(dossier) not in texte and dossier.as_posix() not in texte
    assert not re.search(rf"(?<!\w){re.escape(utilisateur)}(?!\w)", texte, flags=re.IGNORECASE)


def test_anonymiser_mot_entier(monkeypatch):
    monkeypatch.setattr(traces, "dossier_personnel", lambda: "/home/temoin")
    monkeypatch.setattr(traces, "nom_utilisateur", lambda: "temoin")
    # Ni « temoins » ni le dossier d'un autre compte, /home/temoin2, ne sont touchés.
    assert traces.anonymiser("Temoin, temoins, /home/temoin/kit, /home/temoin2") == (
        "<utilisateur>, temoins, ~/kit, /home/temoin2"
    )


def test_trace_apres_exception(racine):
    with pytest.raises(RuntimeError):
        with traces.appel("q", "smolagents", "faux-modele", racine) as trace:
            trace.noter(etapes=[{"code": "len(tableau)", "resultat": "12"}])
            raise RuntimeError("panne simulée")
    trace = lire_unique(racine)
    assert trace["erreur"] == "RuntimeError : panne simulée"
    assert trace["etapes"] == [{"code": "len(tableau)", "resultat": "12"}]
    assert trace["reponse"] is None and trace["duree_s"] >= 0


def test_trace_apres_interruption(racine):
    with pytest.raises(KeyboardInterrupt):
        with traces.appel("q", "smolagents", "faux-modele", racine):
            raise KeyboardInterrupt
    assert lire_unique(racine)["erreur"] == "interrompu"


def test_valeurs_hors_json(racine):
    pytest.importorskip("numpy")
    import numpy

    reponse = {"statut": "reponse", "valeur": numpy.int64(12), "justification": float("nan")}
    traces.ecrire_appel({"reponse": reponse, "etapes": [object()]}, racine)
    trace = lire_unique(racine)
    assert trace["reponse"]["valeur"] == 12 and trace["reponse"]["justification"] == "nan"


def test_etat_copie_une_fois(racine):
    equipe = racine / "equipe"
    (equipe / "outils" / "compter.py").write_text("def compter(liste):\n    return len(liste)\n", encoding="utf-8")
    (equipe / "outils" / ".gitkeep").write_text("", encoding="utf-8")
    (equipe / "outils" / "__pycache__").mkdir()
    (equipe / "outils" / "__pycache__" / "compter.pyc").write_bytes(b"\x00\xff")
    (equipe / "questions" / "lot1.toml").write_text('[[question]]\nid = "essai"\n', encoding="utf-8")
    (equipe / "analyse").mkdir()
    (equipe / "analyse" / "notes.md").write_text("Hors de l'état.\n", encoding="utf-8")
    etats = racine / "traces" / "etats"

    premiere = traces.enregistrer_etat(racine)
    assert traces.enregistrer_etat(racine) == premiere
    copie = etats / premiere
    assert list(etats.iterdir()) == [copie]  # aucun dossier provisoire ne reste
    copies = sorted(f.relative_to(copie).as_posix() for f in copie.rglob("*") if f.is_file())
    assert copies == ["agent.py", "consigne.md", "outils/compter.py", "questions/lot1.toml"]
    assert traces.empreinte_etat(traces.lire_etat(copie)) == premiere

    # Une empreinte déjà copiée n'est jamais recopiée.
    (copie / "consigne.md").unlink()
    assert traces.enregistrer_etat(racine) == premiere
    assert not (copie / "consigne.md").exists()

    # Un travail modifié donne un nouvel état, que la trace cite.
    (equipe / "consigne.md").write_text("Une autre consigne.\n", encoding="utf-8")
    poser(racine)
    seconde = lire_unique(racine)["etat"]
    assert seconde != premiere
    assert sorted(dossier.name for dossier in etats.iterdir()) == sorted([premiere, seconde])


def test_etat_independant_des_fins_de_ligne(racine):
    agent = racine / "equipe" / "agent.py"
    avant = traces.empreinte_etat(traces.lire_etat(racine / "equipe"))
    # Sous Windows, le fichier de départ est déjà en CRLF : on repart de LF.
    en_lf = agent.read_bytes().replace(b"\r\n", b"\n")
    agent.write_bytes(en_lf.replace(b"\n", b"\r\n"))
    assert traces.empreinte_etat(traces.lire_etat(racine / "equipe")) == avant


def test_sans_git(racine, monkeypatch):
    assert traces.lire_git(racine) == (None, None)  # un dossier qui n'est pas un dépôt
    monkeypatch.setenv("PATH", "")  # git introuvable
    assert traces.lire_git(racine) == (None, None)
    poser(racine)
    trace = lire_unique(racine)
    assert trace["commit"] is None and trace["modifie"] is None
    assert trace["erreur"] is None and trace["etat"]


def test_commit_et_modifie(racine):
    if shutil.which("git") is None:
        pytest.skip("git absent de cette machine")

    def git(*arguments):
        identite = ["-c", "user.name=kit", "-c", "user.email=kit", "-c", "commit.gpgsign=false"]
        subprocess.run(["git", *identite, *arguments], cwd=racine, check=True, capture_output=True)

    git("init", "-q")
    git("add", "equipe.toml", "equipe")
    git("commit", "-q", "--no-verify", "-m", "état de départ")
    commit, modifie = traces.lire_git(racine)
    assert re.fullmatch(r"[0-9a-f]{40,64}", commit) and modifie is False
    poser(racine)  # écrire dans traces/ ne compte pas comme une modification
    assert traces.lire_git(racine) == (commit, False)
    (racine / "equipe" / "consigne.md").write_text("Une autre consigne.\n", encoding="utf-8")
    assert traces.lire_git(racine) == (commit, True)


def test_equipe_non_valide_non_recopiee(racine):
    (racine / "equipe.toml").write_text('equipe = "prenom-nom"\n', encoding="utf-8")
    poser(racine)
    assert lire_unique(racine)["equipe"] is None


def test_aucun_motif_de_cle_dans_le_depot():
    for fichier in RACINE.rglob("*"):
        parties = set(fichier.relative_to(RACINE).parts)
        if parties & {".git", ".venv", "__pycache__", ".pytest_cache", "donnees"} or not fichier.is_file():
            continue
        texte = fichier.read_bytes().decode("utf-8", errors="ignore")
        assert not traces.MOTIF_CLE.search(texte), fichier
