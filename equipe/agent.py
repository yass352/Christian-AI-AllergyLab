
"""Agent d'analyse des données allergologiques de l'équipe."""

from pathlib import Path

from smolagents import CodeAgent

from equipe import memoire
from equipe.outils import acces, garde_fous
from equipe.outils.calendrier_pollinique import calendrier_pollinique
from equipe.outils.chercher_colonnes import chercher_colonnes
from equipe.outils.classer_allergenes import classer_allergenes
from equipe.outils.codes_officiels import codes_officiels
from equipe.outils.colonnes_par_famille import colonnes_par_famille
from equipe.outils.compter_codes import compter_codes
from equipe.outils.croiser import croiser
from equipe.outils.decrire_colonne import decrire_colonne
from equipe.outils.positifs import positifs
from equipe.outils.source_allergene import source_allergene
from equipe.outils.statistiques import resume_allergene
from kit import modele, reponse
from kit.donnees import charger

CONSIGNE = (Path(__file__).parent / "consigne.md").read_text(encoding="utf-8")

# Une question déjà posée mot pour mot au même agent et au même modèle reprend
# la réponse de sa trace, sans appel au modèle (equipe/memoire.py).
# False : chaque question appelle le modèle, par exemple pour comparer deux réponses.
REUTILISER_LES_TRACES = True

# Les outils de l'équipe, testés sans le modèle dans equipe/tests/. Chacun rend
# des valeurs simples, jamais le tableau : ils restent valables si l'on ferme l'accès.
OUTILS = [
    chercher_colonnes, decrire_colonne, compter_codes, codes_officiels, croiser,
    positifs, classer_allergenes, source_allergene, colonnes_par_famille, calendrier_pollinique,
    resume_allergene,
]


def verifier_contrat(reponse_finale, memoire, agent=None):
    """Refuse une réponse finale hors contrat (kit/reponse.py), ou que rien n'appuie (outils/garde_fous.py).

    L'agent lit alors l'erreur et corrige sa réponse à l'étape suivante, au lieu
    de rendre au kit une réponse illisible ou inventée.
    """
    valide = reponse.valider(reponse_finale)  # lève une erreur qui dit ce qui ne va pas
    executeur = getattr(agent, "python_executor", None)
    if isinstance(executeur, garde_fous.ExecuteurRelu):
        garde_fous.verifier_reponse(valide, executeur.codes, [outil.name for outil in OUTILS])
    return True


def repondre(question):
    # Garde-fou d'entrée : une question trop longue, hors sujet ou qui tente de
    # détourner l'agent reçoit une abstention, sans appel au modèle.
    refus = garde_fous.verifier_question(question)
    if refus:
        print("Question refusée par le garde-fou : aucun appel au modèle.")
        modele.ajouter_etape("# Question refusée par le garde-fou : aucun appel au modèle.", None)  # dans la trace
        return refus

    if REUTILISER_LES_TRACES:
        deja = memoire.reponse_enregistree(question)
        if deja:
            reponse_finale, trace = deja
            print(f"Réponse reprise de {trace} : aucun appel au modèle.")
            modele.ajouter_etape(f"# Réponse reprise de {trace} : aucun appel au modèle.", None)  # dans la trace
            return reponse_finale

    agent = CodeAgent(
        model=modele.ModeleKit(),  # le modèle de kit/reglages.toml
        tools=OUTILS,
        instructions=reponse.consigne(CONSIGNE),  # notre consigne, puis le format de réponse du kit
        max_steps=modele.REGLAGES["agent"]["etapes_max"],
        max_print_outputs_length=modele.REGLAGES["agent"]["sortie_max"],
        step_callbacks=[modele.noter_etape],  # recopie chaque étape dans la trace
        final_answer_checks=[verifier_contrat],
        # Accès aux données : le code écrit par le modèle peut importer pandas.
        additional_authorized_imports=["pandas"],
    )
    # Garde-fou d'exécution : chaque code du modèle est relu avant de tourner
    # (ni fichier, ni système, ni réseau). Ce n'est pas un bac à sable : voir le README.
    agent.python_executor = garde_fous.ExecuteurRelu(
        agent.additional_authorized_imports, max_print_outputs_length=agent.max_print_outputs_length
    )
    return agent.run(
        garde_fous.encadrer(question),  # la question entre balises : un texte à analyser, pas un ordre
        # Accès aux données : le code écrit par le modèle reçoit le tableau complet, sous le nom tableau,
        # et chaque fichier de donnees_complementaires/ déjà chargé (pollens_mois, risque_lyon… : outils/acces.py).
        additional_args={"tableau": charger(), **acces.complements()},
    )
