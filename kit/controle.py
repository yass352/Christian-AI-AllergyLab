"""Vérifie l'installation point par point : `uv run kit controle`.

Chaque vérification rend des lignes (bon, texte, que_faire). Une ligne en
échec dit ce qui ne va pas, puis quoi faire. La dernière ligne affichée est
RÉUSSITE (code 0) ou ÉCHEC (code 1).
"""

import hashlib
import re
import subprocess
import tempfile
import tomllib

from kit import cle, donnees, pousser

RACINE = donnees.RACINE
EQUIPE_VALIDE = re.compile(r"accueil|equipe-[1-9]")

RESTAURER_DONNEES = (
    "restaure le dossier avec « git checkout -- donnees/ », "
    "ou retélécharge l'archive du dépôt."
)
RESTAURER_KIT = (
    "restaure le dossier kit/ avec « git checkout -- kit/ », "
    "ou retélécharge l'archive du dépôt."
)


def empreinte(chemin):
    """Empreinte SHA-256 d'un fichier, en hexadécimal."""
    with open(chemin, "rb") as fichier:
        return hashlib.file_digest(fichier, "sha256").hexdigest()


def lire_attendu(racine):
    """Lit kit/empreintes.toml : empreintes des fichiers et forme du tableau."""
    texte = (racine / "kit" / "empreintes.toml").read_text(encoding="utf-8")
    return tomllib.loads(texte)


def verifier_donnees(racine, attendu):
    """Chaque fichier de donnees/ est présent et a l'empreinte publiée."""
    lignes = []
    for nom, valeur in attendu["fichiers"].items():
        chemin = racine / "donnees" / nom
        if not chemin.is_file():
            lignes.append((False, f"données : donnees/{nom} est absent.", RESTAURER_DONNEES))
        elif empreinte(chemin) != valeur:
            lignes.append((
                False,
                f"données : donnees/{nom} n'a pas l'empreinte publiée. Le fichier a "
                "été modifié, ou ses fins de ligne ont été converties.",
                RESTAURER_DONNEES,
            ))
        else:
            lignes.append((True, f"données : donnees/{nom}, empreinte conforme", None))
    return lignes


def verifier_tableau(racine, attendu):
    """Le tableau se charge et a la forme attendue. Rend la ligne et le tableau."""
    chemin = racine / "donnees" / donnees.NOM_FICHIER
    if not chemin.is_file():
        return (False, "tableau : non chargé, le fichier de données est absent.", RESTAURER_DONNEES), None
    try:
        tableau = donnees.charger(chemin)
    except (ValueError, UnicodeDecodeError) as erreur:
        return (False, f"tableau : il ne se charge pas. {erreur}", RESTAURER_DONNEES), None
    lignes, colonnes = tableau.shape
    forme = attendu["forme"]
    if (lignes, colonnes) != (forme["lignes"], forme["colonnes"]):
        texte = (
            f"tableau : {lignes} lignes et {colonnes} colonnes, "
            f"au lieu de {forme['lignes']} et {forme['colonnes']}."
        )
        return (False, texte, RESTAURER_DONNEES), tableau
    return (True, f"tableau : {lignes} lignes, {colonnes} colonnes", None), tableau


def verifier_dictionnaire(racine, tableau):
    """kit/colonnes.csv décrit les colonnes du tableau, dans l'ordre, avec leur lecture."""
    if tableau is None:
        return False, "dictionnaire des colonnes : non vérifié, le tableau ne se charge pas.", RESTAURER_DONNEES
    chemin = racine / "kit" / "colonnes.csv"
    if not chemin.is_file():
        return False, "dictionnaire des colonnes : kit/colonnes.csv est absent.", RESTAURER_KIT
    dico = donnees.colonnes(chemin)
    probleme = None
    puces = {f"puce_{valeur}" for valeur in tableau[donnees.COLONNE_PUCE].dropna().unique()}
    if list(dico.columns[:3]) != ["colonne", "bloc", "lecture"] or set(dico.columns[3:]) != puces:
        probleme = "ses en-têtes ne sont pas colonne, bloc, lecture et une colonne puce_ par type de puce."
    elif list(dico["colonne"]) != list(tableau.columns):
        probleme = "il ne nomme pas les colonnes du fichier, dans le même ordre."
    else:
        for position, ligne in enumerate(dico.itertuples()):
            bloc = "clinique" if position < donnees.NB_CLINIQUES else "dosage"
            if ligne.bloc != bloc or ligne.lecture != donnees.lecture(tableau[ligne.colonne]):
                probleme = f"la ligne de la colonne {ligne.colonne} ne correspond pas au fichier."
                break
    if probleme:
        return False, f"dictionnaire des colonnes : kit/colonnes.csv, {probleme}", RESTAURER_KIT
    return True, f"dictionnaire des colonnes : {len(dico)} colonnes, cohérent avec le fichier", None


def verifier_equipe(racine):
    """equipe.toml existe et donne un identifiant valide."""
    que_faire = (
        'dans equipe.toml, écris equipe = "accueil" avant la constitution des '
        'équipes, puis equipe = "equipe-N", N étant le numéro de ton équipe (1 à 9).'
    )
    chemin = racine / "equipe.toml"
    if not chemin.is_file():
        return False, "équipe : equipe.toml est absent.", que_faire
    try:
        equipe = tomllib.loads(chemin.read_text(encoding="utf-8")).get("equipe")
    except (tomllib.TOMLDecodeError, UnicodeDecodeError):
        return False, "équipe : equipe.toml ne se lit pas.", que_faire
    if not isinstance(equipe, str) or not EQUIPE_VALIDE.fullmatch(equipe):
        return False, f"équipe : identifiant {equipe!r} non valide.", que_faire
    return True, f"équipe : {equipe}", None


def verifier_traces(racine):
    """Le kit peut écrire dans traces/ : il y crée un fichier provisoire, aussitôt effacé."""
    dossier = racine / "traces"
    try:
        dossier.mkdir(exist_ok=True)
        with tempfile.TemporaryFile(dir=dossier):
            pass
    except OSError:
        return (
            False,
            "traces : le kit ne peut pas écrire dans le dossier traces/.",
            "vérifie que traces/ est un dossier et que le dépôt n'est pas en lecture seule ; "
            "sinon, clone le dépôt à nouveau dans ton dossier personnel, hors de OneDrive ou iCloud.",
        )
    return True, "traces : dossier traces/ inscriptible", None


def signaler_traces_non_poussees(racine):
    """Une ligne d'information, qui ne fait jamais échouer le contrôle (SPEC § 7.4).

    Sans git, ou sans dépôt d'équipe auquel comparer, elle ne dit rien.
    """
    non_poussees = pousser.decompte(pousser.traces_non_poussees(racine) or [])
    if non_poussees:
        print(f"  INFO   traces non poussées : {non_poussees} ; pour les envoyer, uv run kit pousser")


def fichiers_du_depot(racine):
    """Les fichiers suivis par git, et ceux qu'un `git add .` ajouterait. None sans git ou hors d'un dépôt."""
    try:
        resultat = subprocess.run(
            ["git", "--no-optional-locks", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=racine, capture_output=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if resultat.returncode != 0:
        return None
    return sorted({nom for nom in resultat.stdout.decode("utf-8", errors="replace").split("\0") if nom})


def verifier_cle_hors_depot(racine):
    """Aucun fichier du dépôt, suivi ou prêt à l'être, ne contient ce qui ressemble à une clé d'API."""
    noms = fichiers_du_depot(racine)
    if noms is None:
        return True, "clé dans le dépôt : pas de dépôt git ici, rien ne peut partir dans un commit", None
    en_usage = cle.lire()
    suspects = []
    for nom in noms:
        try:
            texte = (racine / nom).read_bytes().decode("utf-8", errors="ignore")
        except OSError:
            continue  # un fichier supprimé, pas encore enregistré
        if cle.MOTIF_CLE.search(texte) or (en_usage and len(en_usage) >= 8 and en_usage in texte):
            suspects.append(nom)
    if suspects:
        return (
            False,
            f"clé dans le dépôt : {', '.join(suspects)} contient ce qui ressemble à une clé d'API.",
            "retire la clé de ce fichier avant tout commit ; elle vit dans ton dossier personnel, "
            "où uv run kit cle la range. Si elle est déjà poussée, préviens l'animateur : elle doit être révoquée.",
        )
    return True, f"clé dans le dépôt : aucune, dans les {len(noms)} fichiers suivis ou prêts à l'être", None


def verifier_cle():
    """Une clé est enregistrée, dans le dossier personnel ou dans la variable ALLERGYLAB_CLE."""
    valeur, provenance = cle.trouver()
    if not valeur:
        return False, "clé d'API : absente.", "lance uv run kit cle, puis colle la clé que l'animateur t'a donnée."
    return True, f"clé d'API : présente ({provenance})", None


def verifier_appel():
    """Un appel minimal au modèle du développement aboutit."""
    from kit import modele  # importé ici seulement : litellm est long à charger, et --hors-ligne s'en passe

    try:
        identifiant, jetons, cout = modele.essai()
    except modele.ErreurModele as erreur:
        return False, f"appel au modèle : {erreur.texte}", erreur.que_faire
    return True, f"appel au modèle : {identifiant} a répondu ({jetons} jetons, coût estimé {modele.en_dollars(cout)})", None


def afficher(bon, texte, que_faire):
    print(f"  {'OK   ' if bon else 'ÉCHEC'}  {texte}")
    if not bon:
        print(f"         Que faire : {que_faire}")


def controler(racine=RACINE, hors_ligne=False):
    """Fait toutes les vérifications, les affiche, rend 0 (réussite) ou 1 (échec)."""
    print("Contrôle du kit AllergyLab")
    try:
        attendu = lire_attendu(racine)
    except (OSError, tomllib.TOMLDecodeError):
        afficher(False, "données : kit/empreintes.toml est absent ou illisible.", RESTAURER_KIT)
        print("ÉCHEC")
        return 1
    lignes = verifier_donnees(racine, attendu)
    for ligne in lignes:
        afficher(*ligne)
    ligne_tableau, tableau = verifier_tableau(racine, attendu)
    suite = [
        ligne_tableau, verifier_dictionnaire(racine, tableau), verifier_equipe(racine), verifier_traces(racine),
    ]
    for ligne in suite:
        afficher(*ligne)
    signaler_traces_non_poussees(racine)
    lignes += suite
    lignes.append(verifier_cle_hors_depot(racine))
    afficher(*lignes[-1])
    if hors_ligne:
        print("  --     clé d'API et appel au modèle : non vérifiés (--hors-ligne)")
    else:
        lignes.append(verifier_cle())
        afficher(*lignes[-1])
        if lignes[-1][0]:
            lignes.append(verifier_appel())
            afficher(*lignes[-1])
        else:
            print("  --     appel au modèle : non tenté, faute de clé")
    reussi = all(bon for bon, _, _ in lignes)
    print("RÉUSSITE" if reussi else "ÉCHEC")
    return 0 if reussi else 1
