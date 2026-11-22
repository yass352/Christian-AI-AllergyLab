"""La clé d'API : où elle se range, comment le kit la lit.

La clé vit hors du dépôt, dans le fichier .allergylab/cle du dossier
personnel. Une clé qui n'est pas dans le dossier du dépôt ne peut pas partir
dans un commit, même par `git add .` (SPEC § 4).

Sans terminal interactif (une intégration continue, par exemple), la clé se
lit dans la variable ALLERGYLAB_CLE. Le fichier passe avant la variable :
`uv run kit cle` a toujours le dernier mot.

Le kit ne met jamais la clé dans une variable d'environnement, ne l'affiche
jamais, ne l'écrit dans aucune trace. Il la passe en paramètre au client qui
appelle le modèle (kit/modele.py).
"""

import getpass
import os
import re
import sys
from pathlib import Path

from kit.donnees import RACINE

VARIABLE = "ALLERGYLAB_CLE"

# Le début d'une clé d'API d'Anthropic. Écrit en deux morceaux : ainsi une
# recherche de ce début dans les fichiers du dépôt ne trouve que de vraies fuites.
PREFIXE = "sk-" + "ant-"

# La forme d'une clé d'API d'Anthropic.
FORME = re.compile(PREFIXE + r"[A-Za-z0-9_-]{20,}")

# Tout ce qui ressemble à une clé d'API : celles d'Anthropic et de la plupart
# des fournisseurs commencent par « sk- », celles de Hugging Face par « hf_ ».
MOTIF_CLE = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|hf_[A-Za-z0-9]{20,})")

INVITE = "Colle la clé d'API, puis appuie sur Entrée (rien ne s'affiche, c'est normal) : "


class CleAbsente(Exception):
    """Aucune clé : ni dans le fichier, ni dans la variable."""

    texte = "aucune clé d'API n'est enregistrée."
    que_faire = "lance uv run kit cle, puis colle la clé que l'animateur t'a donnée."

    def __str__(self):
        return f"Clé d'API absente : {self.texte} Que faire : {self.que_faire}"


class CleRefusee(ValueError):
    """Un texte qui n'a pas la forme d'une clé, ou un fichier qui serait dans le dépôt."""


def fichier():
    """Le fichier de la clé, dans le dossier personnel."""
    return Path.home() / ".allergylab" / "cle"


def interactif():
    """Vrai si quelqu'un peut taper au clavier dans ce terminal."""
    try:
        if sys.stdin is None or not sys.stdin.isatty():
            return False
        if sys.platform != "win32":
            return True
        # Sous Windows, isatty() dit vrai aussi pour le périphérique nul (une
        # entrée redirigée vers NUL) : le kit attendrait une clé que personne
        # ne peut taper. Seule une vraie console a un mode de console.
        import ctypes
        import msvcrt

        poignee = ctypes.c_void_p(msvcrt.get_osfhandle(sys.stdin.fileno()))
        mode = ctypes.c_uint32()
        return bool(ctypes.windll.kernel32.GetConsoleMode(poignee, ctypes.byref(mode)))
    except (AttributeError, OSError, ValueError):
        return False


def trouver():
    """(clé, provenance) : le fichier d'abord, puis la variable ; (None, None) sans clé."""
    try:
        texte = fichier().read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        texte = ""
    if texte:
        return texte, "fichier du dossier personnel"
    texte = os.environ.get(VARIABLE, "").strip()
    if texte:
        return texte, f"variable {VARIABLE}"
    return None, None


def lire():
    """La clé, ou None."""
    return trouver()[0]


def exiger():
    """La clé ; sans clé, une erreur qui dit quoi faire."""
    cle = lire()
    if cle is None:
        raise CleAbsente()
    return cle


def enregistrer(texte):
    """Range la clé dans le fichier du dossier personnel, lisible du seul compte. Rend le chemin."""
    cle = texte.strip()
    if not FORME.fullmatch(cle):
        raise CleRefusee(
            f"ce texte n'a pas la forme d'une clé d'API, qui commence par {PREFIXE} et ne contient "
            "pas d'espace. Recopie la clé en entier, puis relance uv run kit cle."
        )
    chemin = fichier()
    if chemin.resolve().is_relative_to(RACINE.resolve()):
        raise CleRefusee(
            f"le fichier {chemin} serait dans le dépôt, et la clé pourrait partir dans un commit. "
            "Clone le dépôt dans un sous-dossier de ton dossier personnel, puis relance uv run kit cle."
        )
    chemin.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Créé d'emblée avec les droits 600 : à aucun moment un autre compte ne peut le lire.
    descripteur = os.open(chemin, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with open(descripteur, "w", encoding="utf-8", newline="\n") as sortie:
        sortie.write(cle + "\n")
    os.chmod(chemin, 0o600)  # si le fichier existait déjà avec d'autres droits
    return chemin


def commande():
    """`uv run kit cle` : enregistre ou remplace la clé. Rend le code de sortie."""
    if interactif():
        texte = getpass.getpass(INVITE)
    else:
        texte = os.environ.get(VARIABLE, "")
        if not texte.strip():
            print(
                f"Pas de terminal interactif, et la variable {VARIABLE} est vide. Lance "
                f"uv run kit cle dans un terminal, ou donne la clé dans la variable {VARIABLE}."
            )
            return 1
    deja = fichier().is_file()
    try:
        chemin = enregistrer(texte)
    except CleRefusee as erreur:
        print(f"Clé refusée : {erreur}")
        return 1
    print(f"Clé {'remplacée' if deja else 'enregistrée'} dans {chemin}, hors du dépôt.")
    print("Étape suivante : uv run kit controle")
    return 0


def installer():
    """L'étape de la clé dans `uv run kit installer`. Rend False seulement si une clé collée est refusée."""
    cle, provenance = trouver()
    if cle:
        print(f"  OK     clé d'API : présente ({provenance})")
        return True
    if not interactif():
        print(
            f"  --     clé d'API : absente. Lance uv run kit cle dans un terminal, "
            f"ou donne la clé dans la variable {VARIABLE}."
        )
        return True
    texte = getpass.getpass("  " + INVITE)
    if not texte.strip():
        print("  --     clé d'API : aucune clé collée. Lance uv run kit cle quand tu l'auras.")
        return True
    try:
        chemin = enregistrer(texte)
    except CleRefusee as erreur:
        print(f"  ÉCHEC  clé d'API : {erreur}")
        return False
    print(f"  OK     clé d'API : enregistrée dans {chemin}, hors du dépôt")
    return True
