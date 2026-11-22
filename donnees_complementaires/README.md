# Données complémentaires

Des données ouvertes françaises sur les allergies, ajoutées par l'équipe à côté du fichier du kit. `donnees/` n'est pas touché : le kit vérifie son empreinte, et le jeu « Allergen Chip Challenge » reste la seule source sur les patients.

Toutes ces données ont été récupérées le 19 novembre 2026 sur [data.gouv.fr](https://www.data.gouv.fr), sous **Licence Ouverte 2.0** : réutilisation libre, à condition de citer la source et la date.

## Les fichiers

| Fichier | Ce qu'il contient | Source | Tel que publié ? |
|---|---|---|---|
| `acc-dictionnaire-codes.csv` | Les tables de codes du dictionnaire officiel (`donnees/acc-dictionnaire-final.xls`), une ligne par code : variable, code, libellé. 137 codes, 28 tables. | Société Française d'Allergologie, [Allergen Chip Challenge](https://www.data.gouv.fr/datasets/allergen-chip-challenge) | Non : recopie du `.xls` en CSV, sans interprétation (`equipe/analyse/extraire_dictionnaire.py`) |
| `acc-dictionnaire-english.pdf` | La version anglaise du même dictionnaire, publiée avec le jeu de données. | Société Française d'Allergologie, même page | Oui |
| `rnsa-pollens-mensuels-france.csv` | Calendrier pollinique moyen de la France métropolitaine : pour 27 pollens et moisissures et chaque mois, la concentration moyenne dans l'air (grains par m³ et par jour). | Ministère chargé de la santé, [Données historiques de surveillance des pollens et des moisissures](https://www.data.gouv.fr/datasets/donnees-historiques-de-surveillance-des-pollens-et-des-moisissures) (Réseau National de Surveillance Aérobiologique, 1987-2024) | Non : préparé par `equipe/analyse/preparer_pollens.py` |
| `rnsa-pollens-annuels-france.csv` | Pour chaque taxon et chaque année de 1987 à 2024 : l'indice pollinique annuel médian des capteurs de métropole (somme des concentrations journalières sur l'année). | Même source | Non : même script |
| `rnsa-pollens-mensuels-stations.csv` | Le calendrier mois par mois de chacun des 125 capteurs (119 en métropole), toutes années confondues, avec le nombre de jours et d'années mesurés. | Même source | Non : même script |
| `lyon-risque-allergique-pollens.csv` | Les bulletins hebdomadaires du risque allergique lié aux pollens dans la Métropole de Lyon, de juin 2014 à mars 2025 : pollens dominants, quantité, niveau de risque de 0 à 5, commentaire. 2 252 lignes, séparateur « ; ». | Métropole de Lyon, [Risque allergique lié aux pollens (historique)](https://www.data.gouv.fr/datasets/risque-allergique-lie-aux-pollens-de-la-metropole-de-lyon-historique) | Oui, export complet de l'API |

Les colonnes `allergenes_acc` des fichiers RNSA disent quelles colonnes de dosage du tableau correspondent à chaque pollen (`bouleau` : `Bet_v`). C'est un choix de l'équipe, fait d'après les noms latins.

## Ce qu'on peut en faire, et ce qu'on ne peut pas

- Ces fichiers décrivent l'air, pas les patients du tableau.
- Dans le tableau, la région et le département sont anonymisés (`regionA`, `deptY`) et l'année du prélèvement n'est pas donnée. Le seul lien possible est le mois du prélèvement (`Blood_Month_sample`) : on peut mettre côte à côte la saison d'un pollen et le mois des prises de sang, pas rattacher un patient à un capteur.
- L'agent reçoit chaque fichier CSV déjà chargé (`pollens_mois`, `pollens_annees`, `pollens_capteurs`, `risque_lyon`, `dictionnaire` : `equipe/outils/acces.py`) et l'analyse comme le tableau. Il lit aussi le calendrier national avec l'outil `calendrier_pollinique` ; l'interface l'affiche dans la page Données.

## Comment les fichiers RNSA sont calculés

Le ministère publie un fichier Excel par capteur et par année (archive `BDD_daily`, 65 Mo, non versionnée ici). Le script :

- compte un mois comme mesuré quand la colonne « Total Taxons » y dépasse 0 ;
- dans un mois mesuré, lit une case vide comme 0 grain ;
- écarte, pour une moisissure, le capteur-année où elle n'a jamais été comptée ;
- ne garde, pour les moyennes nationales, que les capteurs de métropole (Corse comprise) : ni Andorre, ni Bruxelles, ni l'outre-mer ;
- pour l'indice annuel, ne garde que les capteurs mesurés au moins six mois dans l'année.

Pour le refaire : télécharger et décompresser `BDD_daily` depuis la page du jeu, puis, depuis la racine du dépôt :

```
uv run --with xlrd --with openpyxl python equipe/analyse/preparer_pollens.py <dossier BDD_daily>
uv run --with xlrd python equipe/analyse/extraire_dictionnaire.py
```

`--with` prête les lecteurs Excel le temps de la commande, sans les ajouter aux dépendances du projet.

## Empreintes SHA-256

```
ada629eaa497e74326ce6e015b92a887d3d5f7df3f519120ea7a76ef73989b29  acc-dictionnaire-codes.csv
3a07475b8146b6a5ef2941944414994f355fe6cd93bdcfab367985ecbfb09783  acc-dictionnaire-english.pdf
13aa44414f305b5d6f6763dec4e14780cfdd693d8e8216dded4d91e644e2efa5  lyon-risque-allergique-pollens.csv
605d52b848921f6339ba1cdbcda3fe347bad08fa4149b16643005aad95d03a3f  rnsa-pollens-annuels-france.csv
67ffaeeec72b65af2faecae6f75894440f23a16d69f60441066051d06a479839  rnsa-pollens-mensuels-france.csv
e6e45cd91094dce60c2ee46b25735f3cb58170040c3df9a6b6acdeb397a807a1  rnsa-pollens-mensuels-stations.csv
```

`.gitattributes` déclare ces fichiers binaires : git ne change jamais leurs fins de ligne, et ces empreintes restent vraies.
