# Les_Nameks — guide de déploiement

Ce guide permet à un groupe qui découvre le projet de lancer le simulateur sous Windows, puis d'enregistrer ses statistiques sur une VM Debian. **Suivez les étapes dans l'ordre, sans en sauter.** Chaque étape se termine par un résultat attendu : ne passez à la suivante que lorsque vous l'avez obtenu.

## Ce que fait le projet

Les_Nameks est un simulateur pédagogique de circulation routière. L'application PyQt6 représente les routes par un graphe pondéré, calcule les chemins avec Dijkstra, puis anime des véhicules, des feux et des véhicules prioritaires. Elle affiche six mesures et les envoie au serveur Debian. Le serveur Python reçoit les messages par TCP et les enregistre dans MariaDB.

Les composants réseau sont simples : le client ouvre une connexion TCP au serveur sur le port `5000`, envoie un objet JSON UTF-8 terminé par un saut de ligne, puis ferme la connexion. Des threads évitent de bloquer l'interface et permettent au serveur de traiter plusieurs clients. MariaDB n'est utilisée que par le serveur sur la VM, via PyMySQL. Ce service scolaire n'est pas conçu pour être exposé sur Internet.

## Vue d'ensemble du déploiement

| Étape | Où | Ce que l'on obtient |
| --- | --- | --- |
| 1. Préparer les fichiers | Windows | Le dossier `C:\Les_Nameks` |
| 2. Installer et lancer l'application | Windows | Le simulateur fonctionne (sans serveur) |
| 3. Installer le serveur | Debian | MariaDB et le serveur TCP en écoute sur le port 5000 |
| 4. Relier Windows à Debian | Windows + hyperviseur | `TcpTestSucceeded : True` |
| 5. Lancer la simulation complète | Windows | Les statistiques partent toutes les 5 s |
| 6. Vérifier la base | Debian | Les lignes apparaissent dans MariaDB |

L'application Windows fonctionne seule : les étapes 1 et 2 suffisent pour voir le simulateur. Le serveur Debian ne sert qu'à enregistrer les statistiques.

## Fichiers utiles

- `application/` : interface et simulation PyQt6. `interface.py` est le point de lancement.
- `reseau/client.py` et `reseau/serveur.py` : client Windows et serveur Debian.
- `deploiement_debian/` : script d'installation, fichiers SQL, `.env.example`, test de connexion et [guide Debian détaillé](deploiement_debian/README.md).
- `requirements.txt` : dépendances Python de l'application Windows.

## Architecture et déroulement d'une simulation

### Rôle des modules essentiels

| Module | Responsabilité et liens |
| --- | --- |
| `application/interface.py` | Contient `FenetrePrincipale`, assemble les widgets et minuteries, coordonne la simulation, les statistiques et l'envoi TCP. Elle utilise les autres modules de l'application. |
| `application/graphes.py` | Contient `Graphes`, le modèle des nœuds, routes pondérées et phases des feux. La scène et les véhicules interrogent ce modèle. |
| `application/dijkstra.py` | Calcule un chemin de poids minimal à partir de `Graphes.aretes`. Il est appelé lors de la création d'un `Vehicule`. |
| `application/vehicule.py` | Contient `Vehicule`, son itinéraire et sa progression normalisée sur l'arête en cours. Il consulte le graphe pour les feux. |
| `application/scene_graphe.py` | Contient `SceneGraphe`, dessine le réseau et traduit les clics souris en actions de création, déplacement et sélection. |
| `application/vue_graphe.py` | Contient `VueGraphe`, gère le zoom et le déplacement de la vue. |
| `application/graphe_test.py` | Fournit les positions, routes, feux et densités du réseau de démonstration. |
| `reseau/client.py` | Ouvre une socket TCP et envoie le message JSON du simulateur. |
| `reseau/serveur.py` | Accepte les connexions, valide le JSON et insère les six mesures dans MariaDB. |

### Qui appelle quoi ?

```text
Utilisateur → FenetrePrincipale
  → Graphe de test → Graphes + SceneGraphe
  → création de véhicule → Vehicule → dijkstra(Graphes)
  → QTimer (tick toutes les 20 ms)
      → Vehicule.avancer(Graphes.est_vert)
      → mise à jour du dessin et des statistiques
  → QTimer (toutes les 5 s) → JSON → verrou → thread d'envoi
      → reseau.client.envoyer_message → socket TCP
      → reseau.serveur → thread par connexion → validation JSON
      → MariaDB (INSERT des six valeurs)
```

`FenetrePrincipale` est le chef d'orchestre du programme graphique. `Graphes` ne dessine rien ; `SceneGraphe` dessine le modèle. Dijkstra ne déplace pas les véhicules : il fournit seulement une liste de nœuds à `Vehicule`. Le timer d'interface appelle ensuite `tick`, qui met à jour les états et leur représentation visuelle.

Le temps moyen est calculé à partir des trajets terminés et du temps de simulation active. Le relevé envoyé possède un champ `type` et six mesures. Le verrou empêche le démarrage d'un nouvel envoi si le précédent est encore actif ; le thread d'envoi évite de bloquer l'interface.

### Fichiers de démonstration

- `application/setting_circuit.py` et `application/simulation.py` forment une ancienne démonstration textuelle indépendante de l'interface. `simulation.py` démarre une boucle dès son exécution ; le lancement principal reste `application/interface.py`.
- `scrpte1.py`, à la racine, est vide. Il ne participe pas au lancement.
- `.venv/`, `__pycache__/` et les fichiers `.pyc` sont des éléments générés et ne sont pas nécessaires dans le ZIP.

---

## Étape 1 — Préparer les fichiers (Windows)

**Dans l'Explorateur de fichiers Windows :**

1. Faites un clic droit sur `Les_Nameks.zip`, puis **Extraire tout…**.
2. Dans le champ de destination, remplacez le chemin proposé par `C:\` puis validez. Le ZIP contient déjà un dossier `Les_Nameks` : vous obtenez donc `C:\Les_Nameks`.
3. Ouvrez `C:\Les_Nameks`. **Vérification :** vous devez voir directement `README.md`, `requirements.txt`, `application`, `reseau` et `deploiement_debian`. Si vous voyez à la place un second dossier `Les_Nameks`, l'extraction a créé un dossier en trop : déplacez son contenu d'un niveau, ou utilisez ce sous-dossier comme racine dans toutes les commandes.

Ne copiez pas un dossier `.venv` venant d'une autre machine : un environnement virtuel dépend du système et du chemin Python qui l'a créé.

Le groupe n'a besoin ni de Git ni de GitHub.

## Étape 2 — Installer et lancer l'application (Windows)

**Dans PowerShell** (menu Démarrer → « PowerShell »), placez-vous dans le projet et vérifiez Python :

```powershell
cd C:\Les_Nameks
py --version
```

La commande doit afficher Python 3.10 ou une version ultérieure. Si `py` est introuvable, installez Python depuis python.org en cochant **« Add python.exe to PATH »**, puis fermez et rouvrez PowerShell.

Créez un environnement propre et installez les dépendances :

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Ces commandes utilisent directement le Python de l'environnement `.venv` : il n'est pas nécessaire de l'« activer », ce qui évite les blocages de la politique d'exécution PowerShell. `requirements.txt` contient PyQt6 (l'interface) et PyMySQL (utilisé seulement côté serveur, sans effet sur Windows).

Lancez l'application :

```powershell
.\.venv\Scripts\python.exe application\interface.py
```

**Résultat attendu :** la fenêtre « Simulateur de trafic » s'ouvre. Cliquez sur **Graphe de test**, puis sur **Démarrer** : les véhicules circulent et les feux changent toutes les 5 secondes.

Tant que le serveur Debian n'est pas installé, le terminal affiche toutes les 5 secondes `Envoi des statistiques impossible : timed out` (ou `refused`). **C'est normal** : la simulation continue, seules les statistiques ne sont pas enregistrées. Fermez la fenêtre et passez à l'étape 3.

### Utiliser l'interface

| Action | Comment faire |
| --- | --- |
| Charger le réseau de démonstration | Choisir une densité (Aucun, Faible, Moyen, Fort), puis **Graphe de test**. |
| Lancer / suspendre | **Démarrer** / **Pause**. La simulation démarre toujours en pause. |
| Zoomer / se déplacer | Molette pour zoomer ; clic du milieu, ou clic droit dans le vide, maintenu pour déplacer la vue. |
| Ajouter un nœud | **Ajouter un nœud**, puis clic gauche dans une zone vide, puis saisir un nom. |
| Créer une route | Clic gauche sur un premier nœud, puis sur un second, puis saisir un poids strictement positif. |
| Déplacer un nœud | Clic gauche maintenu sur le nœud, puis glisser. |
| Renommer / supprimer un nœud | Clic droit sur le nœud. Possible uniquement s'il n'y a aucun véhicule : recréez le **Graphe de test** avec la densité **Aucun** pour éditer librement. |
| Ajouter un feu | **Ajouter un feu**, puis choisir un carrefour qui a **exactement 4 routes**. |
| Créer un véhicule | **Créer véhicule**, puis choisir départ, destination, vitesse (0,01 à 1) et type (Normal ou Prioritaire). |
| Voir le trajet d'un véhicule | Clic gauche sur le véhicule : son chemin Dijkstra s'affiche en orange. Second clic pour l'effacer. |

## Étape 3 — Installer le serveur (Debian)

Toute la partie Debian est décrite dans **[`deploiement_debian/README.md`](deploiement_debian/README.md)**. Suivez ce guide **de la section 0 à la section 8, dans l'ordre**, puis revenez ici.

Ne lancez pas le serveur avant d'avoir créé le compte MariaDB et le fichier `.env` (sections 4 et 5 du guide) : sans eux, le serveur démarre, mais chaque relevé reçu provoque une erreur MariaDB.

**Liste de contrôle à la fin du guide Debian :**

- [ ] `sudo systemctl is-active mariadb` affiche `active` ;
- [ ] `python3 deploiement_debian/tester_db.py` affiche `Connexion à MariaDB réussie` ;
- [ ] le serveur affiche `Serveur en écoute sur 0.0.0.0:5000...` et son terminal reste ouvert ;
- [ ] vous avez noté l'adresse IPv4 de la VM (section 7 du guide).

## Étape 4 — Relier Windows à Debian

Windows doit pouvoir joindre le port TCP `5000` de la VM. C'est l'étape qui pose le plus souvent problème en TP, à cause du mode réseau de la VM.

### 4.1 Vérifier le mode réseau de la VM

Dans VirtualBox, VM arrêtée ou non : **Configuration → Réseau → Carte 1 → Mode d'accès réseau**.

- **Accès par pont** (recommandé) : la VM obtient une adresse du réseau de la salle, du type `192.168.x.x` ou `10.x.x.x`, directement joignable depuis Windows. Utilisez cette adresse ci-dessous.
- **NAT** (mode par défaut de VirtualBox) : Windows **ne peut pas** joindre la VM directement (son adresse est souvent `10.0.2.15`). Deux solutions :
  - passer en **Accès par pont**, puis redémarrer le réseau de la VM (ou la VM) et relever la nouvelle adresse ;
  - ou garder NAT et ajouter une redirection : **Avancé → Redirection de ports → +**, protocole `TCP`, port hôte `5000`, port invité `5000`. Dans ce cas, l'adresse à utiliser depuis Windows est `127.0.0.1`.

Avec VMware, l'équivalent est le mode **Bridged**. Si le mode réseau est imposé par la salle, demandez à l'enseignant lequel utiliser.

### 4.2 Indiquer l'adresse à l'application

**Dans le PowerShell qui servira à lancer l'application**, depuis `C:\Les_Nameks` :

```powershell
$env:NAMEKS_SERVER_HOST = "192.168.1.50"
Test-NetConnection -ComputerName $env:NAMEKS_SERVER_HOST -Port 5000
```

Remplacez `192.168.1.50` par l'adresse de la VM (ou par `127.0.0.1` si vous utilisez la redirection NAT).

**Résultat attendu :** `TcpTestSucceeded : True`.

La variable ne vaut que pour cette fenêtre PowerShell : si vous la fermez, il faudra la redéfinir. Si la variable n'est pas définie, le client utilise l'ancienne adresse `10.128.238.191`, qui ne correspond très probablement pas à votre VM. En dernier recours, cette adresse par défaut se modifie dans la constante `ADRESSE_SERVEUR` de `reseau/client.py`.

Si le test échoue : vérifiez que le serveur tourne toujours sur Debian, que l'adresse est la bonne (`ip -4 -brief address` sur Debian) et le mode réseau. Si un pare-feu est actif sur Debian, voyez la section 7 du guide Debian. N'ouvrez pas le port MariaDB `3306` et ne désactivez pas tout le pare-feu.

## Étape 5 — Lancer la simulation complète (Windows)

Dans **le même PowerShell** que l'étape 4 :

```powershell
.\.venv\Scripts\python.exe application\interface.py
```

Cliquez sur **Graphe de test**, puis **Démarrer**. Les statistiques sont envoyées toutes les cinq secondes pendant que la simulation est active (pas pendant la pause). Le message `Envoi des statistiques impossible` ne doit plus apparaître dans le terminal Windows, et le terminal du serveur Debian affiche `Statistiques enregistrées dans MariaDB.`

## Étape 6 — Vérifier les six statistiques dans MariaDB (Debian)

Après au moins dix secondes de simulation, **dans un autre terminal Debian** :

```bash
sudo mariadb simulation_trafic -e "SELECT id, date_mesure, vehicules_actifs, vehicules_arrives, vehicules_prioritaires, temps_moyen_trajet, vehicules_attente_feu, vehicules_bouchon FROM statistiques ORDER BY id DESC LIMIT 10;"
```

**Résultat attendu :** des lignes récentes, environ une toutes les cinq secondes, avec les six colonnes de mesures. Une valeur de `temps_moyen_trajet` égale à `0` est normale tant qu'aucun véhicule n'a terminé de trajet.

Si aucune ligne n'apparaît, lisez les messages du terminal serveur, confirmez `TcpTestSucceeded : True`, puis vérifiez `.env` et les colonnes SQL. Ne copiez jamais le contenu du fichier `.env` dans un rapport.

---

## Dépendances et limitations connues

Les dépendances Python sont `PyQt6` et `PyMySQL` dans `requirements.txt`. Côté Debian, l'installateur fournit PyMySQL par le paquet système `python3-pymysql` ; la VM n'a pas besoin de PyQt6.

Les graphes ne sont pas enregistrés sur disque. Le client n'a pas de file de retransmission : les statistiques produites pendant une coupure réseau sont perdues. Le serveur écoute sur toutes les interfaces et ne fournit ni chiffrement ni authentification applicative : limitez son accès au réseau de TP de confiance.

## Problèmes fréquents

| Symptôme | Cause probable et vérification | Solution |
| --- | --- | --- |
| `py` ou `python` introuvable | Python absent ou PATH non actualisé. | Installer Python 3 depuis python.org avec l'option PATH, puis rouvrir PowerShell. |
| `ModuleNotFoundError: PyQt6` | Dépendances installées dans un autre Python. | Depuis `C:\Les_Nameks`, exécuter `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`, puis lancer avec ce même `python.exe`. |
| `.venv\Scripts\python.exe` introuvable | Le venv n'a pas été créé, ou PowerShell n'est pas dans `C:\Les_Nameks`. | `cd C:\Les_Nameks`, puis `py -m venv .venv`. |
| Fichier introuvable au lancement | PowerShell n'est pas à la racine du projet. | `cd C:\Les_Nameks` puis relancer ; vérifier que `dir` montre `application` et `reseau`. |
| `Envoi des statistiques impossible : timed out` | Serveur injoignable : serveur arrêté, mauvaise adresse, mode NAT ou pare-feu. | Normal sans serveur. Sinon, refaire l'étape 4 et `Test-NetConnection`. |
| `Connection refused` | La VM est joignable mais le serveur n'écoute pas sur le port 5000. | Sur Debian : relancer le serveur (section 8 du guide), vérifier avec `sudo ss -ltnp \| grep ':5000'`. |
| Le serveur affiche `Erreur MariaDB (FileNotFoundError…)` | Le fichier `deploiement_debian/.env` n'existe pas. | Guide Debian, section 5. |
| Le serveur affiche une autre `Erreur MariaDB` | Compte, mot de passe, table ou colonnes incorrects. | Guide Debian, sections 3 à 6 et tableau de dépannage. |
| Aucune ligne, interface fonctionne | Simulation en pause, réseau inaccessible ou erreur SQL serveur. | Laisser tourner plus de cinq secondes, lire les terminaux Windows et Debian, refaire la requête de l'étape 6. |
| Impossible de renommer ou supprimer un nœud | Des véhicules sont présents (protection volontaire). | Recréer le **Graphe de test** avec la densité **Aucun**. |
| « Le carrefour doit avoir 4 routes » | Un feu ne s'installe que sur un carrefour à exactement 4 routes. | Choisir un autre carrefour ou ajouter/supprimer des routes. |

Pour les problèmes propres à Debian (`sudo`, MariaDB, `.env`, port déjà utilisé), consultez le tableau de dépannage du [guide Debian](deploiement_debian/README.md#11-problèmes-fréquents-et-solutions).

## Préparer le ZIP à remettre

Le ZIP doit s'extraire en un dossier nommé exactement `Les_Nameks`, et ne contenir aucun secret.

1. Dans l'Explorateur, créez un dossier vide `C:\livrable`, puis à l'intérieur un dossier **`Les_Nameks`** (ce nom exact, car toutes les commandes des guides l'utilisent). Ne modifiez pas votre dossier de travail.
2. Copiez dans `C:\livrable\Les_Nameks` : `README.md`, `requirements.txt`, `.gitattributes`, les dossiers `application` et `reseau`.
3. Créez `C:\livrable\Les_Nameks\deploiement_debian` et copiez-y uniquement : `README.md`, `installer.sh`, `init_db.sql`, `migration_stats.sql`, `tester_db.py` et `.env.example`. **Ne copiez jamais `.env`** : il contient le mot de passe MariaDB.
4. Dans les dossiers copiés, supprimez les éventuels dossiers `__pycache__` (ce sont des fichiers générés). Ne copiez pas `.git`, `.venv`, ni de fichiers personnels ou temporaires.
5. Faites un clic droit sur `C:\livrable\Les_Nameks` → **Envoyer vers → Dossier compressé**. Vous obtenez `Les_Nameks.zip`.
6. Ouvrez le ZIP pour vérifier : il doit contenir un seul dossier `Les_Nameks`, avec `README.md` à l'intérieur, et aucun fichier `.env` (seulement `.env.example`).
