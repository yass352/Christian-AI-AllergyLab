"""Environnement : ce qui change d'une machine à l'autre, et les règles du dépôt."""

import ast
import os
import re
import shutil
import subprocess
import tomllib

from kit.donnees import RACINE

from conftest import copier_kit, lancer_kit

# Les deux scripts d'avant la semaine sont rangés dans kit/ tels quels.
SCRIPTS_FOURNIS = {"tester-la-stack.py", "verifier-ma-machine.py"}


def test_chemin_avec_espaces_et_accents(tmp_path):
    dossier = copier_kit(tmp_path / "Dossier de l'élève" / "kit à tester")
    code, sortie = lancer_kit(dossier, "controle", "--hors-ligne")
    assert code == 0, sortie
    assert sortie.strip().splitlines()[-1] == "RÉUSSITE"


def test_dossier_sans_git(tmp_path):
    dossier = copier_kit(tmp_path / "archive")
    env = os.environ.copy()
    env["GIT_CEILING_DIRECTORIES"] = str(tmp_path)  # git ne cherche pas de dépôt plus haut
    assert not (dossier / ".git").exists()
    if shutil.which("git"):
        hors_depot = subprocess.run(["git", "rev-parse", "--git-dir"], cwd=dossier, env=env, capture_output=True)
        assert hors_depot.returncode != 0
    for commande in (["installer"], ["controle", "--hors-ligne"]):
        code, sortie = lancer_kit(dossier, *commande, env=env)
        assert code == 0, sortie


def test_affichage_des_accents(tmp_path):
    # Une console réglée sur un encodage sans accents, comme certaines sous Windows.
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "ascii"
    env.pop("PYTHONUTF8", None)
    code, sortie = lancer_kit(RACINE, env=env)
    assert code == 0
    assert "vérifie l'installation" in sortie


def test_gitignore():
    motifs = (RACINE / ".gitignore").read_text(encoding="utf-8").splitlines()
    for motif in (".venv/", "__pycache__/", ".pytest_cache/", ".DS_Store", ".env"):
        assert motif in motifs


def test_dependances_figees():
    projet = tomllib.loads((RACINE / "pyproject.toml").read_text(encoding="utf-8"))
    assert sorted(projet["project"]["dependencies"]) == ["anthropic", "pandas", "smolagents[litellm]==1.26.0"]
    assert projet["dependency-groups"] == {"dev": ["pytest"]}
    verrou = tomllib.loads((RACINE / "uv.lock").read_text(encoding="utf-8"))
    versions = {paquet["name"]: paquet["version"] for paquet in verrou["package"]}
    assert versions["smolagents"] == "1.26.0"
    assert (RACINE / ".python-version").read_text(encoding="utf-8").strip() == "3.12"


def test_fichiers_texte_ouverts_en_utf8():
    for fichier in (RACINE / "kit").rglob("*.py"):
        if fichier.name in SCRIPTS_FOURNIS:
            continue
        for noeud in ast.walk(ast.parse(fichier.read_text(encoding="utf-8"))):
            if not isinstance(noeud, ast.Call):
                continue
            nom = getattr(noeud.func, "attr", getattr(noeud.func, "id", None))
            if getattr(getattr(noeud.func, "value", None), "id", None) == "os":
                continue  # os.open rend un descripteur, sans encodage ; c'est open() qui le lit ou l'écrit
            mode = [a.value for a in noeud.args[1:2] if isinstance(a, ast.Constant)]
            if nom in ("open", "read_text", "write_text") and not any("b" in m for m in mode):
                cles = {mot.arg for mot in noeud.keywords}
                assert "encoding" in cles, f"{fichier.name}, ligne {noeud.lineno} : encoding manquant"


def test_aucun_script_shell():
    for fichier in RACINE.rglob("*"):
        if set(fichier.relative_to(RACINE).parts) & {".git", ".venv"}:
            continue
        assert fichier.suffix not in (".sh", ".bat", ".cmd", ".ps1"), fichier


def test_aucune_adresse_electronique():
    adresse = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
    for fichier in RACINE.rglob("*"):
        parties = set(fichier.relative_to(RACINE).parts)
        if parties & {".git", ".venv", "__pycache__", ".pytest_cache", "donnees"} or not fichier.is_file():
            continue
        texte = fichier.read_bytes().decode("utf-8", errors="ignore")
        assert not adresse.search(texte), fichier


def modeles_valides():
    """La liste MODELES de kit/tester-la-stack.py : les identifiants que ce script valide."""
    arbre = ast.parse((RACINE / "kit" / "tester-la-stack.py").read_text(encoding="utf-8"))
    for noeud in arbre.body:
        if isinstance(noeud, ast.Assign) and getattr(noeud.targets[0], "id", None) == "MODELES":
            return ast.literal_eval(noeud.value)
    raise AssertionError("MODELES introuvable dans tester-la-stack.py")


def test_deux_modeles_dans_les_reglages():
    reglages = tomllib.loads((RACINE / "kit" / "reglages.toml").read_text(encoding="utf-8"))
    modeles = reglages["modeles"]
    assert set(modeles) == {"developpement", "officiel"}
    assert sorted(m["identifiant"] for m in modeles.values()) == sorted(modeles_valides())
    assert all(m["entree"] > 0 and m["sortie"] > 0 for m in modeles.values())
    assert reglages["agent"]["etapes_max"] == 8
    re.compile(reglages["limite"]["motif"])


def test_un_seul_module_parle_au_modele():
    # Seul kit/modele.py importe un client du modèle ou écrit un identifiant de modèle.
    for fichier in (RACINE / "kit").rglob("*.py"):
        relatif = fichier.relative_to(RACINE).as_posix()
        if fichier.name in SCRIPTS_FOURNIS or "tests" in fichier.parts or relatif == "kit/modele.py":
            continue
        for noeud in ast.walk(ast.parse(fichier.read_text(encoding="utf-8"))):
            if isinstance(noeud, ast.Import):
                modules = [alias.name for alias in noeud.names]
            elif isinstance(noeud, ast.ImportFrom):
                modules = [noeud.module or ""] + [f"{noeud.module}.{alias.name}" for alias in noeud.names]
            else:
                modules = []
            for module in modules:
                assert not module.startswith(("anthropic", "litellm")), f"{relatif} importe {module}"
                assert not module.endswith("Model"), f"{relatif} importe {module}"
            if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
                assert "claude-" not in noeud.value, f"{relatif}, ligne {noeud.lineno} : identifiant de modèle"
