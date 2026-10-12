# Déployer MariaDB sur Debian

Ce dossier prépare MariaDB sur la VM Debian pour le projet Les_Nameks. MariaDB reste accessible **uniquement sur la VM** ; le simulateur Windows communique avec le serveur Python par TCP sur le port 5000. Ce guide n'ouvre pas le port MariaDB 3306 sur le réseau.

> Les commandes sont à exécuter sur la VM Debian, sauf indication contraire. Remplace les valeurs explicitement signalées avant d'exécuter les commandes.

## 1. Récupérer le projet sur Debian

Choisis une méthode.

### Avec Git

Installe Git si nécessaire, puis remplace `URL_DU_DEPOT` par l'adresse HTTPS ou SSH de votre dépôt :

```bash
sudo apt-get update
sudo apt-get install -y git
cd "$HOME"
git clone URL_DU_DEPOT Les_Nameks
```

### En copiant le dossier

Copie le dossier complet du projet sur la VM avec une clé USB ou un dossier partagé. Si le dossier copié est par exemple dans `~/Transferts/Les_Nameks`, exécute :

```bash
cp -a "$HOME/Transferts/Les_Nameks" "$HOME/Les_Nameks"
```

Remplace le chemin source par l'emplacement réel du dossier copié. Si `~/Les_Nameks` existe déjà, copie les nouveaux fichiers dans ce dossier au lieu de l'écraser.

## 2. Ouvrir un terminal dans ce dossier

Après l'une ou l'autre méthode :

```bash
cd "$HOME/Les_Nameks/deploiement_debian"
pwd
```

La dernière commande doit afficher un chemin qui se termine par `/Les_Nameks/deploiement_debian`.

## 3. Installer MariaDB et PyMySQL

Le script installe les paquets Debian `mariadb-server` et `python3-pymysql`, puis active et démarre le service MariaDB. Il ne supprime pas de base existante.

```bash
chmod +x installer.sh
./installer.sh
```

Le script peut demander le mot de passe de `sudo`. Il n'exécute aucune commande d'installation sur Windows.

## 4. Créer la base et la table

Toujours depuis `deploiement_debian/`, exécute le fichier SQL avec le compte administrateur local MariaDB :

```bash
sudo mariadb < init_db.sql
```

Le script crée `simulation_trafic` et `statistiques` si nécessaire. Une nouvelle exécution ne supprime pas et ne vide pas les données existantes.

## 5. Créer le compte applicatif

Ouvre le client MariaDB sans enregistrer les commandes sensibles dans son historique :

```bash
sudo env MYSQL_HISTFILE=/dev/null mariadb
```

Dans l'invite `MariaDB [(none)]>`, saisis les commandes suivantes en remplaçant le texte entre apostrophes par un mot de passe solide choisi localement. Ne mets pas le mot de passe dans une commande PowerShell, dans un script du dépôt ou dans un message partagé.

```sql
CREATE USER IF NOT EXISTS 'trafic'@'localhost' IDENTIFIED BY 'REMPLACER_PAR_UN_MOT_DE_PASSE_SOLIDE';
GRANT SELECT, INSERT ON simulation_trafic.* TO 'trafic'@'localhost';
SHOW GRANTS FOR 'trafic'@'localhost';
EXIT;
```

La sortie de `SHOW GRANTS` doit accorder uniquement `SELECT` et `INSERT` sur `simulation_trafic.*`. Si le compte existe déjà et que tu dois changer son mot de passe, utilise dans le client MariaDB :

```sql
ALTER USER 'trafic'@'localhost' IDENTIFIED BY 'REMPLACER_PAR_LE_NOUVEAU_MOT_DE_PASSE';
```

Puis saisis de nouveau le `GRANT` et `SHOW GRANTS` ci-dessus. L'option `MYSQL_HISTFILE=/dev/null` évite de conserver ces commandes dans l'historique du client MariaDB pour cette session.

## 6. Configurer les paramètres locaux

Crée le fichier `.env` privé à partir de l'exemple et édite-le :

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

Renseigne `DB_PASSWORD` avec le mot de passe que tu viens de choisir, sans ajouter d'apostrophes ou de guillemets autour de la valeur. Enregistre dans nano avec `Ctrl+O`, Entrée, puis quitte avec `Ctrl+X`.

Le fichier `.env` est ignoré par Git. Ne l'affiche pas avec `cat`, ne le joins pas à un ticket et ne copie pas son contenu dans les journaux. Le script de test ne journalise pas les paramètres ni le mot de passe.

## 7. Vérifier MariaDB

Vérifie que le service est actif et que la table existe :

```bash
sudo systemctl is-active mariadb
sudo mariadb -e "SHOW TABLES IN simulation_trafic;"
```

La première commande doit répondre `active`; la seconde doit afficher `statistiques`.

Vérifie aussi que MariaDB n'écoute que localement :

```bash
sudo ss -ltnp | grep ':3306'
```

L'adresse d'écoute attendue est `127.0.0.1:3306` (éventuellement aussi `::1:3306`). Si la sortie indique `0.0.0.0:3306` ou `*:3306`, ne configure pas de règle réseau pour le port 3306 et demande à l'administrateur de la VM de vérifier la configuration avant de continuer.

Vérifie que Git ignore bien les paramètres locaux, sans afficher leur contenu :

```bash
git check-ignore .env
```

La commande doit afficher `.env`.

## 8. Tester la connexion Python à la base

Depuis `deploiement_debian/` :

```bash
python3 tester_db.py
```

Le script doit afficher un succès et le nombre de lignes de `statistiques` (probablement `0` avant tout enregistrement). Il lit `.env`, exécute `SELECT COUNT(*)`, puis ferme la connexion.

## 9. Lancer ensuite le serveur TCP

Le serveur Python est dans le dossier voisin `reseau/`, pas dans `deploiement_debian/`. Dans un nouveau terminal Debian, lance-le depuis la racine du projet :

```bash
cd "$HOME/Les_Nameks"
python3 reseau/serveur.py
```

Ce serveur TCP reçoit actuellement un message texte et l'affiche. **Il n'utilise pas encore MariaDB et n'enregistre pas automatiquement de statistiques.** L'intégration de l'enregistrement sera une étape ultérieure. Seul le port TCP 5000 est destiné aux messages venant du simulateur Windows ; le port 3306 reste local à Debian.

## 10. Afficher les statistiques

Après de futurs enregistrements dans la table, affiche les lignes avec :

```bash
sudo mariadb simulation_trafic -e "SELECT id, date_mesure, vehicules_actifs, vehicules_arrives, vehicules_prioritaires FROM statistiques ORDER BY id DESC;"
```

Pour l'instant, la table peut rester vide : le serveur TCP actuel ne fait aucun `INSERT`.

## Erreurs fréquentes

- **`Permission denied` avec `sudo`** : le compte Debian doit être autorisé à utiliser `sudo`; demande de l'aide à l'administrateur de la VM.
- **`Unit mariadb.service could not be found`** : relance `./installer.sh` et vérifie que l'installation a terminé sans erreur.
- **Service inactif** : exécute `sudo systemctl status mariadb --no-pager` pour lire l'état du service.
- **`ModuleNotFoundError: No module named 'pymysql'`** : exécute `sudo apt-get install -y python3-pymysql`.
- **Accès refusé (erreur 1045)** : vérifie `DB_USER`, `DB_PASSWORD` dans `.env`, puis les droits affichés par `SHOW GRANTS`. Ne partage pas le mot de passe pour demander de l'aide.
- **Connexion refusée à `127.0.0.1:3306` (erreur 2003)** : vérifie que MariaDB est actif et écoute sur `127.0.0.1:3306` avec les commandes de la section 7.
- **Base ou table inconnue** : depuis ce dossier, relance `sudo mariadb < init_db.sql`.
- **`tester_db.py` dit que `.env` manque** : vérifie que tu as fait `cp .env.example .env` depuis `deploiement_debian/` puis rempli `DB_PASSWORD`.
- **Un message TCP n'apparaît pas sur Debian** : vérifie que `python3 reseau/serveur.py` tourne depuis la racine du projet et que le réseau autorise le port 5000. Cela est indépendant de MariaDB.

## Étape future : enregistrer les statistiques reçues en JSON

Le client Windows et le serveur TCP devront convenir d'un format JSON avec les champs `vehicules_actifs`, `vehicules_arrives` et `vehicules_prioritaires`. Le serveur devra décoder et valider chaque message reçu, lire sa configuration locale, puis exécuter un `INSERT` paramétré dans `statistiques` avec PyMySQL. Il faudra aussi décider quand mesurer les compteurs et comment répondre au client en cas de message invalide ou d'échec MariaDB. Le serveur actuel ne réalise aucune de ces opérations.
