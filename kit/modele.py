"""Le seul module du kit qui parle au modèle.

Il reprend la façon de faire que kit/tester-la-stack.py valide :
- à travers smolagents : LiteLLMModel(model_id="anthropic/<identifiant>") ;
- sans framework, pour la boucle maison : anthropic.Anthropic(...).messages.create(...).

Deux écarts, voulus :
- la clé est passée en paramètre au client, jamais par une variable
  d'environnement (kit/cle.py) ;
- les nouvelles tentatives se décident ici seulement : celles de smolagents
  (retry=False) et celles du client anthropic (max_retries=0) sont coupées.

La règle, la même pour les deux moteurs (SPEC § 5.3) :
- une saturation passagère (erreur 429 ou 529) donne droit à deux nouvelles
  tentatives espacées, pas plus ;
- toute autre erreur est finale : un seul appel, aucune nouvelle tentative.
  Une erreur 400 dont le message correspond au motif de reglages.toml veut
  dire que la limite de dépense est atteinte : la cagnotte est épuisée.

Chaque appel note dans `journal` le moteur, le modèle, les jetons et le coût
estimé ; l'agent y ajoute ses étapes. `kit agent` affiche ce journal et
l'écrit dans la trace.
"""

import hashlib
import os
import re
import time
import tomllib
from pathlib import Path

# litellm télécharge sa table de tarifs à chaque import ; le kit a la sienne,
# dans reglages.toml. Cette variable lui fait lire la copie qu'il embarque.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import anthropic  # noqa: E402
import litellm  # noqa: E402
import tiktoken.load  # noqa: E402
from smolagents import LiteLLMModel  # noqa: E402

from kit import cle  # noqa: E402

# Sonnet 5.5 refuse un appel d'outil forcé (tool_choice) : litellm retire de
# la requête les paramètres que le modèle n'accepte pas.
litellm.drop_params = True
# Pas de bandeau de litellm à chaque erreur : le kit dit lui-même quoi faire.
litellm.suppress_debug_info = True

# litellm compte les jetons avec tiktoken. Il embarque une copie du tokenizer
# et dit à tiktoken de la chercher dans son dossier (TIKTOKEN_CACHE_DIR). Dans
# la roue Windows de litellm, cette copie a des fins de ligne CRLF : son
# empreinte n'est plus celle qu'attend tiktoken, qui la supprime et va la
# télécharger sur openaipublic.blob.core.windows.net. Le kit ne doit dépendre
# que de l'API d'Anthropic : tiktoken lit donc la copie, fins de ligne
# ramenées à LF, et ne télécharge rien si l'empreinte est alors la bonne.
lire_en_cache = tiktoken.load.read_file_cached


def lire_copie_embarquee(adresse, empreinte=None):
    """Le fichier que tiktoken irait télécharger, lu dans la copie de litellm quand elle a la bonne empreinte."""
    dossier = os.environ.get("TIKTOKEN_CACHE_DIR")
    if dossier and empreinte:
        # Le nom que tiktoken donne à sa copie : l'empreinte SHA-1 de l'adresse.
        copie = Path(dossier) / hashlib.sha1(adresse.encode(), usedforsecurity=False).hexdigest()
        if copie.is_file():
            contenu = copie.read_bytes().replace(b"\r\n", b"\n")
            if tiktoken.load.check_hash(contenu, empreinte):
                return contenu
    return lire_en_cache(adresse, empreinte)


tiktoken.load.read_file_cached = lire_copie_embarquee

REGLAGES = tomllib.loads((Path(__file__).parent / "reglages.toml").read_text(encoding="utf-8"))

# Le modèle appelé : « developpement », ou « officiel » pour une passe officielle.
en_cours = "developpement"

SATURATION = (429, 529)  # trop de requêtes ; serveurs surchargés
ATTENTES = (10, 30)  # secondes avant la première, puis la seconde nouvelle tentative

journal = {}


class ErreurModele(Exception):
    """Une erreur finale de l'appel au modèle : texte dit ce qui ne va pas, que_faire quoi faire."""

    def __init__(self, texte, que_faire):
        super().__init__(f"{texte} Que faire : {que_faire}")
        self.texte, self.que_faire = texte, que_faire


class CagnotteEpuisee(ErreurModele):
    """La limite de dépense du workspace est atteinte."""


def journal_neuf():
    """Remet le journal à zéro, avant une question."""
    journal.clear()
    journal.update(moteur=None, modele=None, jetons={"entree": 0, "sortie": 0}, cout_estime=0.0, etapes=[], erreur=None)


journal_neuf()


# --- Une erreur, et ce qu'elle veut dire --------------------------------------


def statut(erreur):
    """Le code HTTP d'une erreur de l'API, ou None. litellm range l'erreur 529 sous le code 500."""
    if "overloaded_error" in str(erreur):
        return 529
    code = getattr(erreur, "status_code", None)
    return code if isinstance(code, int) else None


def resume(erreur):
    """Le message de l'erreur sur une ligne, tronqué, sans clé."""
    texte = cle.MOTIF_CLE.sub("<clé>", " ".join(str(erreur).split()))
    cle_en_usage = cle.lire()
    return (texte.replace(cle_en_usage, "<clé>") if cle_en_usage else texte)[:300]


def traduire(erreur):
    """L'erreur finale à montrer, avec ce qu'il faut faire ; None si l'erreur ne vient pas de l'API."""
    code = statut(erreur)
    if isinstance(erreur, (anthropic.APIConnectionError, litellm.APIConnectionError, litellm.Timeout)):
        return ErreurModele(
            "l'API d'Anthropic ne répond pas : pas de connexion, ou délai dépassé.",
            "vérifie ton accès à internet, puis relance la commande.",
        )
    if code == 400 and re.search(REGLAGES["limite"]["motif"], str(erreur)):
        return CagnotteEpuisee(
            "cagnotte épuisée : la limite de dépense de ton équipe est atteinte (erreur 400). "
            "Aucune nouvelle tentative n'a été faite.",
            "va voir Adrien. Une demande de rallonge s'écrit dans JOURNAL.md, en trois lignes signées de l'équipe.",
        )
    if code == 401:
        return ErreurModele(
            "la clé d'API est refusée (erreur 401) : elle est révoquée, ou mal copiée.",
            "enregistre la bonne clé avec uv run kit cle.",
        )
    if code in SATURATION:
        return ErreurModele(
            f"le modèle est saturé (erreur {code}), même après deux nouvelles tentatives.",
            "attends une minute, puis repose ta question.",
        )
    if code is not None:
        return ErreurModele(
            f"l'API a refusé l'appel (erreur {code}), et aucune nouvelle tentative n'a été faite. {resume(erreur)}",
            "montre ce message à l'animateur.",
        )
    return None


def appeler(envoyer):
    """Appelle envoyer() une fois ; après une saturation passagère, deux fois de plus au plus."""
    for tentative in range(len(ATTENTES) + 1):
        try:
            return envoyer()
        except Exception as erreur:
            code = statut(erreur)
            if code in SATURATION and tentative < len(ATTENTES):
                print(f"Modèle saturé (erreur {code}) : nouvelle tentative dans {ATTENTES[tentative]} s.")
                time.sleep(ATTENTES[tentative])
                continue
            finale = traduire(erreur)
            if finale is None:
                raise
            # smolagents avale l'erreur de son tout dernier appel, après la
            # dernière étape : le journal la garde pour kit agent.
            journal["erreur"] = finale
            raise finale from erreur


# --- Les jetons et leur coût --------------------------------------------------


def choisi(nom=None):
    """Les réglages d'un modèle (identifiant, tarifs) ; par défaut, ceux du modèle en cours."""
    return REGLAGES["modeles"][nom or en_cours]


def cout(reglage, entree, sortie):
    """Le coût estimé, en dollars, de jetons d'entrée et de sortie."""
    return (entree * reglage["entree"] + sortie * reglage["sortie"]) / 1_000_000


def compter(reglage, entree, sortie):
    journal["modele"] = reglage["identifiant"]
    journal["jetons"]["entree"] += entree
    journal["jetons"]["sortie"] += sortie
    journal["cout_estime"] += cout(reglage, entree, sortie)


def en_dollars(montant):
    """« 0,0012 $ » : assez de chiffres pour qu'un petit montant ne s'affiche pas comme zéro."""
    return f"{montant:.{4 if montant >= 0.01 else 6}f} $".replace(".", ",")


# --- Les deux moteurs ---------------------------------------------------------


class ModeleKit(LiteLLMModel):
    """Le LiteLLMModel de smolagents, avec la règle des nouvelles tentatives du kit et le compte des jetons."""

    def __init__(self, nom=None):
        self.reglage = choisi(nom)
        super().__init__(
            model_id=f"anthropic/{self.reglage['identifiant']}",
            api_key=cle.exiger(),  # en paramètre : la clé n'entre dans aucune variable d'environnement
            retry=False,  # smolagents ne retente rien lui-même : appeler() décide
        )

    def generate(self, messages, **options):
        journal["moteur"] = "smolagents"
        reponse = appeler(lambda: LiteLLMModel.generate(self, messages, **options))
        compter(self.reglage, reponse.token_usage.input_tokens, reponse.token_usage.output_tokens)
        return reponse


def messages(**requete):
    """Un appel sans framework, comme le contrôle 2 de tester-la-stack.py : celui de la boucle maison."""
    journal["moteur"] = "boucle_maison"
    reglage = choisi()
    # max_retries=0 : le client ne retente rien lui-même, appeler() décide.
    client = anthropic.Anthropic(api_key=cle.exiger(), max_retries=0)
    reponse = appeler(lambda: client.messages.create(model=reglage["identifiant"], **requete))
    compter(reglage, reponse.usage.input_tokens, reponse.usage.output_tokens)
    return reponse


def essai():
    """L'appel minimal de `kit controle`, sur le modèle du développement. Rend (identifiant, jetons, coût)."""
    modele = ModeleKit("developpement")
    question = {"role": "user", "content": [{"type": "text", "text": "Réponds exactement : prêt"}]}
    reponse = modele.generate([question], max_tokens=64)
    entree, sortie = reponse.token_usage.input_tokens, reponse.token_usage.output_tokens
    return modele.reglage["identifiant"], entree + sortie, cout(modele.reglage, entree, sortie)


# --- Les étapes de l'agent ----------------------------------------------------


def tronquer(texte):
    """Coupe une sortie plus longue que sortie_max (reglages.toml)."""
    if texte is None:
        return None
    texte, limite = str(texte), REGLAGES["agent"]["sortie_max"]
    return texte if len(texte) <= limite else f"{texte[:limite]}… [tronqué : {len(texte)} caractères]"


def ajouter_etape(code, resultat):
    journal["etapes"].append({"code": code, "resultat": tronquer(resultat)})


def noter_etape(etape):
    """À donner à un agent de smolagents (step_callbacks) : recopie chaque étape dans la trace."""
    resultat = f"Erreur : {etape.error}" if etape.error is not None else etape.observations
    ajouter_etape(etape.code_action, resultat)
