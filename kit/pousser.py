"""Envoyer les traces vers le dépôt de l'équipe : `uv run kit pousser`.

Quatre machines poussent dans le même dépôt, et un push est refusé tant
qu'on n'a pas récupéré celui des coéquipiers (SPEC §§ 7.3 et 7.4). La
commande fait les gestes dans le bon ordre :

1. enregistrer les traces : git add traces, puis un commit qui ne contient
   que traces/ ;
2. récupérer le travail des coéquipiers : git pull --rebase --autostash ;
3. pousser : git push. Si un coéquipier a poussé entre-temps, le push est
   refusé : on récupère de nouveau, puis on repousse, trois essais au plus.

Ce qu'elle ne fait jamais : enregistrer un fichier hors de traces/, forcer
un push, revenir en arrière par un reset, effacer quoi que ce soit. Un
fichier modifié et non enregistré est retrouvé tel quel, toujours non
enregistré. Si un coéquipier a modifié le même fichier, elle s'arrête et
laisse le dossier comme elle l'a trouvé.

git est appelé sans interpréteur de commandes. Sa sortie ne s'affiche
qu'avec --detail.
"""

import os
import subprocess
import tomllib
from pathlib import Path

from kit.donnees import RACINE

ESSAIS = 3

# Ce que git laisse dans son dossier tant qu'une opération n'est pas finie.
OPERATIONS_EN_COURS = ("rebase-merge", "rebase-apply", "MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD")

GIT_ABSENT = (
    "git est introuvable sur cette machine. Installe-le depuis https://git-scm.com, "
    "ferme et rouvre le terminal, puis relance uv run kit pousser."
)
PAS_UN_DEPOT = (
    "ce dossier n'est pas un dépôt git, sans doute parce que le kit a été téléchargé en archive : "
    "les traces n'ont nulle part où partir. Appelle l'animateur, qui t'aidera à cloner le dépôt de ton équipe."
)
OPERATION_EN_COURS = (
    "une opération git est restée inachevée dans ce dossier (un rebase ou une fusion). "
    "uv run kit pousser n'y touche pas : appelle l'animateur."
)
NON_RATTACHE = (
    "ce clone n'est pas encore rattaché au dépôt de ton équipe : equipe.toml dit encore « accueil ». "
    "Demande à l'animateur la commande qui le redirige vers le dépôt de ton équipe, "
    "puis relance uv run kit pousser."
)
SANS_IDENTITE = (
    "git ne sait pas qui signe les commits sur cette machine. Lance ces deux commandes, en remplaçant "
    "le texte entre guillemets, puis relance uv run kit pousser :\n"
    '    git config --global user.name "ton nom ou un pseudonyme"\n'
    '    git config --global user.email "ton adresse électronique"'
)
SANS_BRANCHE_SUIVIE = (
    "la branche de ce dossier n'est reliée à aucune branche du dépôt de l'équipe : appelle l'animateur."
)
CONNEXION_REFUSEE = (
    "la connexion à GitHub est refusée, ou le réseau ne répond pas. Relance la commande depuis le terminal "
    "intégré de VS Code (menu Terminal, puis Nouveau terminal), qui se charge de te connecter à GitHub ; "
    "si le refus persiste, appelle l'animateur."
)
VOIR_LE_DETAIL = "Relance uv run kit pousser --detail, et montre le résultat à l'animateur."


def git(racine, *arguments, detail=False):
    """Lance git dans racine, sans interpréteur de commandes. Rend son résultat, ou None si git manque.

    GIT_TERMINAL_PROMPT=0 : si GitHub réclame un identifiant dans le terminal,
    git échoue aussitôt au lieu d'attendre une saisie. Le gestionnaire
    d'identifiants du système et celui de VS Code servent toujours.
    """
    try:
        resultat = subprocess.run(
            ["git", *arguments], cwd=racine, capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except OSError:
        return None
    if detail:
        print(f"  $ git {' '.join(arguments)}")
        for ligne in (resultat.stdout + resultat.stderr).replace("\0", "\n").splitlines():
            print(f"    {ligne}")
    return resultat


def noms(resultat):
    """Les chemins d'une sortie de git en -z, où un caractère nul les sépare."""
    return {nom for nom in resultat.stdout.split("\0") if nom}


def dossier_git(racine):
    """Le dossier .git du dépôt dont racine est la racine ; None sans git, ou hors d'un tel dépôt."""
    resultat = git(racine, "rev-parse", "--show-toplevel", "--absolute-git-dir")
    if resultat is None or resultat.returncode != 0:
        return None
    try:
        haut, dossier = resultat.stdout.splitlines()
        # Un dépôt plus haut dans l'arborescence n'est pas celui du kit.
        return Path(dossier) if Path(haut).samefile(racine) else None
    except (OSError, ValueError):  # une réponse de git inattendue : on fait comme s'il n'y avait pas de dépôt
        return None


def operation_en_cours(dossier):
    return any((dossier / nom).exists() for nom in OPERATIONS_EN_COURS)


def lire_equipe(racine):
    try:
        return tomllib.loads((racine / "equipe.toml").read_text(encoding="utf-8")).get("equipe")
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return None


def decompte(chemins):
    """« 2 traces et 1 état du travail » : une trace par fichier, un état par dossier de traces/etats/.

    Rend un texte vide s'il n'y a rien à compter. Les fichiers cachés (.gitkeep,
    copie d'état inachevée) ne comptent pas.
    """
    parties = [chemin.split("/") for chemin in chemins]
    parties = [p for p in parties if len(p) > 1 and not any(nom.startswith(".") for nom in p)]
    etats = {p[2] for p in parties if p[1] == "etats" and len(p) > 3}
    traces = [p for p in parties if p[1] != "etats"]
    morceaux = []
    if traces:
        morceaux.append(f"{len(traces)} trace{'s' if len(traces) > 1 else ''}")
    if etats:
        morceaux.append(f"{len(etats)} état{'s' if len(etats) > 1 else ''} du travail")
    return " et ".join(morceaux)


def traces_non_poussees(racine=RACINE):
    """Les fichiers de traces/ que le dépôt de l'équipe n'a pas, d'après le dernier échange avec lui.

    Aucune connexion : la comparaison porte sur ce que git sait déjà du dépôt
    de l'équipe. Rend None sans git, hors d'un dépôt, ou sans branche suivie.
    """
    if dossier_git(racine) is None:
        return None
    chez_eux = git(racine, "--no-optional-locks", "ls-tree", "-r", "-z", "--name-only", "@{u}", "--", "traces")
    if chez_eux.returncode != 0:
        return None
    ici = git(racine, "--no-optional-locks", "ls-files", "-z", "--cached", "--others", "--exclude-standard",
              "--", "traces")
    return sorted(noms(ici) - noms(chez_eux))


def refus(racine):
    """Pourquoi la commande ne peut pas tourner ici, et quoi faire ; None si rien ne l'en empêche."""
    if git(racine, "--version") is None:
        return GIT_ABSENT
    dossier = dossier_git(racine)
    if dossier is None:
        return PAS_UN_DEPOT
    if operation_en_cours(dossier):
        return OPERATION_EN_COURS
    if lire_equipe(racine) == "accueil":
        return NON_RATTACHE
    # user.useConfigOnly : git n'invente pas une identité à partir du nom de la machine.
    for identite in ("GIT_AUTHOR_IDENT", "GIT_COMMITTER_IDENT"):
        if git(racine, "-c", "user.useConfigOnly=true", "var", identite).returncode != 0:
            return SANS_IDENTITE
    if git(racine, "rev-parse", "--verify", "--quiet", "@{u}").returncode != 0:
        return SANS_BRANCHE_SUIVIE
    return None


def fichiers_en_conflit(racine):
    """Les fichiers modifiés ici sans être enregistrés, qu'un coéquipier a modifiés de son côté.

    git pull --autostash les fusionnerait, et ne saurait pas revenir en arrière
    si les deux versions se heurtent : on s'arrête avant, sans rien toucher.
    traces/ n'en fait pas partie : ses fichiers sont enregistrés juste après.
    """
    chez_eux = noms(git(racine, "diff", "--name-only", "-z", "--no-renames", "HEAD...@{u}"))
    ici = noms(git(racine, "diff", "--name-only", "-z", "--no-renames", "HEAD"))
    ici |= noms(git(racine, "ls-files", "-z", "--others", "--exclude-standard"))
    return sorted(nom for nom in chez_eux & ici if not nom.startswith("traces/"))


def conflit(fichiers):
    if len(fichiers) > 1:
        quoi = f"les mêmes fichiers que toi ({', '.join(fichiers)})"
    else:
        quoi = f"le même fichier que toi ({fichiers[0]})" if fichiers else "le même fichier que toi"
    return f"un coéquipier a modifié {quoi} : ton dossier est resté tel quel, appelle l'animateur."


def enregistrer(racine, detail):
    """git add traces, puis un commit de traces/ seul. Rend les chemins enregistrés, ou None si git refuse."""
    if not (racine / "traces").is_dir():
        return []  # le kit n'a encore rien écrit
    if git(racine, "add", "--", "traces", detail=detail).returncode != 0:
        return None
    chemins = sorted(noms(git(racine, "diff", "--cached", "--name-only", "-z", "--no-renames", "--", "traces")))
    if not chemins:
        return []
    # Le chemin donné après « -- » limite le commit à traces/ : un fichier
    # indexé ailleurs, par un git add de l'étudiant, n'y entre pas.
    commit = git(racine, "commit", "--quiet", "--message", "Enregistrer les traces", "--", "traces", detail=detail)
    return chemins if commit.returncode == 0 else None


def recuperer(racine, detail):
    """git pull --rebase --autostash. Rend None, ou le message d'échec une fois le dossier remis en état."""
    pull = git(racine, "pull", "--rebase", "--autostash", detail=detail)
    if operation_en_cours(dossier_git(racine)):
        # Le rebase s'est arrêté sur un conflit. L'annuler remet aussi en place
        # les modifications non enregistrées que git avait mises de côté.
        heurtes = sorted(noms(git(racine, "diff", "--name-only", "-z", "--diff-filter=U")))
        git(racine, "rebase", "--abort", detail=detail)
        return conflit(heurtes)
    if pull.returncode != 0:
        return f"git n'a pas pu récupérer le travail des coéquipiers. {VOIR_LE_DETAIL}"
    heurtes = sorted(noms(git(racine, "diff", "--name-only", "-z", "--diff-filter=U")))
    if heurtes:
        # Rare : un coéquipier a poussé ce fichier entre la vérification et la récupération.
        return (
            f"un coéquipier a modifié {', '.join(heurtes)} pendant l'envoi, comme toi : tes modifications "
            "sont gardées par git (git stash list) ; appelle l'animateur avant d'y toucher."
        )
    return None


def echec(message):
    print(f"ÉCHEC : {message}")
    return 1


def pousser(racine=RACINE, detail=False):
    """Enregistre les traces, récupère le travail des coéquipiers, pousse. Rend 0 (réussite) ou 1 (échec)."""
    print("Envoi des traces vers le dépôt de l'équipe")
    message = refus(racine)
    if message:
        return echec(message)
    # Un premier échange qui ne touche pas au dossier : il vérifie la connexion,
    # et dit ce que les coéquipiers ont modifié depuis le dernier.
    if git(racine, "fetch", detail=detail).returncode != 0:
        return echec(CONNEXION_REFUSEE)
    communs = fichiers_en_conflit(racine)
    if communs:
        return echec(conflit(communs))

    chemins = enregistrer(racine, detail)
    if chemins is None:
        return echec(f"git a refusé d'enregistrer les traces. {VOIR_LE_DETAIL}")
    enregistrees = decompte(chemins)
    if enregistrees:
        print(f"  OK     traces enregistrées : {enregistrees}")
    else:
        print("  OK     aucune trace nouvelle à enregistrer")

    for essai in range(1, ESSAIS + 1):
        message = recuperer(racine, detail)
        if message:
            return echec(message)
        print("  OK     travail des coéquipiers récupéré")
        if git(racine, "rev-list", "--count", "@{u}..HEAD").stdout.strip() == "0":
            print("RÉUSSITE : rien à envoyer, le dépôt de l'équipe a déjà toutes tes traces.")
            return 0
        envoi = decompte(traces_non_poussees(racine) or [])
        if git(racine, "push", detail=detail).returncode == 0:
            print(f"RÉUSSITE : le dépôt de l'équipe a reçu {envoi or 'tes commits, sans trace nouvelle'}.")
            return 0
        # Push refusé. Si le dépôt de l'équipe a bougé, un coéquipier a poussé
        # entre-temps et l'on recommence ; sinon, le refus vient d'ailleurs.
        if git(racine, "fetch", detail=detail).returncode != 0:
            return echec(CONNEXION_REFUSEE)
        if git(racine, "merge-base", "--is-ancestor", "@{u}", "HEAD").returncode == 0:
            return echec(CONNEXION_REFUSEE)
        communs = fichiers_en_conflit(racine)
        if communs:
            return echec(conflit(communs))
        if essai < ESSAIS:
            print(f"  --     un coéquipier a poussé entre-temps : nouvel essai ({essai + 1} sur {ESSAIS})")
    return echec(
        f"le dépôt de l'équipe a changé pendant chacun des {ESSAIS} essais. Tes traces sont enregistrées : "
        "relance uv run kit pousser dans une minute."
    )
