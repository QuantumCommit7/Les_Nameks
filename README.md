# Les_Nameks — guide de déploiement

Ce guide permet à un groupe qui découvre le projet de lancer le simulateur Windows et d'enregistrer ses statistiques sur une VM Debian. Suivez les étapes dans l'ordre. Le détail de l'installation Debian et MariaDB est dans [`deploiement_debian/README.md`](deploiement_debian/README.md).

## Ce que fait le projet

Les_Nameks est un simulateur pédagogique de circulation routière. L'application PyQt6 représente les routes par un graphe pondéré, calcule les chemins avec Dijkstra, puis anime des véhicules, des feux et des véhicules prioritaires. Elle affiche six mesures et les envoie au serveur Debian. Le serveur Python reçoit les messages par TCP et les enregistre dans MariaDB.

Les composants réseau sont simples : le client ouvre une connexion TCP au serveur sur le port `5000`, envoie un objet JSON UTF-8 terminé par un saut de ligne, puis ferme la connexion. Des threads évitent de bloquer l'interface et permettent au serveur de traiter plusieurs clients. MariaDB n'est utilisée que par le serveur sur la VM, via PyMySQL. Ce service scolaire n'est pas conçu pour être exposé sur Internet.

## Fichiers utiles

- `application/` : interface et simulation PyQt6. `interface.py` est le point de lancement.
- `reseau/client.py` et `reseau/serveur.py` : client Windows et serveur Debian.
- `deploiement_debian/` : script d'installation, fichiers SQL, `.env.example`, test de connexion et guide détaillé.
- `requirements.txt` : dépendances Python du projet.
- `cartographie_experimentale/` et `application/fond_carte.py` : code de carte conservé mais déconnecté. La carte ne se lance pas dans l'interface actuelle.

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

### Fichiers de démonstration et d'expérimentation

- `application/setting_circuit.py` et `application/simulation.py` forment une ancienne démonstration textuelle indépendante de l'interface. `simulation.py` démarre une boucle dès son exécution ; le lancement principal reste `application/interface.py`.
- `application/fond_carte.py`, `application/cache_tuiles/` et `cartographie_experimentale/` sont conservés pour une expérimentation de cartographie, mais ne sont pas raccordés à la scène active.
- `scrpte1.py` est vide. Il ne participe pas au lancement.
- `.venv/`, `__pycache__/` et les fichiers `.pyc` sont des éléments générés et ne sont pas nécessaires dans le ZIP.

## Étape 1 — Préparer les machines et les fichiers

**Sur Windows, dans l'Explorateur de fichiers :**

1. Extraire le ZIP dans un dossier simple, par exemple `C:\Les_Nameks`.
2. Ouvrir ce dossier. La racine correcte contient `README.md`, `requirements.txt`, `application`, `reseau` et `deploiement_debian`.
3. Ne pas copier un dossier `.venv` d'une autre machine : un environnement virtuel dépend du système et du chemin Python qui l'a créé.

Le groupe n'a besoin ni de Git ni de GitHub. Pour transférer le projet à Debian, privilégiez le dossier partagé fourni par la salle : copiez le dossier `Les_Nameks` depuis Windows vers le dossier personnel de Debian. Si le ZIP est copié à la place, l'étape 2 donne les commandes pour l'extraire.

`scp` est une autre possibilité uniquement si Debian a un serveur SSH actif, Windows dispose de la commande `scp`, et les deux machines peuvent communiquer. Exemple PowerShell, à adapter :

```powershell
scp -r C:\Les_Nameks etudiant@192.168.1.50:/home/etudiant/
```

Cette commande copie le dossier vers le dossier personnel Debian de `etudiant`. Pour un premier déploiement en TP, le dossier partagé ou le transfert de fichier prévu par l'enseignant est souvent plus simple.

**Fichiers nécessaires :** toute l'arborescence `application`, `reseau`, `deploiement_debian`, `requirements.txt` et les deux README. Les tuiles de carte et `cartographie_experimentale` ne sont pas nécessaires au lancement, mais peuvent rester dans l'archive de remise. N'incluez jamais un `.env` personnel, un mot de passe, `.venv`, `__pycache__` ni des fichiers temporaires. Gardez `.env.example` : il ne contient pas de secret.

Le plus simple est de transférer la même arborescence complète aux deux machines. À défaut, Windows a besoin de `application/`, `reseau/client.py` et `requirements.txt`; Debian a besoin de `reseau/serveur.py` et, au minimum, `deploiement_debian/installer.sh`, `init_db.sql`, `migration_stats.sql`, `.env.example`, `tester_db.py` et son README. Conservez les chemins et les noms de dossiers.

## Étape 2 — Installer et configurer Debian

**Sur Debian, dans un terminal :**

- Si le dossier partagé contient déjà le dossier décompressé, vérifiez-le avec :

  ```bash
  cd "$HOME/Les_Nameks"
  ls
  ```

  Vous devez voir `README.md`, `reseau` et `deploiement_debian`.

- Si vous avez transféré le ZIP `Les_Nameks.zip` dans le dossier personnel, installez l'outil d'extraction puis extrayez-le :

  ```bash
  sudo apt-get update
  sudo apt-get install -y unzip
  unzip "$HOME/Les_Nameks.zip" -d "$HOME"
  ```

  Si l'archive crée un dossier au nom différent, repérez-le avec `ls "$HOME"`, puis utilisez son vrai nom dans les commandes suivantes. Placez-vous ensuite à la racine du projet :

  ```bash
  cd "$HOME/Les_Nameks"
  ```

Le script d'installation Debian doit être lancé depuis son propre dossier :

```bash
cd "$HOME/Les_Nameks/deploiement_debian"
chmod +x installer.sh
./installer.sh
```

Le script installe MariaDB, Python PyMySQL et le support des environnements virtuels, puis démarre MariaDB. Le détail des contrôles et les solutions aux erreurs sont dans le guide Debian. Si l'installation des paquets échoue, vérifiez la connexion Internet de la VM et relancez les commandes après correction.

## Étape 3 — Créer et vérifier la base MariaDB

**Sur Debian, dans le terminal, depuis `~/Les_Nameks/deploiement_debian` :**

Pour une VM neuve seulement, créez la table puis appliquez la migration des trois mesures supplémentaires :

```bash
sudo mariadb < init_db.sql
sudo mariadb < migration_stats.sql
```

La migration ajoute `temps_moyen_trajet`, `vehicules_attente_feu` et `vehicules_bouchon`. Le détail de création du compte, du fichier `.env`, du test de connexion et de la vérification des six colonnes est dans [`deploiement_debian/README.md`](deploiement_debian/README.md).

**Installation existante :** ne relancez pas `init_db.sql` ou une migration sans avoir identifié l'état de la base et suivi la procédure de mise à jour et de sauvegarde du guide Debian. Ne supprimez jamais la base pour résoudre un problème de connexion.

Résultat attendu : MariaDB est active, le test Python réussit et la table possède les colonnes des six mesures. En cas d'erreur de base, table ou colonne, revenez aux contrôles de l'étape 3 du guide Debian avant de démarrer le serveur.

## Étape 4 — Créer l'environnement Python et démarrer le serveur TCP

**Sur Debian, dans un second terminal, depuis la racine `~/Les_Nameks` :**

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/python reseau/serveur.py
```

L'option `--system-site-packages` permet à cet environnement d'utiliser le paquet PyMySQL installé par `installer.sh`. PyQt6 n'est pas nécessaire sur Debian pour le serveur. Le message attendu est `Serveur en écoute sur 0.0.0.0:5000...`. Laissez ce terminal ouvert pendant la simulation.

Si `venv` manque, vérifiez que `installer.sh` a fini sans erreur et relancez `sudo apt-get install -y python3-venv`. Si le serveur indique que `.env` est manquant ou incomplet, reprenez sa configuration décrite dans le guide Debian. Si le port est déjà utilisé, identifiez le programme avec `sudo ss -ltnp | grep ':5000'`; ne tuez pas un processus sans savoir ce qu'il fait.

## Étape 5 — Installer l'application sous Windows

**Sur Windows, dans PowerShell, depuis `C:\Les_Nameks` :** vérifiez d'abord Python :

```powershell
py --version
```

La commande doit afficher Python 3.10 ou une version ultérieure en 64 bits. Si `py` est introuvable, installez Python depuis python.org en activant l'option d'ajout au PATH, puis ouvrez un nouveau PowerShell.

Créez un environnement propre et installez les dépendances :

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

`requirements.txt` contient seulement PyQt6 et PyMySQL. PyMySQL est utilisé par le serveur/test de base ; l'application graphique seule ne se connecte pas à MariaDB.

Si l'activation est bloquée par la politique PowerShell, l'activation n'est pas obligatoire. Utilisez directement l'interpréteur virtuel :

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

En cas de `ModuleNotFoundError: PyQt6`, installez les exigences avec le même interpréteur que celui qui lancera l'application.

## Étape 6 — Configurer la connexion réseau Windows → Debian

**Sur Debian, dans un autre terminal :** trouvez les adresses IPv4 :

```bash
ip -4 -brief address
```

Relevez l'adresse de l'interface réseau de la VM, généralement une adresse privée du type `192.168.x.x` ou `10.x.x.x`. N'utilisez pas `127.0.0.1` : cette adresse désigne la machine elle-même. Vérifiez que le serveur tourne et écoute :

```bash
sudo ss -ltnp | grep ':5000'
```

La ligne doit montrer `0.0.0.0:5000` (écoute sur les interfaces réseau). L'adresse actuelle historique dans le code est `10.128.238.191`, port `5000`; elle ne correspond probablement pas à une VM nouvellement créée.

**Sur Windows, dans le même PowerShell qui servira à lancer l'application :** définissez une seule variable avec l'adresse relevée :

```powershell
$env:NAMEKS_SERVER_HOST = "192.168.1.50"
Test-NetConnection -ComputerName $env:NAMEKS_SERVER_HOST -Port 5000
```

Remplacez l'exemple par l'adresse réelle de Debian. `TcpTestSucceeded : True` indique que Windows peut joindre le port. La variable s'applique à la fenêtre PowerShell actuelle ; après fermeture de la fenêtre, il faudra la définir de nouveau. Le client conserve l'adresse historique comme valeur par défaut si la variable n'est pas définie. Cette configuration ne change pas le protocole TCP.

Si le test échoue, vérifiez que les deux machines sont sur des réseaux qui peuvent communiquer. En mode **pont**, la VM apparaît comme une machine du réseau de TP et reçoit souvent une adresse directement joignable. En mode **NAT**, les connexions entrantes sont souvent bloquées sans redirection de port ; demandez à l'enseignant ou à l'administrateur si ce mode est imposé. Vérifiez aussi avec l'administrateur que le pare-feu autorise le port TCP `5000` depuis le réseau Windows de TP. N'ouvrez pas le port MariaDB `3306` et ne désactivez pas tout le pare-feu.

Le moyen de changer l'adresse est la variable `NAMEKS_SERVER_HOST`. En dernier recours, l'unique constante à modifier est `ADRESSE_SERVEUR` dans `reseau/client.py`; aucune autre adresse du client n'est à changer.

## Étape 7 — Lancer et utiliser la simulation

**Sur Windows, dans PowerShell depuis `C:\Les_Nameks`**, après avoir défini `NAMEKS_SERVER_HOST` si nécessaire :

```powershell
python application\interface.py
```

Si l'environnement n'est pas activé, lancez plutôt :

```powershell
.\.venv\Scripts\python.exe application\interface.py
```

Dans l'interface :

1. Choisissez une densité et cliquez sur **Graphe de test**.
2. Cliquez sur **Démarrer**. Les véhicules doivent circuler et les feux changer de phase.
3. Les statistiques s'affichent dans le panneau latéral. Les relevés réseau sont envoyés toutes les cinq secondes pendant une simulation active.

Pour construire un graphe : **Ajouter un nœud**, puis cliquer dans la zone ; cliquer sur deux nœuds pour relier les routes et entrer un poids positif ; **Ajouter un feu** puis choisir un carrefour à quatre routes ; **Créer véhicule** puis choisir départ, destination, vitesse et type. Ces commandes sont détaillées plus haut dans ce README par les libellés exacts de l'interface.

Sans serveur Debian joignable, l'interface et la simulation peuvent fonctionner, mais le terminal Windows affiche une erreur d'envoi réseau et aucune statistique n'est enregistrée à distance.

## Étape 8 — Vérifier les six statistiques dans MariaDB

Après avoir laissé tourner la simulation au moins cinq secondes, **sur Debian, dans un troisième terminal**, exécutez :

```bash
sudo mariadb simulation_trafic -e "SELECT id, date_mesure, vehicules_actifs, vehicules_arrives, vehicules_prioritaires, temps_moyen_trajet, vehicules_attente_feu, vehicules_bouchon FROM statistiques ORDER BY id DESC LIMIT 10;"
```

Résultat attendu : une ou plusieurs lignes récentes avec les six colonnes de mesures. Une valeur de `temps_moyen_trajet` égale à `0` est normale tant qu'aucun véhicule n'a terminé de trajet. Si aucune ligne n'apparaît, regardez les messages du terminal serveur, confirmez `TcpTestSucceeded : True`, puis vérifiez `.env`, les colonnes SQL et la simulation active. Ne copiez jamais le contenu du fichier `.env` dans un rapport.

## Dépendances et limitation connues

Les dépendances Python sont `PyQt6` et `PyMySQL` dans `requirements.txt`. Côté Debian, l'installateur fournit PyMySQL par le paquet système `python3-pymysql`; la VM n'a pas besoin de PyQt6.

La carte OpenStreetMap est expérimentale et reste déconnectée. Les graphes ne sont pas enregistrés sur disque. Le client n'a pas de file de retransmission en cas de coupure réseau. Le serveur écoute sur toutes les interfaces et ne fournit ni chiffrement ni authentification applicative : limitez son accès au réseau de TP de confiance.

## Problèmes fréquents

| Symptôme | Cause probable et vérification | Solution |
| --- | --- | --- |
| `py` ou `python` introuvable | Python absent ou PATH non actualisé. | Installer Python 3, activer l'ajout au PATH et rouvrir PowerShell. |
| `ModuleNotFoundError: PyQt6` | Dépendances installées dans un autre Python. | Depuis la racine Windows, exécuter `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`. |
| Venv ne se crée/active pas | Python incomplet ou politique PowerShell. | Debian : `sudo apt-get install python3-venv`. Windows : ne pas activer, utiliser `.venv\Scripts\python.exe`. |
| `.env` absent/incomplet | Fichier non créé dans le dossier attendu. | Suivre la section 5 du guide Debian ; le chemin doit être `deploiement_debian/.env`. |
| PyMySQL manquant | L'installateur Debian n'a pas fini ou l'environnement ne voit pas les paquets système. | Relancer `sudo apt-get install python3-pymysql python3-venv`, recréer le venv avec `--system-site-packages`. |
| Connexion TCP refusée ou timeout | Serveur arrêté, mauvaise IP, réseau NAT ou pare-feu. | Debian : `sudo ss -ltnp | grep ':5000'`. Windows : `Test-NetConnection -ComputerName $env:NAMEKS_SERVER_HOST -Port 5000`. Voir l'étape 6. |
| Base/table/colonnes inconnues | SQL non appliqué ou migration absente. | Vérifier `SHOW TABLES` et `SHOW COLUMNS`; pour une base neuve suivre l'étape 3 du guide Debian. |
| Aucune ligne, interface fonctionne | Simulation inactive, réseau inaccessible ou erreur SQL serveur. | Laisser tourner plus de cinq secondes, lire les terminaux Windows/Debian et consulter la requête de l'étape 8. |
| `Address already in use` | Un autre programme utilise le port 5000. | `sudo ss -ltnp | grep ':5000'`; arrêter uniquement le service identifié ou convenir d'un port commun avant tout changement. |
| Import local introuvable | Python lancé depuis un mauvais dossier. | Se placer dans la racine `Les_Nameks` puis lancer `python application\interface.py` ou `python3 reseau/serveur.py`. |

Pour les identifiants MariaDB, le compte et les erreurs SQL, consulter la section dépannage détaillée de [`deploiement_debian/README.md`](deploiement_debian/README.md).

## Préparer le ZIP à remettre

Pour éviter de mettre un secret dans l'archive, créez dans l'Explorateur un dossier de préparation séparé, par exemple `C:\Les_Nameks-livrable`, sans modifier ni supprimer le dossier de travail. Copiez-y `README.md`, `requirements.txt`, `application`, `reseau`, et créez `deploiement_debian` en y copiant `README.md`, `installer.sh`, `init_db.sql`, `migration_stats.sql`, `tester_db.py` et `.env.example` (pas un éventuel `.env`). La copie peut aussi contenir `cartographie_experimentale` et `.gitattributes`; elles ne sont pas requises pour le lancement. Compressez ensuite le dossier de préparation et inspectez son contenu. N'y copiez pas `.git`, `.venv`, `__pycache__`, fichiers temporaires ni données personnelles. Ne supprimez pas automatiquement des fichiers du dépôt pour préparer l'archive.
