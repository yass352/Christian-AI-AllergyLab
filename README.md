# Christian AI · AllergyLab, équipe 1

Christian AI est l'agent d'analyse de l'équipe 1 pour la semaine AllergyLab de l'EFREI (16-20 novembre 2026). On lui pose une question en français sur le jeu de données « Allergen Chip Challenge » : il écrit et exécute du code Python, s'appuie sur les outils de l'équipe, puis rend une réponse en trois champs (statut, valeur, justification), ou s'abstient quand les données ne permettent pas de conclure.

Le projet repose sur le **harnais** fourni par le kit (`kit/`) : la boucle, le modèle, les garde-fous, les traces. L'équipe a écrit l'agent (`equipe/`), une interface web (`Frontend/` et `backend/`) et ajouté des données ouvertes complémentaires (`donnees_complementaires/`).

## Sommaire

- [Démarrer](#démarrer)
- [L'interface web](#linterface-web)
- [Notre agent](#notre-agent)
- [Les données](#les-données)
- [Tester](#tester)
- [Ce que le kit enregistre](#ce-que-le-kit-enregistre)
- [Ce qu'un agent ouvert peut faire](#ce-quun-agent-ouvert-peut-faire)
- [Dépannage](#dépannage)
- [Arborescence](#arborescence)

## Démarrer

Il faut deux outils sur la machine : git et uv. Clone le dépôt dans ton dossier personnel, hors d'un dossier synchronisé (OneDrive, iCloud), puis, depuis le dossier du dépôt :

```
uv run kit installer
uv run kit controle
uv run kit agent "Combien de lignes compte le tableau ?"
```

`uv run kit` seul affiche la liste des commandes. Chaque commande rend le code 0 quand tout va bien, 1 sinon. Tout passe par `uv run` : pas d'environnement virtuel à activer, pas de `pip`.

`installer` te demande la clé d'API que l'animateur t'a donnée : colle-la dans le terminal, rien ne s'affiche, c'est normal. Elle se range dans ton dossier personnel (`.allergylab/cle`), hors du dépôt : elle ne peut pas partir dans un commit. Pour la remplacer : `uv run kit cle`.

## L'interface web

Une interface de discussion avec Christian AI, qui tourne uniquement sur ta machine. Il faut en plus Node.js 20.19 ou plus récent.

**Terminal 1**, à la racine du dépôt, le serveur local :

```
uv run uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

**Terminal 2**, l'interface :

```
cd Frontend
npm install
npm run dev
```

Puis ouvre `http://127.0.0.1:5173`.

- **Assistant** : la conversation. Pendant que l'agent travaille, l'avatar de Christian AI passe en mode réflexion (anneau animé et bulle de pensée), et la bulle « Christian AI réfléchit… » s'affiche avec le temps écoulé, comme l'indicateur de saisie d'une messagerie. Chaque réponse montre son statut, sa valeur, sa justification, le code écrit par l'agent (« Raisonnement de l'agent »), les jetons, le coût estimé et la durée. « Écouter » la lit à voix haute avec la synthèse vocale du navigateur, gratuite et hors ligne. Le micro, à côté du bouton d'envoi, dicte la question en français avec la reconnaissance vocale du navigateur : aucune bibliothèque, aucun appel à notre modèle, aucun jeton. Dans un Chrome à jour, le premier clic installe le français sur l'ordinateur (un téléchargement, une seule fois) ; ensuite la dictée marche sans internet et le son ne quitte pas l'ordinateur. Les navigateurs qui ne savent pas le faire (Edge, Brave, un Chrome ancien) envoient le son à leur propre service en ligne : il leur faut internet, et le message sous la zone de saisie le dit quand il manque. Le survol du micro dit lequel des deux est utilisé. Firefox n'a pas cette fonction : le micro n'y apparaît pas. Une salutation ou une question hors sujet reçoit une réponse courte, marquée « Hors sujet », sans appel au modèle.
- **Données** : les chiffres clés du tableau, les mois de prélèvement à côté du calendrier pollinique de France métropolitaine, et les colonnes les moins renseignées. Le navigateur ne reçoit que des statistiques agrégées, jamais une ligne de patient.
- **À propos** : comment l'agent répond, et ce qu'il faut savoir avant de s'en servir.

Le serveur ne fait qu'appeler `uv run kit agent` : la validation de la réponse, le décompte des jetons et la trace restent ceux du kit. Il accepte une question à la fois, de 3 à 2 000 caractères, et coupe l'agent au bout de cinq minutes. Ses points d'entrée :

| Méthode | Adresse | Ce qu'elle rend |
|---|---|---|
| GET | `/api/health` | l'état du serveur (sans tester la clé : c'est le rôle de `uv run kit controle`) |
| GET | `/api/dataset/summary` | des statistiques agrégées du tableau |
| GET | `/api/pollens/calendar` | le calendrier pollinique moyen, depuis `donnees_complementaires/` |
| POST | `/api/agent/ask` | `{"question": "…"}` donne la réponse de l'agent, ses étapes (le code seul), ses jetons et sa durée |

L'interface est faite pour un usage local. Ne la rends jamais accessible depuis ton réseau ou internet : elle n'a pas d'authentification, et l'agent exécute du code sur ta machine. Ce n'est pas un outil de diagnostic médical.

## Notre agent

`equipe/agent.py` est un `CodeAgent` de smolagents, **ouvert** : il reçoit le tableau et les cinq tables des données complémentaires (voir [Les données](#les-données)), et peut importer pandas. Par rapport à l'agent minimal du kit, cinq choses changent.

**Une consigne complète** (`equipe/consigne.md`) : l'agent raisonne en allergologue qui analyse des données. Son expertise explique et interprète, le tableau montre : toute réponse s'appuie sur au moins un calcul ou un outil, aucun chiffre ne vient de sa mémoire, et une question générale (« Qu'est-ce que la réactivité croisée ? ») reçoit une explication illustrée par les données. La consigne décrit aussi ce que contient le tableau (le bloc clinique et le bloc dosage, les trois puces, les codes « 9 = non renseigné », les cellules à plusieurs codes, les colonnes anonymisées, les unités), une façon de raisonner en cinq temps (comprendre, chercher, analyser, interpréter, conclure), la règle d'abstention de l'équipe, et la forme attendue de la valeur et d'une justification en trois phrases : comment le résultat est obtenu, ce qu'il veut dire, sa limite.

**Dix outils** (`equipe/outils/`, un fichier par outil). Chacun rend une valeur simple, jamais le tableau, et lève une erreur qui dit quoi corriger quand on l'appelle mal :

| Outil | Ce qu'il fait |
|---|---|
| `chercher_colonnes` | les colonnes dont le nom contient un motif (`"Ara_h"`) |
| `decrire_colonne` | le bloc, les valeurs renseignées par puce, puis les valeurs fréquentes ou les statistiques |
| `compter_codes` | les patients par code d'une colonne clinique, cellules à plusieurs codes séparées |
| `codes_officiels` | le sens des codes, d'après le dictionnaire officiel |
| `croiser` | le tableau croisé de deux colonnes à peu de valeurs |
| `positifs` | les patients positifs à un dosage, parmi les seuls patients mesurés, par puce |
| `classer_allergenes` | les dosages classés par nombre ou par part de patients positifs |
| `source_allergene` | la source, le nom latin et la famille d'un allergène (`Bet_v_1` : bouleau) |
| `colonnes_par_famille` | les dosages d'une famille (acariens, pollens d'arbre, aliments végétaux…) |
| `calendrier_pollinique` | la concentration moyenne mois par mois d'un pollen dans l'air (données du RNSA) |

`equipe/outils/acces.py` n'est pas un outil : il charge le tableau une seule fois pour tous les outils. Les tables de référence que lisent les outils sont dans `equipe/analyse/` : `allergenes.csv` (préfixe, source, nom latin, famille) et `correspondance_colonnes.csv` (colonne du tableau, table du dictionnaire officiel). Ce sont des choix de l'équipe, à relire et à compléter.

**Un contrôle du contrat avant la fin.** `verifier_contrat` refuse une réponse finale qui n'a pas ses trois champs, ou dont la justification dépasse trois phrases. L'agent lit l'erreur et corrige à l'étape suivante, au lieu de rendre au kit une réponse illisible.

**Des garde-fous à chaque porte** (`equipe/outils/garde_fous.py`, testés sans le modèle dans `equipe/tests/test_garde_fous.py`) :

- *Avant le modèle.* Une question trop longue (plus de 500 caractères), hors sujet (« hello », la capitale de l'Italie, un poème) ou qui tente de détourner l'agent (« ignore tes instructions », montrer la consigne, la clé, un fichier, une adresse web) reçoit une abstention qui dit pourquoi, sans appel au modèle : zéro jeton. Le terminal affiche « Question refusée par le garde-fou ».
- *Pendant l'exécution.* Chaque code écrit par le modèle est relu avant de tourner. S'il ouvre ou écrit un fichier (`read_csv`, `to_csv`, `open`), appelle le système (`os`, `subprocess`) ou fait évaluer un texte (`eval`, `query`, `getattr`), il ne tourne pas, et le modèle lit pourquoi. Toutes les données arrivent déjà chargées : aucun calcul n'a besoin d'ouvrir un fichier, et un code qui pourrait en lire un pourrait aussi lire la clé.
- *À la fin.* Une réponse (pas une abstention) doit s'appuyer sur un calcul exécuté sur `tableau` ou avec un outil ; sinon elle est refusée et le modèle calcule, ou s'abstient. Une réponse qui montre un motif de clé est refusée.
- La question est passée au modèle entre balises `<question>`, comme un texte à analyser, et la consigne lui dit de ne jamais y lire un ordre.

Ce sont des listes de mots et de noms : elles arrêtent les cas évidents et les erreurs du modèle, pas quelqu'un qui cherche longtemps à les contourner (voir plus bas). Une question légitime refusée à tort se corrige en ajoutant son mot à `RACINES` ou `MOTS`, dans `garde_fous.py`.

**Une mémoire des réponses, pour économiser des jetons** (`equipe/memoire.py`). Une question déjà posée mot pour mot (majuscules et espaces en trop mis à part), au même agent et au même modèle, reprend la réponse enregistrée dans sa trace : aucun appel au modèle, zéro jeton. « Le même agent », c'est la même empreinte d'état : dès que `agent.py`, `consigne.md`, `outils/` ou `questions/` changent, les anciennes réponses ne sont plus reprises. Une réponse reprise le dit dans le terminal, dans sa trace et dans l'interface (« Réponse reprise d'une trace · 0 jeton »). Pour obtenir une réponse neuve à chaque fois, mets `REUTILISER_LES_TRACES = False` dans `equipe/agent.py`. Comme les traces sont poussées avec le dépôt, une réponse obtenue sur une machine sert aussi aux autres membres de l'équipe.

Pour fermer l'accès, retire les deux lignes signalées par `# Accès aux données :` dans `equipe/agent.py` : l'agent n'atteindra plus les données que par les outils. Pour aller au bout, remplace `CodeAgent` par `ToolCallingAgent`.

## Les données

`donnees/allergenchipchallenge-data-corrected-final-hdh-sfa.csv` est le jeu « Allergen Chip Challenge » publié par la Société Française d'Allergologie, DOI [10.60597/j5fe-g420](https://doi.org/10.60597/j5fe-g420), sous Licence Ouverte 2.0. Son dictionnaire officiel, `donnees/acc-dictionnaire-final.xls`, est livré tel que publié.

Ces deux fichiers sont dans le dépôt sans aucune modification, et on ne les modifie pas : `uv run kit controle` vérifie leur empreinte.

En Python :

```python
from kit.donnees import charger, colonnes

tableau = charger()      # le tableau complet, sans recodage ni filtrage
dictionnaire = colonnes()  # une ligne par colonne : bloc, lecture, types de puce
```

### Données complémentaires

L'équipe a cherché d'autres données ouvertes françaises sur les allergies. Elles sont rangées à part, dans `donnees_complementaires/`, toutes sous Licence Ouverte 2.0 :

| Fichier | Source |
|---|---|
| `acc-dictionnaire-codes.csv` | le dictionnaire officiel recopié en CSV, une ligne par code |
| `acc-dictionnaire-english.pdf` | la version anglaise du dictionnaire, publiée avec le jeu |
| `rnsa-pollens-mensuels-france.csv`, `rnsa-pollens-annuels-france.csv`, `rnsa-pollens-mensuels-stations.csv` | les relevés de pollens et de moisissures du Réseau National de Surveillance Aérobiologique, 125 capteurs de 1987 à 2024 (Ministère chargé de la santé) |
| `lyon-risque-allergique-pollens.csv` | les bulletins hebdomadaires de risque allergique de la Métropole de Lyon, 2014-2025 |

Ces données décrivent l'air, pas les patients. Le tableau ne donne ni la région réelle ni l'année du prélèvement : on ne peut rapprocher les deux que par le mois. Sources exactes, règles de calcul, commandes pour tout refaire et empreintes : [`donnees_complementaires/README.md`](donnees_complementaires/README.md).

L'agent reçoit chaque fichier CSV déjà chargé, à côté de `tableau`, et l'analyse avec pandas comme le tableau (`equipe/outils/acces.py`, colonnes décrites dans `equipe/consigne.md`) :

| Variable | Fichier |
|---|---|
| `pollens_mois` | `rnsa-pollens-mensuels-france.csv` |
| `pollens_annees` | `rnsa-pollens-annuels-france.csv` |
| `pollens_capteurs` | `rnsa-pollens-mensuels-stations.csv` |
| `risque_lyon` | `lyon-risque-allergique-pollens.csv` (dates lues comme des dates, `quantite` comme un nombre) |
| `dictionnaire` | `acc-dictionnaire-codes.csv` |

Le PDF anglais n'est pas une table : il reste une référence à lire.

Aucune ligne n'a été ajoutée au tableau des patients : il vient d'une seule étude, et d'autres données n'ont ni les mêmes patients ni les mêmes mesures.

## Tester

```
uv run pytest -q              tous les tests, hors ligne
uv run pytest -q equipe/tests les tests de l'équipe seulement
uv run kit controle --hors-ligne
cd Frontend && npm run build  vérifie le TypeScript et construit l'interface
```

Les tests de l'équipe (`equipe/tests/`) tournent sur la table inventée de douze lignes (`kit/exemple/mini.csv`), sans réseau, sans clé, sans le modèle : un faux modèle joue son rôle. Ils vérifient chaque outil sur des valeurs comptées à la main, que l'agent appelle bien ses outils et lit le tableau, que le contrôle du contrat fait corriger une réponse hors contrat, et qu'aucun outil ne passe un texte à `eval`, `exec` ou `query`.

## Ce que le kit enregistre

Le kit garde une trace de chaque exécution, seul, sans que tu aies à y penser. Tout s'écrit dans le dossier `traces/` de ton dépôt. Le kit n'envoie ces traces nulle part : elles partent avec le reste de ton travail, à chaque `git push`. Une question posée depuis l'interface web passe par `uv run kit agent` : elle laisse la même trace.

**À chaque question posée à l'agent** (`uv run kit agent`), un fichier JSON dans `traces/appels/<jour>/`, nommé par l'heure (en temps universel, UTC) et un suffixe tiré au hasard. Il contient ces champs, et aucun autre :

| Champ | Contenu |
|---|---|
| `format` | la version du format de la trace |
| `horodatage` | la date et l'heure de l'appel, en UTC |
| `equipe` | l'identifiant de `equipe.toml` |
| `kit` | la version du kit |
| `etat` | l'empreinte de l'état de ton travail (voir plus bas) |
| `commit`, `modifie` | le commit git en cours, et s'il y a des modifications pas encore enregistrées ; vides hors d'un dépôt git |
| `moteur`, `modele` | ce qui fait tourner l'agent, et le modèle appelé |
| `question`, `reponse` | la question posée et la réponse rendue |
| `etapes` | les étapes de l'agent : le code qu'il a écrit, ses résultats tronqués |
| `jetons`, `cout_estime` | les jetons consommés et leur coût estimé |
| `duree_s` | la durée de l'appel, en secondes |
| `erreur` | l'erreur, s'il y en a eu une |

La trace s'écrit même quand l'appel échoue ou que tu l'interromps.

**À chaque état nouveau de ton travail**, une copie de `equipe/agent.py`, `equipe/consigne.md`, `equipe/outils/` et `equipe/questions/` dans `traces/etats/<empreinte>/`. L'empreinte résume le contenu de ces fichiers : tant qu'ils ne changent pas, rien n'est recopié. Chaque version de ton agent est ainsi gardée, que tu aies fait un commit ou non.

**Rien qui porte un nom.** Aucune trace ne contient ton nom d'utilisateur, le nom de ta machine, l'auteur des commits, ni rien qui te reconnaisse d'une exécution à l'autre. Avant toute écriture, le kit remplace le chemin de ton dossier personnel par `~`, ton nom d'utilisateur par `<utilisateur>`, et tout ce qui a la forme d'une clé d'API par `<clé>`.

Une limite : le texte libre. Ce que tu tapes dans une question, ce que tu écris dans ton code est recopié tel quel, et aucune machine ne sait y reconnaître un prénom. La règle est donc simple : on signe en équipe, jamais d'un prénom. L'historique git, lui, porte l'auteur de chaque commit ; il appartient aux membres de l'équipe et n'entre pas dans les traces.

**À quoi cela sert.** Pendant la semaine, à retrouver une erreur de l'agent avec ses étapes sans avoir pensé à faire une capture, à comparer ton agent d'un jour à l'autre, et, dans notre équipe, à ne pas repayer une question déjà posée (voir la mémoire des réponses, plus haut). Après la semaine, `traces/`, `JOURNAL.md` et `equipe.toml` sont collectés dans chaque dépôt d'équipe pour monter un dossier de valorisation de la semaine, sans nom d'étudiant. Ne supprime pas `traces/` : pousse-le avec le reste.

## Ce qu'un agent ouvert peut faire

L'agent de `equipe/agent.py` est un `CodeAgent` de smolagents, **ouvert** : à chaque étape, le modèle écrit du code Python, et ce code s'exécute sur ton portable, avec tes droits, sans que personne l'ait relu.

- Ce code peut lire et écrire les fichiers de ton compte, et accéder au réseau. Ta clé d'API est un fichier de ton compte : un agent ouvert peut la lire comme n'importe quel autre. La vraie protection de la clé, c'est le plafond de dépense de ton équipe, et sa révocation.
- Deux lignes de `equipe/agent.py` ouvrent les données à l'agent, chacune signalée par un commentaire : celle qui autorise son code à importer pandas, celle qui lui passe le tableau complet et les données complémentaires. Tant qu'elles sont là, les outils de ton équipe ne sont qu'une option parmi d'autres pour lui.
- Retirer ces deux lignes **ferme** l'accès : l'agent écrit toujours du code, mais il n'atteint plus les données que par les outils de `equipe/outils/`. Fermer réduit ce qu'il peut faire ; ce n'est pas un bac à sable, et la documentation de smolagents le dit elle-même de son interpréteur.
- Un outil qui rend le tableau lui-même rouvre tout. Un outil rend une valeur simple : un nombre, un texte, une courte liste.
- Les garde-fous de l'équipe (`equipe/outils/garde_fous.py`) relisent la question et le code avant qu'il tourne. Ils réduisent le risque, ils ne l'éliminent pas : une liste de noms interdits se contourne. Ce n'est pas un bac à sable non plus.
- Le bout de ce chemin : remplacer `CodeAgent` par `ToolCallingAgent`, qui n'exécute aucun code et n'appelle que les outils. Le kit a aussi un repli, `kit/boucle_maison.py`, une boucle d'outils qui n'exécute aucun code écrit par le modèle ; son mode d'emploi est en tête du fichier.
- La seule isolation réelle est de faire tourner l'agent sur une machine distante, pas sur ton portable.
- L'interface web ne change rien à tout cela : elle lance le même agent, sur la même machine.

Jusqu'où fermer est une décision de ton équipe, qu'elle justifie par ses scores.

**Ce que coûte une question.** Chaque `uv run kit agent` affiche ses jetons et leur coût estimé ; l'interface les affiche sous chaque réponse et en fait le total de la session. Par défaut, l'agent fait huit étapes au plus par question et ses sorties sont tronquées (`kit/reglages.toml`) : ce sont des réglages, pas des verrous. La seule vraie limite est la cagnotte de ton équipe. Quand elle est épuisée, le kit affiche « cagnotte épuisée », écrit la trace et ne retente rien : va voir Adrien.

## Dépannage

| Ce qui s'affiche | Quoi faire |
|---|---|
| « Serveur inaccessible » dans l'interface | le terminal 1 ne tourne pas, ou pas sur le port 8000 : relance `uv run uvicorn backend.main:app --host 127.0.0.1 --port 8000` |
| « La clé d'API est absente ou refusée » | `uv run kit cle`, puis `uv run kit controle` |
| « L'agent a échoué » | pose la même question dans le terminal, `uv run kit agent "…"`, pour lire le message du kit |
| « L'agent répond déjà à une question » | une seule question à la fois : attends la réponse en cours |
| « Christian AI réfléchit… » très longtemps | l'agent retente peut-être après une saturation de l'API ; regarde le terminal 1, puis la dernière trace dans `traces/appels/` |
| Pas de bouton « Écouter » | le navigateur n'a pas de synthèse vocale ; le reste fonctionne |

## Arborescence

```
kit/                       le harnais fourni par le kit ; on n'y touche pas
equipe/agent.py            l'agent : CodeAgent, outils, contrôle du contrat
equipe/memoire.py          la mémoire des réponses, lue dans traces/
equipe/consigne.md         la consigne de l'agent, règle d'abstention comprise
equipe/outils/             un fichier par outil, plus acces.py
equipe/analyse/            tables de référence de l'équipe et scripts de préparation
equipe/tests/              les tests de l'équipe, hors ligne
equipe/questions/          les questions de contrôle de l'équipe
donnees/                   le fichier publié et son dictionnaire officiel, jamais modifiés
donnees_complementaires/   les données ouvertes ajoutées par l'équipe, avec leur README
backend/                   le serveur local (FastAPI)
Frontend/                  l'interface (React, TypeScript, Vite)
traces/                    écrit par le kit à chaque exécution, versionné
JOURNAL.md                 le journal de bord de l'équipe
```
