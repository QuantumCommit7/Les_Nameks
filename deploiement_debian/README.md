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

## 9. Mettre à jour les statistiques sur une installation existante

Cette procédure ajoute les nouvelles mesures sans supprimer de table ni de ligne. Le serveur mis à jour doit être déployé **après la migration SQL et avant d'utiliser le nouveau simulateur Windows**.

### 9.1 Arrêter le serveur TCP

Dans le terminal Debian où `reseau/serveur.py` est lancé, appuie sur `Ctrl+C` et attends le message d'arrêt. Si le serveur est géré par un service, arrête ce service à la place.

### 9.2 Récupérer les modifications

Sur la VM déjà clonée, exécute :

```bash
cd "$HOME/Les_Nameks"
git status --short
git pull --ff-only
```

Si `git status --short` signale des modifications locales, conserve-les ou demande conseil avant de continuer. Le fichier local `deploiement_debian/.env` est ignoré par Git et contient les paramètres MariaDB propres à la VM.

### 9.3 Vérifier et sauvegarder la base

Vérifie que la base et la table attendues existent :

```bash
sudo mariadb -e "SHOW TABLES IN simulation_trafic;"
```

Crée une sauvegarde avant la modification du schéma :

```bash
mkdir -p "$HOME/sauvegardes"
sudo mariadb-dump simulation_trafic > "$HOME/sauvegardes/simulation_trafic_avant_migration_$(date +%Y%m%d_%H%M%S).sql"
ls -lh "$HOME"/sauvegardes/simulation_trafic_avant_migration_*.sql
```

Vérifie que le fichier de sauvegarde est présent et non vide avant de continuer.

### 9.4 Lancer la migration

La migration vérifie chaque colonne dans `information_schema` et n'ajoute que celles qui manquent. Les anciennes lignes reçoivent `0` comme valeur par défaut pour les nouvelles mesures.

```bash
cd "$HOME/Les_Nameks/deploiement_debian"
sudo mariadb < migration_stats.sql
```

La commande doit se terminer sans erreur. Elle peut être relancée : les colonnes déjà présentes ne sont pas ajoutées une deuxième fois.

### 9.5 Vérifier les colonnes

```bash
sudo mariadb simulation_trafic -e "SHOW COLUMNS FROM statistiques;"
```

La sortie doit contenir `temps_moyen_trajet` de type `double`, puis `vehicules_attente_feu` et `vehicules_bouchon` de type `int`. Les trois colonnes doivent être `NOT NULL` avec `DEFAULT 0`.

### 9.6 Redémarrer le serveur mis à jour

Après la migration seulement, lance le serveur depuis la racine du projet :

```bash
cd "$HOME/Les_Nameks"
python3 reseau/serveur.py
```

Laisse ce terminal ouvert. Il utilise les identifiants du fichier local `deploiement_debian/.env`. Seul le port TCP 5000 reçoit les messages du simulateur ; MariaDB reste local à Debian.

### 9.7 Lancer le simulateur Windows et vérifier les six mesures

Après le redémarrage du serveur, récupère aussi la version à jour du projet sur Windows (`git pull` dans son dossier cloné), puis lance le simulateur. Pendant la simulation active, le client envoie les six mesures toutes les cinq secondes.

Sur Debian, affiche les derniers enregistrements :

```bash
sudo mariadb simulation_trafic -e "SELECT id, date_mesure, vehicules_actifs, vehicules_arrives, vehicules_prioritaires, temps_moyen_trajet, vehicules_attente_feu, vehicules_bouchon FROM statistiques ORDER BY id DESC LIMIT 10;"
```

De nouvelles lignes doivent apparaître au rythme d'environ une ligne toutes les cinq secondes lorsque la simulation est active. Les trois colonnes ajoutées doivent contenir les valeurs envoyées par l'interface. `temps_moyen_trajet` peut valoir `0` tant qu'aucun trajet n'est terminé.

## Erreurs fréquentes

- **`Permission denied` avec `sudo`** : le compte Debian doit être autorisé à utiliser `sudo`; demande de l'aide à l'administrateur de la VM.
- **`Unit mariadb.service could not be found`** : relance `./installer.sh` et vérifie que l'installation a terminé sans erreur.
- **Service inactif** : exécute `sudo systemctl status mariadb --no-pager` pour lire l'état du service.
- **`ModuleNotFoundError: No module named 'pymysql'`** : exécute `sudo apt-get install -y python3-pymysql`.
- **Accès refusé (erreur 1045)** : vérifie `DB_USER`, `DB_PASSWORD` dans `.env`, puis les droits affichés par `SHOW GRANTS`. Ne partage pas le mot de passe pour demander de l'aide.
- **Connexion refusée à `127.0.0.1:3306` (erreur 2003)** : vérifie que MariaDB est actif et écoute sur `127.0.0.1:3306` avec les commandes de la section 7.
- **Base ou table inconnue** : vérifie d'abord le nom de la base et la table avec `sudo mariadb -e "SHOW TABLES IN simulation_trafic;"`. N'exécute pas une réinitialisation pour corriger une migration échouée.
- **`tester_db.py` dit que `.env` manque** : vérifie que tu as fait `cp .env.example .env` depuis `deploiement_debian/` puis rempli `DB_PASSWORD`.
- **Aucune nouvelle ligne n'apparaît** : vérifie que le serveur mis à jour tourne, qu'il affiche `Statistiques enregistrées dans MariaDB.`, et que la simulation Windows est active. Regarde ensuite les erreurs du terminal serveur sans afficher le contenu de `.env`.
- **Erreur SQL indiquant une colonne inconnue** : vérifie la sortie de `SHOW COLUMNS FROM statistiques;` et exécute `migration_stats.sql` avant de relancer le serveur.
- **Erreur de connexion TCP** : vérifie que `python3 reseau/serveur.py` tourne depuis la racine du projet et que le réseau autorise le port 5000.

## Compatibilité de la migration

Le fichier crée une procédure stockée pour vérifier `information_schema`, l'appelle puis la supprime. Cette méthode évite de dépendre de `ADD COLUMN IF NOT EXISTS`, dont la disponibilité dépend de la version de MariaDB. Le client en ligne de commande `mariadb` comprend les délimiteurs utilisés. Le compte qui exécute la migration doit pouvoir créer une procédure et modifier `simulation_trafic.statistiques` ; `sudo mariadb` est utilisé dans les commandes ci-dessus. La migration n'a pas été exécutée sur la VM dans le cadre de cette modification.
