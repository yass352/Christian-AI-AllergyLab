"""Erreurs du modèle : une erreur 400 n'est jamais retentée, une saturation l'est deux fois, pas plus.

Le faux modèle de conftest.py répond à la place de l'API, au niveau des
requêtes HTTP : il compte chaque appel qui serait parti sur le réseau, quelles
que soient les couches entre le kit et lui. Chaque règle est vérifiée dans les
deux moteurs : smolagents, et la boucle maison.
"""

import pytest

from kit import controle, modele, question
from kit.donnees import RACINE

from conftest import MOTEURS, agent_smolagents, erreur, lire_trace, message, reponse_finale

# Le message de l'API quand la limite de dépense d'un workspace est atteinte.
LIMITE = "You have reached your specified workspace API usage limits. You will regain access on 2026-12-01 at 00:00 UTC."

# Une erreur 400 ordinaire, dont le texte contient « 429 » : smolagents, seul,
# la prendrait pour une limite de débit et la retenterait.
REFUS = "messages.0.content: text content blocks must be non-empty (requête 429)"

SATURE = erreur(529, "overloaded_error", "Overloaded")
TROP_DE_REQUETES = erreur(429, "rate_limit_error", "Number of requests has exceeded your per-minute rate limit")
REPONSE = {"statut": "reponse", "valeur": 12, "justification": "Une réponse inventée pour le test."}


@pytest.mark.parametrize("moteur", MOTEURS)
def test_erreur_400_un_seul_appel(moteur, faux_modele, cle_enregistree, depot, brancher, capsys):
    faux_modele.programmer(erreur(400, "invalid_request_error", LIMITE))
    brancher(moteur)

    assert question.poser("Combien de lignes ?", depot) == 1

    assert faux_modele.appels == 1
    assert faux_modele.attentes == []
    sortie = capsys.readouterr().out
    assert "Cagnotte épuisée" in sortie
    assert "Que faire : va voir Adrien." in sortie
    assert "Aucune nouvelle tentative" in sortie
    trace = lire_trace(depot)
    assert trace["moteur"] == moteur and trace["reponse"] is None
    assert trace["erreur"].startswith("CagnotteEpuisee : cagnotte épuisée")


@pytest.mark.parametrize("moteur", MOTEURS)
def test_erreur_400_ordinaire_un_seul_appel(moteur, faux_modele, cle_enregistree, depot, brancher, capsys):
    faux_modele.programmer(erreur(400, "invalid_request_error", REFUS))
    brancher(moteur)

    assert question.poser("Combien de lignes ?", depot) == 1

    assert faux_modele.appels == 1 and faux_modele.attentes == []
    sortie = capsys.readouterr().out
    assert "L'API a refusé l'appel (erreur 400)" in sortie
    assert "Cagnotte" not in sortie
    assert "erreur 400" in lire_trace(depot)["erreur"]


def test_erreur_400_avalee_par_smolagents(faux_modele, cle_enregistree, depot, monkeypatch, capsys):
    # Après sa dernière étape, smolagents demande une réponse finale au modèle
    # et avale l'erreur de cet appel. Le kit la retrouve dans son journal.
    faux_modele.programmer(message("<code>\nprint(1)\n</code>"), erreur(400, "invalid_request_error", LIMITE))
    monkeypatch.setattr(question, "charger_repondre", lambda racine: lambda q: agent_smolagents(q, etapes_max=1))

    assert question.poser("Combien de lignes ?", depot) == 1

    assert faux_modele.appels == 2  # une étape, puis la 400, une seule fois
    assert "Cagnotte épuisée" in capsys.readouterr().out
    trace = lire_trace(depot)
    assert trace["erreur"].startswith("CagnotteEpuisee")
    assert trace["etapes"][0]["code"] == "print(1)"


@pytest.mark.parametrize("moteur", MOTEURS)
def test_saturation_deux_nouvelles_tentatives(moteur, faux_modele, cle_enregistree, depot, brancher, capsys):
    faux_modele.programmer(SATURE, TROP_DE_REQUETES, SATURE, reponse_finale(moteur, REPONSE))
    brancher(moteur)

    assert question.poser("Combien de lignes ?", depot) == 1

    assert faux_modele.appels == 3  # le premier appel, puis deux nouvelles tentatives, pas plus
    assert faux_modele.attentes == list(modele.ATTENTES)
    sortie = capsys.readouterr().out
    assert sortie.count("nouvelle tentative dans") == 2
    assert "Le modèle est saturé (erreur 529), même après deux nouvelles tentatives." in sortie
    assert "saturé" in lire_trace(depot)["erreur"]


@pytest.mark.parametrize("moteur", MOTEURS)
def test_saturation_puis_reponse(moteur, faux_modele, cle_enregistree, depot, brancher):
    faux_modele.programmer(TROP_DE_REQUETES, reponse_finale(moteur, REPONSE))
    brancher(moteur)

    assert question.poser("Combien de lignes ?", depot) == 0

    assert faux_modele.appels == 2 and faux_modele.attentes == [modele.ATTENTES[0]]
    trace = lire_trace(depot)
    assert trace["reponse"] == REPONSE and trace["erreur"] is None


@pytest.mark.parametrize("moteur", MOTEURS)
def test_cle_refusee_par_l_api(moteur, faux_modele, cle_enregistree, depot, brancher, capsys):
    faux_modele.programmer(erreur(401, "authentication_error", "invalid x-api-key"))
    brancher(moteur)

    assert question.poser("Combien de lignes ?", depot) == 1

    assert faux_modele.appels == 1
    assert "Que faire : enregistre la bonne clé avec uv run kit cle." in capsys.readouterr().out


@pytest.mark.parametrize("moteur", MOTEURS)
def test_sans_cle_aucun_appel(moteur, faux_modele, depot, brancher, capsys):
    brancher(moteur)

    assert question.poser("Combien de lignes ?", depot) == 1

    assert faux_modele.appels == 0
    sortie = capsys.readouterr().out
    assert "Aucune clé d'API n'est enregistrée." in sortie
    assert "Que faire : lance uv run kit cle" in sortie
    assert "Clé d'API absente" in lire_trace(depot)["erreur"]


def test_controle_appel_minimal(faux_modele, cle_enregistree, capsys):
    faux_modele.programmer(message("prêt", entree=12, sortie=3))
    avant = sorted((RACINE / "traces").rglob("*"))
    assert controle.controler(RACINE) == 0
    sortie = capsys.readouterr().out
    assert "appel au modèle : claude-haiku-5-5 a répondu (15 jetons" in sortie
    assert sortie.strip().splitlines()[-1] == "RÉUSSITE"
    assert faux_modele.appels == 1
    assert sorted((RACINE / "traces").rglob("*")) == avant  # le contrôle n'écrit aucune trace


def test_controle_cagnotte_epuisee(faux_modele, cle_enregistree, capsys):
    faux_modele.programmer(erreur(400, "invalid_request_error", LIMITE))
    assert controle.controler(RACINE) == 1
    sortie = capsys.readouterr().out
    assert "ÉCHEC  appel au modèle : cagnotte épuisée" in sortie
    assert "Que faire : va voir Adrien." in sortie
    assert faux_modele.appels == 1
