"""Les traces : ce que le kit écrit seul, à chaque exécution, dans traces/.

Trois sortes d'écrits (SPEC § 7) :
- la trace d'un appel : un fichier JSON par exécution, dans
  traces/appels/<jour>/, nommé par l'horodatage UTC et un suffixe tiré au
  hasard. Aucun fichier commun : deux machines ne se gênent jamais ;
- la trace d'une évaluation : un fichier JSON par batterie, nommé de la
  même façon, dans traces/evaluations/<jour>/ ;
- l'état du travail de l'équipe : une copie de equipe/ dans
  traces/etats/<empreinte>/, faite une seule fois par empreinte.

Rien qui porte un nom : les champs forment une liste fermée, et tout texte
est anonymisé avant d'être écrit.

Usage, dans le code qui pose une question à l'agent :

    with traces.appel(question, moteur, modele) as trace:
        ...
        trace.noter(reponse=reponse, etapes=etapes, jetons=jetons, cout_estime=cout)

La trace s'écrit à la sortie du bloc, même si l'appel lève une exception ou
est interrompu (Ctrl+C).
"""

import getpass
import hashlib
import json
import math
import numbers
import os
import re
import secrets
import shutil
import subprocess
import time
import tomllib
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from kit import cle
from kit.cle import MOTIF_CLE
from kit.controle import EQUIPE_VALIDE
from kit.donnees import RACINE

# Version du format des traces d'appel : elle change avec la liste des champs.
FORMAT_APPEL = 1

# La liste fermée des champs d'une trace d'appel. Un champ nouveau se décide
# dans SPEC.md, pas ici.
CHAMPS_APPEL = (
    "format", "horodatage", "equipe", "kit", "etat", "commit", "modifie", "moteur",
    "modele", "question", "reponse", "etapes", "jetons", "cout_estime", "duree_s", "erreur",
)

# Version du format des traces d'évaluation : elle change avec la liste des champs.
FORMAT_EVALUATION = 1

# La liste fermée des champs d'une trace d'évaluation, puis celle de chaque
# question. Aucune valeur attendue, aucun type de question, aucune tolérance :
# un corrigé ne doit pas pouvoir se lire dans un dépôt d'équipe. Un champ
# nouveau se décide dans SPEC.md, pas ici.
CHAMPS_EVALUATION = (
    "format", "horodatage", "equipe", "kit", "etat", "commit", "modifie", "officielle", "modele",
    "batterie", "table", "justesse", "abstention", "verdicts", "frugalite", "erreur", "questions",
)
CHAMPS_QUESTION = ("id", "texte", "reponse", "etapes", "jetons", "cout_estime", "duree_s", "erreur", "verdict")

# Ce qui, dans equipe/, fait l'état du travail de l'équipe.
CONTENU_ETAT = ("agent.py", "consigne.md", "outils", "questions")


def maintenant():
    """L'instant présent, en UTC. Une fonction à part, pour que les tests fixent l'heure."""
    return datetime.now(timezone.utc)


# --- Anonymiser ---------------------------------------------------------------


def dossier_personnel():
    try:
        return str(Path.home())
    except RuntimeError:
        return None


def nom_utilisateur():
    try:
        return getpass.getuser()
    except Exception:  # selon le système : OSError, KeyError, ImportError
        return None


def anonymiser(texte):
    """Remplace le dossier personnel par ~, le nom d'utilisateur par <utilisateur>, toute clé par <clé>."""
    dossier = dossier_personnel()
    parties = [re.escape(partie) for partie in re.split(r"[\\/]+", dossier or "") if partie]
    if parties:
        # Séparateurs / ou \, simples ou doublés : C:\Users\x, C:/Users/x, "C:\\Users\\x".
        motif = (r"[\\/]+" if dossier[0] in "\\/" else "") + r"[\\/]+".join(parties) + r"(?![\w-])"
        texte = re.sub(motif, "~", texte, flags=re.IGNORECASE)
    texte = MOTIF_CLE.sub("<clé>", texte)
    # Les clés en usage, même si elles n'ont pas la forme attendue.
    for en_usage in (cle.lire(), os.environ.get("ANTHROPIC_API_KEY", "").strip()):
        if en_usage and len(en_usage) >= 8:
            texte = texte.replace(en_usage, "<clé>")
    utilisateur = nom_utilisateur()
    if utilisateur and len(utilisateur) >= 2:  # en mot entier : « a » n'efface pas tous les « a »
        texte = re.sub(rf"(?<!\w){re.escape(utilisateur)}(?!\w)", "<utilisateur>", texte, flags=re.IGNORECASE)
    return texte


def nettoyer(valeur):
    """Copie de valeur prête pour JSON : chaque texte anonymisé, tout objet inconnu mis en texte."""
    if isinstance(valeur, dict):
        return {anonymiser(str(nom)): nettoyer(v) for nom, v in valeur.items()}
    if isinstance(valeur, (list, tuple)):
        return [nettoyer(v) for v in valeur]
    if valeur is None or isinstance(valeur, bool):
        return valeur
    if isinstance(valeur, numbers.Integral):  # y compris les entiers de numpy
        return int(valeur)
    if isinstance(valeur, numbers.Real) and math.isfinite(valeur):
        return float(valeur)
    return anonymiser(str(valeur))  # texte, NaN, objet d'une bibliothèque…


# --- Situer une exécution -----------------------------------------------------


def lire_equipe(racine=RACINE):
    """L'identifiant de equipe.toml, ou None. Un identifiant non valide n'est pas recopié : ce pourrait être un nom."""
    try:
        equipe = tomllib.loads((racine / "equipe.toml").read_text(encoding="utf-8")).get("equipe")
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return None
    return equipe if isinstance(equipe, str) and EQUIPE_VALIDE.fullmatch(equipe) else None


def version_kit():
    try:
        return version("allergylab-kit")
    except PackageNotFoundError:
        return None


def lire_git(racine=RACINE):
    """(commit, modifie) : le commit courant, et s'il y a des modifications non enregistrées.

    Rend (None, None) sans git, hors d'un dépôt ou dans un dépôt sans commit :
    le kit tourne aussi depuis une archive décompressée. traces/ ne compte pas
    dans les modifications, puisque le kit y écrit à chaque exécution.
    """
    def git(*arguments):
        # --no-optional-locks : ne bloque pas un git lancé au même moment par l'étudiant.
        resultat = subprocess.run(
            ["git", "--no-optional-locks", *arguments], cwd=racine,
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
        )
        resultat.check_returncode()
        return resultat.stdout

    try:
        haut, commit = git("rev-parse", "--show-toplevel", "HEAD").splitlines()
        if not Path(haut).samefile(racine):
            return None, None  # un dépôt plus haut dans l'arborescence, pas celui du kit
        modifie = git("status", "--porcelain", "--", ".", ":(exclude)traces").strip() != ""
        return commit, modifie
    except (OSError, ValueError, subprocess.SubprocessError):
        return None, None


# --- L'état du travail --------------------------------------------------------


def lire_etat(dossier):
    """Les fichiers texte de l'état, anonymisés : {chemin relatif : texte}.

    dossier est equipe/, ou une copie d'état. Sont laissés de côté : les
    fichiers cachés, __pycache__, les liens, ce qui n'est pas du texte UTF-8.
    Les fins de ligne sont ramenées à \\n : un même travail a la même
    empreinte sous Windows, macOS et Linux.
    """
    etat = {}
    for nom in CONTENU_ETAT:
        chemin = dossier / nom
        for fichier in sorted(chemin.rglob("*")) if chemin.is_dir() else [chemin]:
            relatif = fichier.relative_to(dossier)
            cache = any(partie.startswith(".") or partie == "__pycache__" for partie in relatif.parts)
            if cache or fichier.is_symlink() or not fichier.is_file():
                continue
            try:
                texte = fichier.read_bytes().decode("utf-8")
            except UnicodeDecodeError:
                continue
            etat[relatif.as_posix()] = anonymiser(texte.replace("\r\n", "\n"))
    return etat


def empreinte_etat(etat):
    """Les 16 premiers caractères du SHA-256 des chemins et des textes de l'état."""
    texte = json.dumps(etat, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()[:16]


def enregistrer_etat(racine=RACINE):
    """Copie l'état de equipe/ dans traces/etats/<empreinte>/, s'il n'y est pas déjà. Rend l'empreinte."""
    etat = lire_etat(racine / "equipe")
    empreinte = empreinte_etat(etat)
    dossier = racine / "traces" / "etats" / empreinte
    if dossier.exists():
        return empreinte
    # La copie se fait à côté, puis on la renomme : une copie interrompue ne
    # passe jamais pour complète.
    provisoire = dossier.with_name(f".{empreinte}-{secrets.token_hex(4)}")
    try:
        provisoire.mkdir(parents=True)
        for chemin, texte in etat.items():
            cible = provisoire / chemin
            cible.parent.mkdir(parents=True, exist_ok=True)
            cible.write_text(texte, encoding="utf-8", newline="\n")
        provisoire.rename(dossier)
    except OSError:
        if not dossier.exists():  # sinon, une autre exécution l'a copié au même moment
            raise
    finally:
        shutil.rmtree(provisoire, ignore_errors=True)
    return empreinte


# --- La trace d'un appel ------------------------------------------------------


def verifier_champs(champs, liste=CHAMPS_APPEL):
    hors_liste = [nom for nom in champs if nom not in liste]
    if hors_liste:
        raise ValueError(
            f"Champ de trace hors liste : {', '.join(hors_liste)}. La liste des champs est "
            "fermée ; un champ nouveau se décide dans SPEC.md, pas dans le code."
        )


def ecrire_appel(champs, racine=RACINE, instant=None):
    """Écrit la trace d'un appel et rend son chemin. Un champ absent vaut null."""
    verifier_champs(champs)
    instant = instant or maintenant()
    trace = {nom: nettoyer(champs.get(nom)) for nom in CHAMPS_APPEL}
    trace["format"] = FORMAT_APPEL
    return ecrire(trace, racine / "traces" / "appels", instant)


def ecrire_evaluation(champs, racine=RACINE, instant=None):
    """Écrit la trace d'une évaluation et rend son chemin. Un champ absent vaut null, à chaque niveau."""
    verifier_champs(champs, CHAMPS_EVALUATION)
    questions = champs.get("questions") or []
    for question in questions:
        verifier_champs(question, CHAMPS_QUESTION)
    instant = instant or maintenant()
    trace = {nom: nettoyer(champs.get(nom)) for nom in CHAMPS_EVALUATION}
    trace["format"] = FORMAT_EVALUATION
    trace["questions"] = [{nom: nettoyer(question.get(nom)) for nom in CHAMPS_QUESTION} for question in questions]
    return ecrire(trace, racine / "traces" / "evaluations", instant)


def ecrire(trace, dossier, instant):
    """Écrit trace dans dossier/<jour>/, dans un fichier neuf nommé par l'horodatage. Rend son chemin."""
    trace["horodatage"] = f"{instant:%Y-%m-%dT%H:%M:%SZ}"
    texte = json.dumps(trace, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    dossier = dossier / f"{instant:%Y-%m-%d}"
    dossier.mkdir(parents=True, exist_ok=True)
    while True:
        # Un suffixe tiré à chaque fichier : rien qui désigne une machine ou une personne.
        chemin = dossier / f"{instant:%Y%m%dT%H%M%SZ}-{secrets.token_hex(4)}.json"
        try:
            # Mode « x » : un fichier existant n'est jamais écrasé, on tire un autre suffixe.
            with open(chemin, "x", encoding="utf-8", newline="\n") as fichier:
                fichier.write(texte)
            return chemin
        except FileExistsError:
            continue


class Trace:
    """Les champs d'une trace d'appel, notés au fil de l'exécution."""

    liste = CHAMPS_APPEL

    def __init__(self, **champs):
        self.champs = {}
        self.chemin = None  # le fichier de la trace, une fois écrit
        self.noter(**champs)

    def noter(self, **champs):
        """Ajoute des champs. Un champ hors de la liste fermée est refusé tout de suite."""
        verifier_champs(champs, self.liste)
        self.champs.update(champs)


class TraceEvaluation(Trace):
    """Les champs d'une trace d'évaluation ; les questions s'ajoutent une à une à champs["questions"]."""

    liste = CHAMPS_EVALUATION


def decrire(erreur):
    if isinstance(erreur, KeyboardInterrupt):
        return "interrompu"
    return f"{type(erreur).__name__} : {erreur}"


def situer(trace, racine):
    """Note dans la trace l'équipe, la version du kit, le commit et l'état du travail."""
    trace.noter(equipe=lire_equipe(racine), kit=version_kit())
    commit, modifie = lire_git(racine)
    trace.noter(commit=commit, modifie=modifie)
    trace.noter(etat=enregistrer_etat(racine))


@contextmanager
def evaluation(racine=RACINE, **champs):
    """Trace l'évaluation faite dans le bloc with. La trace s'écrit en sortie, quoi qu'il arrive."""
    debut = maintenant()
    trace = TraceEvaluation(questions=[], **champs)
    try:
        situer(trace, racine)
        yield trace
    except BaseException as erreur:  # BaseException : Ctrl+C compris
        if trace.champs.get("erreur") is None:
            trace.noter(erreur=decrire(erreur))
        raise
    finally:
        trace.chemin = ecrire_evaluation(trace.champs, racine, debut)


@contextmanager
def appel(question, moteur, modele, racine=RACINE):
    """Trace l'appel fait dans le bloc with. La trace s'écrit en sortie, quoi qu'il arrive."""
    debut, chrono = maintenant(), time.monotonic()
    trace = Trace(question=question, moteur=moteur, modele=modele)
    try:
        situer(trace, racine)
        yield trace
    except BaseException as erreur:  # BaseException : Ctrl+C compris
        if trace.champs.get("erreur") is None:
            trace.noter(erreur=decrire(erreur))
        raise
    finally:
        trace.noter(duree_s=round(time.monotonic() - chrono, 2))
        trace.chemin = ecrire_appel(trace.champs, racine, debut)
