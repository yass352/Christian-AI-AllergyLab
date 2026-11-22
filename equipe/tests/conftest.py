"""Les tests de l'équipe tournent sur la table inventée de kit/exemple/, jamais sur le fichier réel.

Ils n'appellent ni le réseau ni le modèle : un faux modèle joue son rôle.
"""

import pytest
from smolagents.models import ChatMessage, MessageRole, Model
from smolagents.monitoring import TokenUsage

from equipe.outils import acces
from kit import cle
from kit.donnees import RACINE, charger

TABLE_INVENTEE = RACINE / "kit" / "exemple" / "mini.csv"


@pytest.fixture(autouse=True)
def sans_vraie_cle(tmp_path, monkeypatch):
    """Comme dans kit/tests : un dossier personnel vide pour la clé, aucune variable de clé."""
    monkeypatch.setattr(cle, "fichier", lambda: tmp_path / "maison" / ".allergylab" / "cle")
    monkeypatch.setattr(cle, "interactif", lambda: False)
    monkeypatch.delenv(cle.VARIABLE, raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.fixture(autouse=True)
def table_inventee(monkeypatch):
    """Les outils lisent la table inventée de douze lignes."""
    monkeypatch.setattr(acces, "CHEMIN", TABLE_INVENTEE)
    acces.tableau.cache_clear()
    yield
    acces.tableau.cache_clear()


class FauxModele(Model):
    """Rend, dans l'ordre, des réponses écrites d'avance, et garde les messages reçus."""

    def __init__(self, *reponses):
        super().__init__(model_id="faux")
        self.reponses = list(reponses)
        self.recus = []

    def generate(self, messages, stop_sequences=None, response_format=None, tools_to_call_from=None, **options):
        self.recus.append(messages)
        texte = self.reponses.pop(0)
        return ChatMessage(role=MessageRole.ASSISTANT, content=texte, token_usage=TokenUsage(input_tokens=10, output_tokens=5))


@pytest.fixture
def faux_modele(monkeypatch):
    """faux_modele(*reponses) : l'agent de l'équipe parlera à ce faux modèle, sur la table inventée."""
    from equipe import agent
    from kit import modele

    def brancher(*reponses):
        faux = FauxModele(*reponses)
        monkeypatch.setattr(modele, "ModeleKit", lambda: faux)
        monkeypatch.setattr(agent, "charger", lambda: charger(TABLE_INVENTEE))
        monkeypatch.setattr(agent, "REUTILISER_LES_TRACES", False)  # pas de réponse reprise des vraies traces
        modele.journal_neuf()
        return faux

    return brancher
