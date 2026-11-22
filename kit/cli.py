"""La commande `uv run kit` : une seule entrée, un verbe par action.

Codes de sortie : 0 pour une réussite, 1 pour un échec. Une erreur
inattendue s'affiche en une phrase ; --detail montre la trace Python.
"""

import platform
import sys
import traceback
from importlib.metadata import version

from kit import cle, controle, pousser

AIDE = """Kit AllergyLab. Usage : uv run kit <commande>

  installer                 installe le kit, vérifie les données, demande la clé
  cle                       enregistre ou remplace la clé d'API
  controle                  vérifie l'installation point par point
  controle --hors-ligne     la même chose, sans appeler le modèle
  agent "question"          pose une question à l'agent de l'équipe
  pousser                   envoie les traces vers le dépôt de l'équipe
  evaluer [batterie.toml]   fait passer une batterie de questions à l'agent ;
                            sans batterie, toutes celles de equipe/questions/
    --exemple               la batterie d'exemple, sur la table inventée
    --modele nom            un modèle de kit/reglages.toml (developpement par défaut)
    --officielle            passe officielle : equipe/ doit être enregistré et poussé
  noter trace.json --corrige corrige.toml
                            note après coup une trace d'évaluation ; --json : sur une ligne
  bilan                     tableau des exécutions passées et de leur coût estimé

Ajoute --detail à une commande pour voir le détail d'une erreur inattendue ;
pour pousser, ce que git a répondu ; pour evaluer, ce que l'agent affiche."""

# Les options suivies d'une valeur : --modele officiel, --corrige corrige.toml.
AVEC_VALEUR = ("--modele", "--corrige")


def regler_console():
    """Écrit en UTF-8 sur les trois systèmes, pour que les accents passent sous Windows."""
    for flux in (sys.stdout, sys.stderr):
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(encoding="utf-8", errors="replace")


def installer(arguments, options):
    """Python et les dépendances sont déjà installés par `uv run` ; on le confirme, puis la clé."""
    print("Installation du kit AllergyLab")
    print(f"  OK     Python {platform.python_version()}")
    paquets = ", ".join(f"{nom} {version(nom)}" for nom in ("pandas", "smolagents", "anthropic"))
    print(f"  OK     dépendances : {paquets}")
    lignes = controle.verifier_donnees(controle.RACINE, controle.lire_attendu(controle.RACINE))
    for ligne in lignes:
        controle.afficher(*ligne)
    cle_acceptee = cle.installer()  # la demande si elle manque, et seulement dans un terminal
    if all(bon for bon, _, _ in lignes) and cle_acceptee:
        print("Installation terminée. Étape suivante : uv run kit controle")
        return 0
    print("Installation incomplète : corrige la ligne en échec, puis relance uv run kit installer.")
    return 1


def verifier(arguments, options):
    return controle.controler(hors_ligne="--hors-ligne" in options)


def enregistrer_cle(arguments, options):
    return cle.commande()


def agent(mots, options):
    if not mots:
        print('Il manque la question, entre guillemets : uv run kit agent "Combien de lignes compte le tableau ?"')
        return 1
    from kit import question  # importé ici seulement : smolagents et litellm sont longs à charger

    return question.poser(" ".join(mots))


def envoyer(arguments, options):
    return pousser.pousser(detail="--detail" in options)


def evaluer_batteries(arguments, options):
    from kit import evaluer

    return evaluer.evaluer(
        arguments, exemple="--exemple" in options, nom_modele=options.get("--modele", "developpement"),
        officielle="--officielle" in options, detail="--detail" in options,
    )


def noter_trace(arguments, options):
    if not arguments or "--corrige" not in options:
        print("Il manque la trace ou le corrigé : uv run kit noter <trace.json> --corrige <corrigé.toml>")
        return 1
    from kit import evaluer

    return evaluer.noter(arguments[0], options["--corrige"], en_json="--json" in options)


def faire_le_bilan(arguments, options):
    from kit import bilan

    return bilan.bilan()


# Chaque verbe : la fonction qui le traite, les options qu'il accepte, et le
# nombre d'arguments qu'il prend en plus (None : un texte libre, la question).
VERBES = {
    "installer": (installer, [], 0),
    "cle": (enregistrer_cle, [], 0),
    "controle": (verifier, ["--hors-ligne"], 0),
    "agent": (agent, [], None),
    "pousser": (envoyer, ["--detail"], 0),
    "evaluer": (evaluer_batteries, ["--exemple", "--modele", "--officielle", "--detail"], 1),
    "noter": (noter_trace, ["--corrige", "--json"], 1),
    "bilan": (faire_le_bilan, [], 0),
}


def separer(verbe, mots, permises):
    """(arguments, options) ; options vaut {nom : valeur, ou True}. Rend un message à la place si l'appel ne va pas."""
    arguments, options, reste = [], {}, iter(mots)
    for mot in reste:
        if not mot.startswith("--"):
            arguments.append(mot)
        elif mot not in permises:
            return f"Option inconnue pour {verbe} : {mot}. Lance uv run kit pour voir les options."
        elif mot in AVEC_VALEUR:
            valeur = next(reste, None)
            if valeur is None or valeur.startswith("--"):
                return f"L'option {mot} attend une valeur juste après elle. Lance uv run kit pour voir l'usage."
            options[mot] = valeur
        else:
            options[mot] = True
    return arguments, options


def main(argv=None):
    regler_console()
    arguments = sys.argv[1:] if argv is None else list(argv)
    detail = "--detail" in arguments
    arguments = [a for a in arguments if a != "--detail"]
    if not arguments or arguments[0] in ("-h", "--help", "aide"):
        print(AIDE)
        return 0
    verbe, mots = arguments[0], arguments[1:]
    if verbe not in VERBES:
        print(f"Commande inconnue : {verbe}. Voici les commandes du kit.\n")
        print(AIDE)
        return 1
    fonction, permises, nombre = VERBES[verbe]
    if nombre is None:  # la question, telle quelle
        lus = mots, {}
    else:
        lus = separer(verbe, mots, permises)
        if isinstance(lus, str):
            print(lus)
            return 1
        if len(lus[0]) > nombre:
            en_trop = " ".join(lus[0][nombre:])
            print(f"Argument en trop pour {verbe} : {en_trop}. Lance uv run kit pour voir l'usage.")
            return 1
        if detail and "--detail" in permises:
            lus[1]["--detail"] = True  # ce verbe s'en sert aussi : pousser y montre ce que git a répondu
    try:
        return fonction(*lus)
    except KeyboardInterrupt:
        print("\nInterrompu.")
        return 1
    except Exception as erreur:
        if detail:
            traceback.print_exc()
        else:
            print(f"Erreur inattendue : {erreur}")
            print("Relance la même commande avec --detail, et montre le résultat à l'animateur.")
        return 1
