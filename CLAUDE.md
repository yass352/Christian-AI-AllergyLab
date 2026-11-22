# Kit AllergyLab : règles de travail

Ce dépôt est le kit de démarrage d'une semaine intensive à l'EFREI, du 16 au 20 novembre 2026. Vingt étudiants de deuxième année, bases de Python, l'installent sur leur portable personnel et construisent dessus un agent d'analyse de données de santé. Le dépôt est public et le kit s'y développe directement : tout commit poussé est lu par eux, ce fichier compris, messages de commit compris.

## Deux sortes de dépôts

Ce fichier sert dans le dépôt du kit et dans les dépôts d'équipe, qui en sont des copies. `equipe.toml` dit où l'on est.

- `equipe = "accueil"` : c'est le dépôt du kit. Tout ce qui suit s'applique.
- `equipe = "equipe-N"` : c'est le dépôt d'une équipe d'étudiants, et les règles 1, 2, 6 et 7 ne s'y appliquent pas. Dans `equipe/`, `README.md` et `JOURNAL.md`, l'équipe écrit librement ses outils d'analyse, sa consigne, sa règle d'abstention, ses questions de contrôle et leurs réponses. Elle ajoute une bibliothèque par `uv add` et appelle le modèle dans la limite de sa cagnotte. Les règles 3, 4 et 5 valent toujours. Le dossier `kit/` ne se modifie pas : l'animateur le met à jour.

## Règle zéro

Lire `SPEC.md` avant toute modification. Elle fait foi. Si une demande contredit la spec ou une règle ci-dessous : s'arrêter, le signaler, ne pas improviser d'exception.

## Sept règles qui ne se négocient pas

1. **Aucune réponse.** Le dépôt ne contient aucune question de contrôle sur le fichier réel, aucune valeur attendue, aucun outil d'analyse, aucune règle d'abstention, aucune remarque sur ce que les données permettent ou non de conclure. Ni dans le code, ni dans les tests, ni dans un commentaire, ni dans un message de commit. Les seuls faits admis sur le fichier réel : son empreinte, sa forme, et le contenu de `kit/colonnes.csv`.
2. **La frontière.** Rien du dépôt privé de production pédagogique n'entre ici : ni corrigé, ni sujet, ni dossier de passation, ni remote git partagé. Ne jamais chercher, lire ou copier un fichier hors de ce dépôt, sauf ceux que le prompt nomme.
3. **Aucune donnée personnelle.** Ni nom, ni prénom, ni identifiant GitHub, ni adresse, dans aucun fichier, aucune trace, aucun test.
4. **Aucun secret.** La clé d'API vit hors du dépôt. Elle n'est jamais affichée, jamais journalisée, jamais écrite dans une trace, jamais placée dans un fichier suivi par git.
5. **`donnees/` ne se modifie pas.** Ces fichiers sont ceux que leur éditeur a publiés. On ne les ouvre qu'en lecture. `.gitattributes` les déclare binaires ; ne pas y toucher.
6. **Aucune dépendance nouvelle sans accord.** Celles du verrouillage, et elles seules. smolagents reste en 1.26.0.
7. **Aucun appel payant sans que le prompt le demande.** Les tests ne touchent ni au réseau ni au modèle. Un appel réel au modèle n'a lieu que si le prompt le prévoit, sur le modèle de développement, et son nombre est annoncé dans le compte rendu.

## Carte du dépôt

```
kit/            le harnais fourni : chargement, modèle, traces, ligne de commande, tests
kit/exemple/    une table inventée de douze lignes, pour les tests et les démonstrations
kit/tests/      les tests du kit
equipe/         ce que l'équipe écrit : agent.py, consigne.md, outils/, questions/, analyse/
traces/         écrit par le kit à chaque exécution, versionné
donnees/        le fichier publié et son dictionnaire officiel
equipe.toml     identifiant de l'équipe
JOURNAL.md      journal de bord de l'équipe
SPEC.md         la spécification
```

Deux publics pour le code. `kit/` est lu par des étudiants curieux : il doit être court et clair. `equipe/` est modifié par des débutants : chaque fichier livré y tient sur un écran, sans abstraction, avec des commentaires qui disent pourquoi.

## Commandes

```
uv run kit installer      installe, vérifie les données, demande la clé
uv run kit cle            enregistre ou remplace la clé
uv run kit controle       RÉUSSITE (code 0) ou ÉCHEC (code 1) ; --hors-ligne saute l'appel au modèle
uv run kit agent "…"      pose une question à l'agent de l'équipe
uv run kit pousser        envoie les traces vers le dépôt de l'équipe
uv run kit evaluer        fait passer une batterie de questions à l'agent
uv run kit noter          note après coup une trace d'évaluation
uv run kit bilan          tableau des exécutions passées
uv run pytest -q          tous les tests, hors ligne
```

Tout passe par `uv run`. On n'active jamais d'environnement virtuel, on n'appelle jamais `pip`.

## Vocabulaire

- **Harnais** : tout ce qui entoure le modèle (boucle, outils, consigne, garde-fous, traces). Le kit est un harnais. C'est le mot à employer dans les textes destinés aux étudiants.
- **Harnais d'évaluation** : la partie qui note l'agent. Toujours en toutes lettres.
- **Abstention** : une réponse dont le statut dit « je ne peux pas conclure ». Le kit en fixe la forme, jamais la règle.
- **Trace** : ce que le kit écrit à chaque exécution. **État** : une copie datée du travail de l'équipe.
- **Ouvert, fermé** : selon que l'agent reçoit le tableau et peut importer pandas, ou ne passe que par les outils.

## Écrire pour ce public

- Tout en français : code, noms, commentaires, messages. Les noms de fichiers, de dossiers, de fonctions et de variables sont en minuscules, sans accent ni espace. Les messages affichés gardent leurs accents.
- Un message d'erreur dit ce qui ne va pas, puis quoi faire, en une ou deux phrases. Jamais de trace d'exécution Python brute devant un étudiant, sauf avec `--detail`.
- Pas d'emoji, pas de couleur indispensable à la lecture.
- Les codes de sortie comptent : 0 pour une réussite, 1 pour un échec. Les commandes de vérification en dépendent.

## Trois systèmes, un seul code

Le kit tourne sous macOS, Windows et Linux, sans droits d'administrateur. Une matrice GitHub Actions le prouve. Avant d'écrire une ligne, se demander ce qu'elle fait sous Windows.

- Chemins : `pathlib` partout, jamais de séparateur écrit en dur. Le dossier personnel d'un étudiant peut contenir des espaces et des accents.
- Encodage : toujours `encoding="utf-8"` à l'ouverture d'un fichier. La sortie console est réglée en UTF-8 au démarrage.
- Fins de ligne : réglées par `.gitattributes`. Un fichier de `donnees/` dont une fin de ligne change n'a plus la bonne empreinte.
- Aucun appel à un interpréteur de commandes, aucun script `.sh` ou `.bat` dans le parcours de l'étudiant.
- git peut manquer : le kit tourne aussi depuis une archive décompressée. Toute lecture de l'état git prévoit ce cas.

## Le modèle et le budget

- Un seul module parle au modèle. Il reprend à l'identique la façon de faire que `kit/tester-la-stack.py` valide.
- Deux modèles, pas d'autre : celui du développement et celui des passes officielles. Leurs identifiants et leurs tarifs sont dans un fichier de réglages, nulle part ailleurs.
- Une limite de dépense atteinte est une erreur finale : message clair, trace écrite, aucune nouvelle tentative. Une saturation passagère donne droit à deux nouvelles tentatives espacées.
- Chaque exécution affiche ses jetons et son coût estimé.

## L'agent et la sécurité

- L'agent livré est un `CodeAgent` ouvert. Il exécute sur la machine de l'étudiant du code écrit par un modèle. Le README le dit sans détour.
- Les deux lignes qui ouvrent l'accès aux données, dans `equipe/agent.py`, restent visibles, commentées, et faciles à retirer.
- Un outil rend des valeurs simples, jamais le tableau. Un outil ne passe jamais un texte venu du modèle à `eval`, `exec`, `query` ou une fonction du même genre.
- Ne jamais présenter la fermeture de l'accès comme une protection complète. Ce n'est pas un bac à sable.
- Ce dépôt ne contient aucun code d'attaque : pas de contournement de l'interpréteur, pas de fichier piégé.

## Les traces

- Liste fermée de champs, format versionné. Un champ nouveau se décide dans la spec, pas dans le code.
- Un fichier par exécution, nommé par son horodatage et un suffixe aléatoire. Jamais de fichier commun qu'on complète.
- Avant toute écriture : le chemin du dossier personnel, le nom d'utilisateur du système et tout motif de clé sont remplacés.
- La trace s'écrit même quand l'exécution échoue ou est interrompue.

## Tests

- Un test par règle de ce fichier qui peut se vérifier par une machine.
- Les tests tournent sans réseau, sans clé, sans le modèle. Un faux modèle joue son rôle.
- Les tests de chargement portent sur la table inventée. Du fichier réel, on ne vérifie que l'empreinte et la forme.
- Aucun test rouge livré « à faire passer » par les étudiants.

## Git

- Un commit par chantier, message en français, à l'infinitif.
- `git add` avec des chemins explicites. Jamais `-A`, jamais `-a`, jamais `.`.
- Ne pas pousser, ne pas créer de dépôt, ne pas modifier l'organisation, sauf si le prompt le demande.
- Dans le dépôt du kit, ne jamais modifier `equipe/`, `equipe.toml`, `README.md` ni `JOURNAL.md` : ces fichiers appartiennent aux équipes, et un changement y ferait échouer la mise à jour de leurs dépôts.

## Fini, c'est quand

Un travail est fini quand la commande « Fini quand » du prompt rend le résultat attendu, et que `uv run pytest -q` puis `uv run kit controle --hors-ligne` rendent tous deux le code 0. Le compte rendu donne la sortie de ces commandes et la liste des fichiers créés ou modifiés. Un doute sur la spec se signale dans le compte rendu ; il ne se tranche pas en silence.
