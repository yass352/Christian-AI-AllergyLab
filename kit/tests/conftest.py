"""Outils communs aux tests : copier le kit ailleurs et l'y faire tourner, et un faux modèle.

Les tests ne touchent jamais à donnees/ : ce qu'ils altèrent, ils l'altèrent
dans une copie, sous un dossier temporaire. Ils ne lisent jamais la vraie
clé, et n'appellent jamais le modèle : le faux modèle répond à sa place.
"""

import json
import os
import shutil
import socket
import subprocess
import sys

import httpx
import httpx2
import pytest

from kit import cle
from kit.donnees import RACINE

# Une fausse clé, construite par morceaux : aucun fichier du dépôt ne contient
# le motif d'une clé en toutes lettres.
FAUSSE_CLE = "sk-" + "ant-api03-" + "AbCd1234" * 10

# Le vrai calcul du chemin de la clé, avant que chaque test ne le remplace.
FICHIER_DE_LA_CLE = cle.fichier

# Lance la commande kit depuis le dossier courant, après avoir vérifié que
# c'est bien le kit de ce dossier qui est importé, et pas celui du dépôt.
LANCEUR = (
    "import pathlib, sys, kit; "
    "assert pathlib.Path(kit.__file__).resolve().parent.parent == pathlib.Path.cwd().resolve(); "
    "from kit.cli import main; sys.exit(main(sys.argv[1:]))"
)


def copier_kit(destination):
    """Copie dans destination ce qu'il faut pour faire tourner le kit, sans .git."""
    shutil.copytree(RACINE / "kit", destination / "kit", ignore=shutil.ignore_patterns("__pycache__", "tests"))
    shutil.copytree(RACINE / "donnees", destination / "donnees")
    shutil.copy2(RACINE / "equipe.toml", destination / "equipe.toml")
    return destination


def lancer_kit(dossier, *arguments, env=None):
    """Lance `kit <arguments>` dans dossier ; rend le code de sortie et la sortie décodée."""
    resultat = subprocess.run(
        [sys.executable, "-c", LANCEUR, *arguments],
        cwd=dossier,
        capture_output=True,
        stdin=subprocess.DEVNULL,  # pas de terminal : le kit ne demande jamais la clé
        env=env or os.environ.copy(),
    )
    return resultat.returncode, resultat.stdout.decode("utf-8") + resultat.stderr.decode("utf-8")


@pytest.fixture(autouse=True)
def sans_vraie_cle(tmp_path, monkeypatch):
    """Chaque test a son propre dossier personnel pour la clé, vide, et aucune variable de clé."""
    monkeypatch.setattr(cle, "fichier", lambda: tmp_path / "maison" / ".allergylab" / "cle")
    monkeypatch.setattr(cle, "interactif", lambda: False)
    monkeypatch.delenv(cle.VARIABLE, raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.fixture
def cle_enregistree():
    """La fausse clé, rangée dans le dossier personnel du test."""
    return cle.enregistrer(FAUSSE_CLE)


@pytest.fixture
def depot(tmp_path, monkeypatch):
    """Un dépôt minimal, hors de tout dépôt git : equipe.toml et equipe/."""
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    racine = tmp_path / "depot"
    (racine / "equipe" / "outils").mkdir(parents=True)
    (racine / "equipe.toml").write_text('equipe = "equipe-2"\n', encoding="utf-8")
    (racine / "equipe" / "consigne.md").write_text("Réponds.\n", encoding="utf-8")
    return racine


def lire_trace(racine):
    """La seule trace d'appel écrite dans racine."""
    (chemin,) = sorted((racine / "traces" / "appels").rglob("*.json"))
    return json.loads(chemin.read_text(encoding="utf-8"))


# --- Le faux modèle ------------------------------------------------------------


def message(texte="", outils=(), entree=100, sortie=20):
    """Une réponse réussie de l'API : un texte, et des appels d'outils [(nom, arguments)]."""
    contenu = [{"type": "text", "text": texte}] if texte else []
    contenu += [
        {"type": "tool_use", "id": f"toolu_{rang}", "name": nom, "input": arguments}
        for rang, (nom, arguments) in enumerate(outils)
    ]
    corps = {
        "id": "msg_faux", "type": "message", "role": "assistant", "model": "faux", "content": contenu,
        "stop_reason": "tool_use" if outils else "end_turn", "stop_sequence": None,
        "usage": {"input_tokens": entree, "output_tokens": sortie},
    }
    return 200, corps


def erreur(statut, nature, texte):
    """Une erreur de l'API, dans la forme où l'API d'Anthropic la rend."""
    return statut, {"type": "error", "error": {"type": nature, "message": texte}}


class FauxModele:
    """Joue le rôle de l'API d'Anthropic, sans réseau.

    Il répond au niveau des requêtes HTTP, sous toutes les couches (smolagents,
    litellm, client anthropic) : chaque requête qui serait partie sur le réseau
    compte pour un appel, et reçoit la réponse suivante de la liste programmée.
    """

    def __init__(self):
        self.reponses = []
        self.appels = 0
        self.cles = []  # la clé reçue à chaque appel
        self.attentes = []  # les pauses demandées entre deux tentatives, en secondes

    def programmer(self, *reponses):
        self.reponses.extend(reponses)

    def envoyer(self, client, requete):
        self.appels += 1
        # litellm envoie la clé dans l'en-tête x-api-key, le client anthropic dans authorization.
        en_tete = requete.headers.get("authorization", "").removeprefix("Bearer ")
        self.cles.append(requete.headers.get("x-api-key") or en_tete or None)
        statut, corps = self.reponses.pop(0) if self.reponses else erreur(500, "api_error", "rien de programmé")
        bibliotheque = httpx2 if isinstance(client, httpx2.Client) else httpx  # anthropic : httpx2 ; litellm : httpx
        return bibliotheque.Response(statut, json=corps, request=requete)


CONNEXION_REELLE = socket.socket.connect


def refuser_le_reseau(prise, adresse, *arguments):
    # Sous Windows, Python relie deux prises de la machine entre elles pour ses
    # propres besoins (socket.socketpair, dans asyncio) : ce n'est pas le réseau.
    if isinstance(adresse, tuple) and adresse[0] in ("127.0.0.1", "::1"):
        return CONNEXION_REELLE(prise, adresse, *arguments)
    raise RuntimeError("Un test a tenté une connexion réseau.")


@pytest.fixture
def faux_modele(monkeypatch):
    from kit import modele

    faux = FauxModele()
    monkeypatch.setattr(socket.socket, "connect", refuser_le_reseau)
    monkeypatch.setattr(httpx.Client, "send", lambda client, requete, **_: faux.envoyer(client, requete))
    monkeypatch.setattr(httpx2.Client, "send", lambda client, requete, **_: faux.envoyer(client, requete))
    monkeypatch.setattr(modele.time, "sleep", faux.attentes.append)
    modele.journal_neuf()
    return faux


# --- Deux agents minimaux, un par moteur, indépendants de equipe/agent.py -------


def agent_smolagents(question, etapes_max=3):
    from smolagents import CodeAgent

    from kit import modele

    agent = CodeAgent(
        model=modele.ModeleKit(), tools=[], max_steps=etapes_max, verbosity_level=0,
        step_callbacks=[modele.noter_etape],
    )
    return agent.run(question)


def agent_boucle_maison(question):
    from kit.boucle_maison import BoucleMaison

    return BoucleMaison(tools=[], instructions="Réponds.").run(question)


MOTEURS = {"smolagents": agent_smolagents, "boucle_maison": agent_boucle_maison}


def reponse_finale(moteur, reponse, entree=100, sortie=20):
    """La réponse du faux modèle qui termine : du code pour smolagents, un appel d'outil pour la boucle maison."""
    if moteur == "smolagents":
        return message(f"<code>\nfinal_answer({reponse!r})\n</code>", entree=entree, sortie=sortie)
    return message(outils=[("final_answer", reponse)], entree=entree, sortie=sortie)


@pytest.fixture
def brancher(monkeypatch):
    """brancher(moteur) : kit agent appellera l'agent minimal de ce moteur au lieu de equipe/agent.py."""
    from kit import question

    def choisir(moteur):
        monkeypatch.setattr(question, "charger_repondre", lambda racine: MOTEURS[moteur])

    return choisir
