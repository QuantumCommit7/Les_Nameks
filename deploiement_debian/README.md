# Déployer le serveur Les_Nameks sur Debian

Ce guide installe le serveur TCP et MariaDB sur une VM Debian neuve à partir des fichiers du ZIP. Il ne nécessite ni Git ni accès au dépôt en ligne. Exécutez les étapes dans l'ordre. Les commandes sont à lancer dans un terminal Debian, sauf mention contraire.

Le client Windows envoie des mesures au serveur Python sur le port TCP `5000`. Le serveur écrit les mesures dans MariaDB, qui reste locale à Debian sur `127.0.0.1:3306`. N'ouvrez pas le port `3306` au réseau.

## 1. Copier et repérer le projet

Avec le dossier partagé de la salle, copiez le dossier `Les_Nameks` depuis Windows vers le dossier personnel de l'utilisateur Debian. Si vous avez reçu un ZIP directement sur Debian, installez l'extracteur et décompressez-le :

```bash
sudo apt-get update
sudo apt-get install -y unzip
unzip "$HOME/Les_Nameks.zip" -d "$HOME"
```

Adaptez le nom du ZIP et, si nécessaire, celui du dossier extrait. La racine du projet est le dossier qui contient `README.md`, `reseau/` et `deploiement_debian/`. Vérifiez-la :

```bash
cd "$HOME/Les_Nameks"
ls
```

Si le ZIP est sur Windows, la méthode conseillée en salle est le dossier partagé ou le transfert de fichier de l'hyperviseur. `scp` fonctionne uniquement si Debian exécute un serveur SSH, Windows possède le client OpenSSH, et les machines peuvent se joindre. N'utilisez pas Git comme prérequis.

## 2. Installer les paquets système

Allez dans le dossier de déploiement. Le script vérifie la famille de la distribution, installe MariaDB et les bibliothèques Python Debian nécessaires, puis active le service :

```bash
cd "$HOME/Les_Nameks/deploiement_debian"
chmod +x installer.sh
./installer.sh
```

`chmod +x` autorise l'exécution du script après extraction du ZIP. Le script peut demander le mot de passe `sudo`. Il ne crée pas et ne réinitialise pas la base de données. Attendez le message `MariaDB est actif.`

Vérifiez ensuite le service :

```bash
sudo systemctl is-active mariadb
```

Résultat attendu : `active`. S'il est inactif, consultez `sudo systemctl status mariadb --no-pager` et corrigez l'erreur avant de continuer. Si l'installation apt échoue, vérifiez l'accès Internet et réessayez.

Le script installe `mariadb-server`, `python3-pymysql` et `python3-venv`. PyMySQL est la seule dépendance Python du serveur et du test DB ; PyQt6 n'est utilisé que par l'application Windows.

## 3. Initialiser MariaDB sur une VM neuve

### Attention : installation neuve ou existante

Les commandes ci-dessous sont pour une VM neuve, sans base `simulation_trafic` à préserver. `init_db.sql` utilise `CREATE DATABASE/TABLE IF NOT EXISTS` et ne vide pas les tables, mais ne permet pas de mettre à niveau une table déjà existante. `migration_stats.sql` ajoute seulement les trois colonnes qui manquent. Pour une base existante, ne suivez pas aveuglément l'initialisation neuve : utilisez la procédure de mise à jour de la section 9, vérifiez le schéma et faites d'abord une sauvegarde.

### Créer la base et les six colonnes de mesures

Depuis `deploiement_debian/`, exécutez les deux scripts dans cet ordre :

```bash
sudo mariadb < init_db.sql
sudo mariadb < migration_stats.sql
```

Le premier crée la base `simulation_trafic` et la table `statistiques`, avec les colonnes `id`, `date_mesure`, `vehicules_actifs`, `vehicules_arrives` et `vehicules_prioritaires`. Le second ajoute `temps_moyen_trajet`, `vehicules_attente_feu` et `vehicules_bouchon`. Les anciennes lignes reçoivent `0` pour les nouvelles colonnes. La migration est réexécutable : elle n'ajoute pas une colonne déjà présente.

Vérifiez les tables et les colonnes :

```bash
sudo mariadb -e "SHOW TABLES IN simulation_trafic;"
sudo mariadb simulation_trafic -e "SHOW COLUMNS FROM statistiques;"
```

Vous devez voir la table `statistiques` et les colonnes de six mesures :

```text
vehicules_actifs
vehicules_arrives
vehicules_prioritaires
temps_moyen_trajet
vehicules_attente_feu
vehicules_bouchon
```

Les trois premières mesures et les mesures entières sont des entiers ; `temps_moyen_trajet` est de type `double`. Si une colonne manque, vérifiez d'abord la sortie de chaque commande SQL et l'état de la base. Ne supprimez pas la base.

## 4. Créer le compte MariaDB du serveur

Le serveur utilise un compte séparé. Sur la VM neuve, ouvrez l'invite MariaDB avec l'historique désactivé :

```bash
sudo env MYSQL_HISTFILE=/dev/null mariadb
```

À l'invite MariaDB, créez le compte et donnez-lui seulement les droits requis. Remplacez le texte de mot de passe par une valeur unique choisie pour cette VM. Choisissez un mot de passe long et notez-le dans le gestionnaire de secrets prévu par l'équipe, pas dans le ZIP ou un message partagé.

```sql
CREATE USER 'trafic'@'127.0.0.1' IDENTIFIED BY 'EXEMPLE_FICTIF_A_REMPLACER';
GRANT SELECT, INSERT ON simulation_trafic.* TO 'trafic'@'127.0.0.1';
SHOW GRANTS FOR 'trafic'@'127.0.0.1';
EXIT;
```

`EXEMPLE_FICTIF_A_REMPLACER` n'est pas un mot de passe utilisable. Ne gardez pas les apostrophes de l'exemple si votre mot de passe en contient, ou choisissez une chaîne aléatoire de lettres, chiffres et signes qui ne contient pas d'apostrophe afin de simplifier la saisie SQL.

`DB_HOST` dans l'exemple vaut `127.0.0.1`, donc le compte est créé pour cette adresse de boucle locale. Cela permet au serveur Python sur Debian de parler à MariaDB sans rendre la base accessible depuis Windows.

Sur une installation existante, le compte peut déjà exister. N'exécutez pas `CREATE USER` tel quel en supposant l'état du serveur : vérifiez les comptes/droits avec l'administrateur, et utilisez `ALTER USER` si un changement de mot de passe est requis. Ne partagez jamais le mot de passe pour obtenir de l'aide.

## 5. Créer le fichier de configuration `.env`

Le programme lit les paramètres MariaDB dans `Les_Nameks/deploiement_debian/.env`. Le ZIP ne doit contenir que `.env.example`, qui n'a pas de mot de passe. Depuis `deploiement_debian/`, créez votre fichier local et protégez ses permissions :

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

Renseignez les valeurs suivantes. Exemple fictif de configuration — le mot de passe doit être remplacé localement :

```dotenv
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=simulation_trafic
DB_USER=trafic
DB_PASSWORD=EXEMPLE_FICTIF_A_REMPLACER
```

Ces cinq noms correspondent exactement à ceux lus par `reseau/serveur.py` et `tester_db.py`. `DB_PASSWORD` doit être identique au mot de passe saisi pour l'utilisateur MariaDB. N'ajoutez pas d'espaces autour de `=`. Dans nano, enregistrez avec `Ctrl+O`, Entrée, puis quittez avec `Ctrl+X`.

Le `.env` est ignoré par Git et ne doit jamais être inclus dans le ZIP final. Ne l'affichez pas avec `cat`, ne faites pas de capture d'écran de son contenu et ne le copiez pas dans un ticket. Vérifiez seulement qu'il est ignoré, sans afficher son contenu :

```bash
git check-ignore .env
```

La commande peut répondre que `.env` n'est pas suivi par Git si le projet vient d'un ZIP, car Git n'est pas nécessaire. Cela n'empêche pas le fonctionnement ; le point essentiel est de ne pas partager ce fichier.

## 6. Créer l'environnement Python Debian et tester MariaDB

Depuis la racine du projet, créez un environnement isolé qui voit PyMySQL installé par apt :

```bash
cd "$HOME/Les_Nameks"
python3 -m venv --system-site-packages .venv
```

L'option `--system-site-packages` rend visible le paquet `python3-pymysql` fourni par Debian. Elle évite une installation globale avec `pip`, que les versions récentes de Debian peuvent bloquer. Le serveur n'importe pas PyQt6.

Testez les identifiants et l'accès en lecture à la table :

```bash
.venv/bin/python deploiement_debian/tester_db.py
```

Résultat attendu : `Connexion à MariaDB réussie. Lignes dans statistiques : 0.` (le nombre peut être supérieur à zéro si des mesures existent déjà). Le test lit `.env`, exécute `SELECT COUNT(*)` et ferme la connexion. Il ne modifie pas la base.

Si le test dit que PyMySQL manque, vérifiez `sudo apt-get install python3-pymysql` et recréez le venv avec l'option ci-dessus. Pour un accès refusé, vérifiez les cinq paramètres et les droits sans révéler le mot de passe. Pour une erreur de connexion locale, vérifiez `sudo systemctl is-active mariadb`.

## 7. Trouver l'adresse Debian et configurer le réseau

Le serveur écoute sur `0.0.0.0:5000`, donc sur les interfaces réseau de la VM. Pour trouver l'adresse IPv4 Debian :

```bash
ip -4 -brief address
```

Utilisez l'adresse de l'interface reliée au réseau de TP, pas `127.0.0.1`. Vérifiez que le serveur est à l'écoute après l'avoir démarré (étape suivante) :

```bash
sudo ss -ltnp | grep ':5000'
```

Windows et Debian doivent pouvoir communiquer. En mode réseau **pont**, Debian reçoit normalement une adresse sur le même réseau local que Windows. En mode **NAT**, les connexions initiées depuis Windows vers la VM sont souvent bloquées sauf configuration de redirection de port par l'administrateur/hyperviseur. Pour un groupe débutant, demandez à l'enseignant quel mode réseau et quelle interface utiliser. Ne désactivez pas le pare-feu. Si UFW est installé et actif, l'administrateur peut autoriser uniquement la machine/réseau Windows de TP vers le port TCP 5000, par exemple :

```bash
sudo ufw status verbose
sudo ufw allow from 192.168.1.25 to any port 5000 proto tcp
```

Remplacez `192.168.1.25` par l'adresse Windows appropriée et n'appliquez la règle que si UFW est déjà utilisé conformément aux consignes de la salle. Pour un autre pare-feu, demandez à l'administrateur la règle équivalente. N'ouvrez jamais `3306` au réseau.

Sur Windows PowerShell, définissez dans la même fenêtre que celle qui lancera l'application l'adresse Debian relevée :

```powershell
$env:NAMEKS_SERVER_HOST = "192.168.1.50"
Test-NetConnection -ComputerName $env:NAMEKS_SERVER_HOST -Port 5000
```

Remplacez l'exemple par l'adresse de la VM. Résultat attendu : `TcpTestSucceeded : True`. Une variable `$env:` ne vaut que dans la fenêtre PowerShell courante. Le code conserve l'ancienne adresse `10.128.238.191` comme valeur par défaut si la variable n'est pas définie. Les instructions de dépannage réseau sont dans le README principal.

## 8. Démarrer le serveur TCP

Le serveur doit être lancé depuis la racine du projet pour que ses imports fonctionnent correctement. Depuis un terminal Debian :

```bash
cd "$HOME/Les_Nameks"
.venv/bin/python reseau/serveur.py
```

Résultat attendu : `Serveur en écoute sur 0.0.0.0:5000...`. Laissez ce terminal ouvert. Dans un second terminal, confirmez l'écoute :

```bash
sudo ss -ltnp | grep ':5000'
```

À l'arrêt, utilisez `Ctrl+C`. Les erreurs MariaDB sont affichées sans révéler la valeur du mot de passe. Le serveur n'a ni chiffrement ni authentification de client : ne l'exposez qu'au réseau de TP de confiance.

## 9. Vérification de bout en bout

### Côté Debian avant le test

1. `sudo systemctl is-active mariadb` doit afficher `active`.
2. `sudo mariadb -e "SHOW TABLES IN simulation_trafic;"` doit montrer `statistiques`.
3. `sudo mariadb simulation_trafic -e "SHOW COLUMNS FROM statistiques;"` doit montrer les six mesures listées à l'étape 3.
4. `.venv/bin/python deploiement_debian/tester_db.py` doit confirmer la connexion.
5. Le serveur doit afficher qu'il écoute sur `0.0.0.0:5000`.

### Côté Windows

1. Depuis `C:\Les_Nameks`, installez les dépendances et démarrez `python application\interface.py` (voir le README principal).
2. Définissez `NAMEKS_SERVER_HOST` avec l'IPv4 Debian et vérifiez `Test-NetConnection ... -Port 5000` donne `TcpTestSucceeded : True`.
3. Cliquez sur **Graphe de test**, puis **Démarrer**. Les véhicules circulent et les compteurs s'affichent.

### Vérifier les lignes enregistrées

Laissez tourner la simulation au moins cinq secondes. Depuis Debian, dans un autre terminal :

```bash
sudo mariadb simulation_trafic -e "SELECT id, date_mesure, vehicules_actifs, vehicules_arrives, vehicules_prioritaires, temps_moyen_trajet, vehicules_attente_feu, vehicules_bouchon FROM statistiques ORDER BY id DESC LIMIT 10;"
```

De nouvelles lignes doivent apparaître pendant que la simulation fonctionne, environ une toutes les cinq secondes. Les six colonnes de mesures doivent être présentes. `temps_moyen_trajet` peut être `0` tant qu'aucun trajet n'est terminé. Si l'interface fonctionne sans serveur Debian joignable, elle continue la simulation mais le terminal Windows affiche une erreur d'envoi et aucune nouvelle ligne n'est insérée.

## 10. Mise à jour d'une installation existante

Cette procédure ne s'applique pas à une VM vierge. Avant toute modification, arrêtez le serveur TCP, confirmez le nom de la base et faites une sauvegarde non vide. Ne lancez pas `init_db.sql` pour tenter de réparer une installation existante et ne supprimez aucune base.

Depuis la racine du projet, vérifiez d'abord les tables et colonnes actuelles :

```bash
sudo mariadb -e "SHOW TABLES IN simulation_trafic;"
sudo mariadb simulation_trafic -e "SHOW COLUMNS FROM statistiques;"
```

Sauvegardez avant la migration :

```bash
mkdir -p "$HOME/sauvegardes"
sudo mariadb-dump simulation_trafic > "$HOME/sauvegardes/simulation_trafic_avant_migration.sql"
ls -lh "$HOME/sauvegardes/simulation_trafic_avant_migration.sql"
```

Vérifiez que le fichier existe et n'est pas vide. Puis, si la table `statistiques` existe et que l'objectif est seulement d'ajouter les trois nouvelles mesures, lancez la migration idempotente :

```bash
cd "$HOME/Les_Nameks/deploiement_debian"
sudo mariadb < migration_stats.sql
```

Revérifiez les colonnes avec `SHOW COLUMNS`. La migration n'efface pas les lignes et ajoute `DEFAULT 0` aux colonnes nouvelles. En cas d'erreur ou si la base diffère de ce schéma, arrêtez-vous et demandez conseil à l'administrateur plutôt que de réinitialiser la base.

## 11. Problèmes fréquents et solutions

| Symptôme | Cause probable | Vérification et solution |
| --- | --- | --- |
| `python3: command not found` | Python absent ou PATH inhabituel. | `python3 --version`; installer avec `sudo apt-get install python3 python3-venv`. |
| `No module named venv` | Paquet venv absent. | `sudo apt-get install python3-venv`, puis refaire la création du venv. |
| `No module named pymysql` | Paquet système absent ou venv créé sans accès aux paquets système. | `sudo apt-get install python3-pymysql`; créer `.venv` avec `--system-site-packages`. |
| `.env` manquant/incomplet | Fichier absent du dossier exact ou valeur requise vide. | Créer `deploiement_debian/.env` depuis `.env.example`; ne pas afficher son contenu. |
| Accès MariaDB refusé (1045) | Nom d'utilisateur, mot de passe ou hôte de compte incorrect. | Vérifier les paramètres localement et `SHOW GRANTS`; rétablir les droits sans partager le secret. |
| MariaDB arrêtée / connexion locale refusée (2003) | Service arrêté ou mauvais `DB_HOST`/port. | `sudo systemctl status mariadb --no-pager`; `.env` doit utiliser `127.0.0.1` et `3306`. |
| Base ou table inconnue | Scripts SQL non appliqués ou mauvais nom. | `sudo mariadb -e "SHOW TABLES IN simulation_trafic;"`; sur une VM neuve suivre les deux commandes de l'étape 3. |
| Colonne inconnue dans INSERT | Migration absente. | `SHOW COLUMNS FROM statistiques`; ne migrer une base existante qu'après sauvegarde et selon section 10. |
| Port TCP 5000 déjà utilisé | Un autre processus écoute déjà. | `sudo ss -ltnp | grep ':5000'`; identifier le processus avant toute action, ne pas l'arrêter à l'aveugle. |
| Windows indique `Connection refused` | Serveur arrêté, IP incorrecte ou port bloqué. | Debian : vérifier `ss`; Windows : `Test-NetConnection -ComputerName $env:NAMEKS_SERVER_HOST -Port 5000`. |
| Windows indique timeout / inaccessible | Mauvais mode NAT/pont, IP d'une mauvaise interface ou pare-feu. | Comparer l'IP avec `ip -4 -brief address`, demander le mode réseau de TP et une règle limitée au port 5000. |
| Serveur lancé depuis le mauvais dossier | Les imports relatifs au dépôt ne trouvent pas le projet. | `cd "$HOME/Les_Nameks"` puis `.venv/bin/python reseau/serveur.py`. |
| Simulation active, aucune ligne n'arrive | Port injoignable, mauvais `.env`, colonnes manquantes ou serveur arrêté. | Lire les deux terminaux, vérifier le test DB, `Test-NetConnection`, puis exécuter la requête SQL de l'étape 9. |

Ne désactivez pas le pare-feu et n'exposez pas MariaDB pour contourner une erreur réseau. Le port `3306` doit rester local à Debian ; seul le port TCP `5000` doit être autorisé depuis le réseau de TP concerné.
