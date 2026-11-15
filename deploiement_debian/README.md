# Déployer le serveur Les_Nameks sur Debian

Ce guide installe le serveur TCP et MariaDB sur une VM Debian neuve à partir des fichiers du projet. Il ne nécessite ni Git ni accès au dépôt en ligne. Si l'application tourne elle aussi sur une VM Debian (deux VM, sans ZIP), suivez d'abord la [Variante B du README principal](../README.md#variante-b--deux-vm-debian-sans-zip) : elle vous renvoie ici pour les sections 0 et 2 à 8. **Exécutez les sections 0 à 8 dans l'ordre**, puis revenez à l'étape 4 du [README principal](../README.md). Les commandes sont à lancer dans un terminal Debian, sauf mention contraire.

Le client Windows envoie des mesures au serveur Python sur le port TCP `5000`. Le serveur écrit les mesures dans MariaDB, qui reste locale à Debian sur `127.0.0.1:3306`. N'ouvrez pas le port `3306` au réseau.

Dans ce guide, le nom d'utilisateur Debian `etudiant` est un exemple : remplacez-le par le vôtre (la commande `whoami` l'affiche).

## 0. Vérifier que `sudo` fonctionne

Presque toutes les commandes utilisent `sudo`. Testez-le :

```bash
sudo whoami
```

**Résultat attendu :** `root` (après avoir saisi votre mot de passe).

Si le message est `etudiant is not in the sudoers file` ou `sudo: command not found`, c'est fréquent sur une Debian neuve dont l'installation a défini un mot de passe root. Corrigez-le une fois pour toutes :

```bash
su -
apt-get install -y sudo
usermod -aG sudo etudiant
exit
```

`su -` demande le **mot de passe root** choisi pendant l'installation de Debian. Remplacez `etudiant` par votre nom d'utilisateur. **Fermez ensuite complètement votre session** (déconnexion, ou redémarrage de la VM) et reconnectez-vous : le nouveau droit n'est pris en compte qu'à la connexion suivante. Refaites `sudo whoami` pour vérifier.

## 1. Envoyer le projet du PC Windows vers la VM

Situation de départ : le ZIP du projet est sur le **PC 1** (Windows, celui qui lancera l'application) et la VM Debian tourne sur le **PC 2**. On va copier le ZIP à travers le réseau avec la commande `scp`, déjà intégrée à Windows 10 et 11.

```text
   PC 1 — Windows                                 PC 2 — héberge la VM
   ┌────────────────────────┐                     ┌──────────────────────────┐
   │ Les_Nameks.zip         │   réseau de la      │  VM Debian               │
   │ PowerShell : scp ──────┼──── salle ─────────►│  serveur SSH (port 22)   │
   └────────────────────────┘                     │  ~/Les_Nameks.zip        │
                                                  └──────────────────────────┘
```

`scp` (*secure copy*) copie un fichier vers une autre machine en passant par SSH. Il faut donc que la VM soit **joignable par le réseau** et qu'un **serveur SSH** y tourne. Les étapes 1.1 et 1.2 préparent la VM, les étapes 1.3 à 1.5 se font depuis le PC 1.

> Si la VM tourne sur le **même PC** que le ZIP, vous pouvez aussi utiliser le dossier partagé de VirtualBox ou une clé USB, puis passer directement à l'étape 1.5. La méthode `scp` ci-dessous fonctionne dans tous les cas.
>
> **Pas de ZIP, ou deux VM Debian ?** Copiez directement le dossier du projet comme expliqué à l'[étape B.2 du README principal](../README.md#b2-copier-le-projet-sur-les-deux-vm-sans-zip), puis reprenez ce guide à la section 2.

### 1.1 Mettre la VM sur le réseau de la salle (sur le PC 2)

Dans VirtualBox, sur le PC 2 : sélectionnez la VM, puis **Configuration → Réseau → Carte 1** :

- **Mode d'accès réseau** : `Accès par pont` ;
- **Nom** : la carte réseau réelle du PC 2 (celle qui est branchée : Ethernet ou Wi-Fi).

Validez, puis démarrez (ou redémarrez) la VM. En mode « Accès par pont », la VM obtient sa propre adresse sur le réseau de la salle, comme un vrai ordinateur : le PC 1 pourra la joindre pour `scp` maintenant, et pour le port `5000` du serveur plus tard.

Avec VMware, l'équivalent est le mode **Bridged**. Si l'enseignant impose un autre mode réseau, demandez-lui comment joindre la VM depuis un autre poste.

### 1.2 Activer SSH et relever l'adresse de la VM (terminal Debian)

Dans un terminal de la VM :

```bash
sudo apt-get update
sudo apt-get install -y openssh-server unzip
sudo systemctl enable --now ssh
sudo systemctl is-active ssh
ip -4 -brief address
```

**Résultat attendu :**
- `sudo systemctl is-active ssh` affiche `active` ;
- `ip -4 -brief address` affiche une ligne comme `enp0s3   UP   192.168.1.50/24`. **Notez cette adresse** (ici `192.168.1.50`, sans le `/24`). Ignorez la ligne `lo` (`127.0.0.1`).

Si l'adresse est `10.0.2.15`, la VM est encore en mode NAT : revenez à l'étape 1.1.

Notez aussi votre nom d'utilisateur Debian (commande `whoami`) et son mot de passe : `scp` les demandera.

### 1.3 Vérifier que le PC 1 voit la VM (PowerShell, PC 1)

Sur le PC 1, ouvrez PowerShell (menu Démarrer → « PowerShell ») et testez le port SSH de la VM, en remplaçant l'adresse par celle notée à l'étape 1.2 :

```powershell
Test-NetConnection -ComputerName 192.168.1.50 -Port 22
```

**Résultat attendu :** `TcpTestSucceeded : True`.

Si le résultat est `False` : vérifiez l'adresse, que la VM est démarrée, que `ssh` est `active` (étape 1.2) et que les deux PC sont sur le même réseau de salle. Sur certains réseaux (Wi-Fi invité, réseau isolé), les postes ne peuvent pas se joindre : demandez à l'enseignant.

### 1.4 Envoyer le ZIP (PowerShell, PC 1)

Placez-vous dans le dossier qui contient `Les_Nameks.zip` (souvent `Téléchargements`), puis envoyez-le :

```powershell
cd $HOME\Downloads
scp .\Les_Nameks.zip etudiant@192.168.1.50:~/
```

Décomposition de la commande :

| Morceau | Signification |
|---|---|
| `.\Les_Nameks.zip` | le fichier à envoyer, dans le dossier courant |
| `etudiant` | votre nom d'utilisateur **Debian** (pas celui de Windows) |
| `192.168.1.50` | l'adresse de la VM notée à l'étape 1.2 |
| `:~/` | la destination : le dossier personnel de cet utilisateur sur la VM |

Ce qui va s'afficher :

1. **À la première connexion seulement :** `Are you sure you want to continue connecting (yes/no/[fingerprint])?` → tapez `yes` puis Entrée. Windows mémorise ainsi l'identité de la VM.
2. `etudiant@192.168.1.50's password:` → tapez le mot de passe Debian puis Entrée. **Rien ne s'affiche pendant la saisie, c'est normal.**
3. Une ligne de progression se termine par `100%` : le fichier est arrivé.

**Astuce :** si le ZIP est ailleurs, tapez `scp ` (avec un espace), **glissez le fichier ZIP depuis l'Explorateur dans la fenêtre PowerShell** (son chemin complet s'écrit tout seul), puis complétez avec ` etudiant@192.168.1.50:~/`.

**Vous n'avez que le dossier `C:\Les_Nameks`, pas de ZIP ?** Créez-en un avec la commande `tar` intégrée à Windows, qui laisse de côté les dossiers inutiles (`.venv`, `__pycache__`), puis envoyez-le :

```powershell
tar -a -cf "$HOME\Desktop\Les_Nameks.zip" --exclude=.venv --exclude=__pycache__ -C C:\ Les_Nameks
scp "$HOME\Desktop\Les_Nameks.zip" etudiant@192.168.1.50:~/
```

### 1.5 Extraire le projet (terminal Debian)

Sur la VM :

```bash
cd ~
unzip Les_Nameks.zip
cd ~/Les_Nameks
ls
```

**Résultat attendu :** `README.md`, `reseau` et `deploiement_debian` apparaissent. Si `cd ~/Les_Nameks` échoue, regardez le nom réel du dossier avec `ls ~` et renommez-le, par exemple `mv ~/Les_Nameks-main ~/Les_Nameks`.

**Envoyer une nouvelle version plus tard :** refaites l'étape 1.4, puis `cd ~ && unzip -o Les_Nameks.zip` (`-o` remplace les anciens fichiers sans poser de question). Votre fichier `deploiement_debian/.env` n'est pas dans le ZIP : il est conservé.

### Astuce : piloter la VM depuis PowerShell

Maintenant que SSH fonctionne, vous pouvez ouvrir un terminal Debian **directement dans PowerShell** sur le PC 1, et suivre la suite de ce guide sans aller sur le PC 2 :

```powershell
ssh etudiant@192.168.1.50
```

Toutes les commandes tapées ensuite s'exécutent sur la VM ; `exit` revient à Windows. Attention : si le serveur TCP (section 8) est lancé dans cette fenêtre, fermer la fenêtre arrête le serveur.

## 2. Installer les paquets système

Le script vérifie la famille de la distribution, installe MariaDB et PyMySQL, puis active le service :

```bash
cd "$HOME/Les_Nameks/deploiement_debian"
bash installer.sh
```

Le script peut demander le mot de passe `sudo`. Il ne crée pas et ne réinitialise pas la base de données. **Résultat attendu :** le message `MariaDB est actif.`

Vérifiez ensuite le service :

```bash
sudo systemctl is-active mariadb
```

Résultat attendu : `active`. S'il est inactif, consultez `sudo systemctl status mariadb --no-pager` et corrigez l'erreur avant de continuer. Si l'installation apt échoue, vérifiez l'accès Internet de la VM et réessayez.

Le script installe `mariadb-server`, `python3-pymysql` et `python3-venv`. PyMySQL est la seule dépendance Python du serveur et du test de base ; PyQt6 n'est utilisé que par l'application Windows. Le paquet `python3-venv` n'est pas nécessaire pour suivre ce guide.

## 3. Initialiser MariaDB sur une VM neuve

### Attention : installation neuve ou existante

Les commandes ci-dessous sont pour une VM neuve, sans base `simulation_trafic` à préserver. `init_db.sql` utilise `CREATE DATABASE/TABLE IF NOT EXISTS` et ne vide pas les tables, mais ne permet pas de mettre à niveau une table déjà existante. `migration_stats.sql` ajoute seulement les trois colonnes qui manquent. Pour une base existante, ne suivez pas aveuglément l'initialisation neuve : utilisez la procédure de mise à jour de la **section 10**, vérifiez le schéma et faites d'abord une sauvegarde.

### Créer la base et les six colonnes de mesures

Toujours depuis `~/Les_Nameks/deploiement_debian`, exécutez les deux scripts **dans cet ordre** :

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

Vous devez voir la table `statistiques` et les colonnes des six mesures :

```text
vehicules_actifs
vehicules_arrives
vehicules_prioritaires
temps_moyen_trajet
vehicules_attente_feu
vehicules_bouchon
```

Les mesures de comptage sont des entiers ; `temps_moyen_trajet` est de type `double`. Si une colonne manque, vérifiez d'abord la sortie de chaque commande SQL et l'état de la base. Ne supprimez pas la base.

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

`EXEMPLE_FICTIF_A_REMPLACER` n'est pas un mot de passe utilisable. Pour simplifier la saisie, choisissez une chaîne de lettres et de chiffres, sans apostrophe ni guillemet. Gardez les apostrophes qui entourent le mot de passe dans la commande SQL.

`DB_HOST` vaut `127.0.0.1` dans la configuration, donc le compte est créé pour cette adresse de boucle locale. Cela permet au serveur Python sur Debian de parler à MariaDB sans rendre la base accessible depuis Windows.

Sur une installation existante, le compte peut déjà exister. N'exécutez pas `CREATE USER` tel quel en supposant l'état du serveur : vérifiez les comptes et droits avec l'administrateur, et utilisez `ALTER USER` si un changement de mot de passe est requis. Ne partagez jamais le mot de passe pour obtenir de l'aide.

## 5. Créer le fichier de configuration `.env`

Le serveur lit les paramètres MariaDB dans `~/Les_Nameks/deploiement_debian/.env`. Le ZIP ne contient que `.env.example`, qui n'a pas de mot de passe. Depuis `deploiement_debian/`, créez votre fichier local et protégez ses permissions :

```bash
cd "$HOME/Les_Nameks/deploiement_debian"
cp .env.example .env
chmod 600 .env
nano .env
```

Renseignez les valeurs suivantes. Exemple fictif — le mot de passe doit être remplacé par celui choisi à la section 4 :

```dotenv
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=simulation_trafic
DB_USER=trafic
DB_PASSWORD=EXEMPLE_FICTIF_A_REMPLACER
```

Ces cinq noms correspondent exactement à ceux lus par `reseau/serveur.py` et `tester_db.py`. `DB_PASSWORD` doit être identique au mot de passe de l'utilisateur MariaDB, **sans** les apostrophes de la commande SQL. Dans nano, enregistrez avec `Ctrl+O`, Entrée, puis quittez avec `Ctrl+X`.

Vérifiez que le fichier existe et n'est lisible que par vous, sans afficher son contenu :

```bash
ls -l .env
```

**Résultat attendu :** une ligne commençant par `-rw-------`.

Le `.env` ne doit jamais être inclus dans le ZIP final ni partagé. Ne l'affichez pas avec `cat`, ne faites pas de capture d'écran de son contenu et ne le copiez pas dans un ticket.

## 6. Tester la connexion à MariaDB

Depuis la racine du projet :

```bash
cd "$HOME/Les_Nameks"
python3 deploiement_debian/tester_db.py
```

**Résultat attendu :** `Connexion à MariaDB réussie. Lignes dans statistiques : 0.` (le nombre peut être supérieur à zéro si des mesures existent déjà). Le test lit `.env`, exécute `SELECT COUNT(*)` et ferme la connexion. Il ne modifie pas la base.

Si le test dit que PyMySQL manque, exécutez `sudo apt-get install -y python3-pymysql`. Pour un accès refusé, vérifiez les cinq paramètres et les droits sans révéler le mot de passe. Pour une erreur de connexion locale, vérifiez `sudo systemctl is-active mariadb`.

## 7. Trouver l'adresse Debian et préparer le réseau

Le serveur écoute sur `0.0.0.0:5000`, donc sur toutes les interfaces réseau de la VM. Pour trouver l'adresse IPv4 de Debian :

```bash
ip -4 -brief address
```

Relevez l'adresse de l'interface réseau (souvent `enp0s3`, `ens33` ou `eth0`), pas celle de `lo` (`127.0.0.1`). Notez-la : elle servira à l'étape 4 du README principal.

**Mode réseau de la VM.** C'est la même adresse que celle utilisée pour `scp` à la section 1 : si l'envoi du ZIP a fonctionné, le PC Windows pourra aussi joindre le port 5000. Si l'adresse est du type `10.0.2.15`, la VM est en mode **NAT** et Windows ne pourra pas la joindre : repassez-la en **Accès par pont** (section 1.1), puis relevez à nouveau l'adresse avec la commande ci-dessus.

**Pare-feu.** Une Debian neuve n'active pas de pare-feu par défaut. Si UFW est installé et actif (`sudo ufw status` affiche `Status: active`), autorisez uniquement la machine Windows vers le port 5000 :

```bash
sudo ufw allow from 192.168.1.25 to any port 5000 proto tcp
```

Remplacez `192.168.1.25` par l'adresse de la machine Windows. Pour un autre pare-feu, demandez à l'administrateur la règle équivalente. Ne désactivez pas le pare-feu et n'ouvrez jamais `3306` au réseau.

## 8. Démarrer le serveur TCP

Depuis la racine du projet :

```bash
cd "$HOME/Les_Nameks"
python3 reseau/serveur.py
```

**Résultat attendu :** `Serveur en écoute sur 0.0.0.0:5000...`. **Laissez ce terminal ouvert** pendant toute la simulation : fermer le terminal arrête le serveur. À chaque relevé reçu, il affiche `Client connecté : …` puis `Statistiques enregistrées dans MariaDB.`

Dans un second terminal, vous pouvez confirmer l'écoute :

```bash
sudo ss -ltnp | grep ':5000'
```

Pour arrêter le serveur, utilisez `Ctrl+C`. Les erreurs MariaDB sont affichées sans révéler la valeur du mot de passe. Le serveur n'a ni chiffrement ni authentification de client : ne l'exposez qu'au réseau de TP de confiance.

**Le serveur est prêt.** Revenez à l'**étape 4** du [README principal](../README.md) pour relier Windows à Debian.

## 9. Vérification de bout en bout (récapitulatif)

### Côté Debian

1. `sudo systemctl is-active mariadb` doit afficher `active`.
2. `sudo mariadb -e "SHOW TABLES IN simulation_trafic;"` doit montrer `statistiques`.
3. `sudo mariadb simulation_trafic -e "SHOW COLUMNS FROM statistiques;"` doit montrer les six mesures listées à la section 3.
4. `python3 deploiement_debian/tester_db.py` (depuis `~/Les_Nameks`) doit confirmer la connexion.
5. Le serveur doit afficher qu'il écoute sur `0.0.0.0:5000`.

### Côté Windows

1. `Test-NetConnection -ComputerName $env:NAMEKS_SERVER_HOST -Port 5000` doit donner `TcpTestSucceeded : True` (étape 4 du README principal).
2. Dans ce même PowerShell, lancez l'application, cliquez sur **Graphe de test**, puis **Démarrer**.

### Vérifier les lignes enregistrées

Laissez tourner la simulation au moins dix secondes. Depuis Debian, dans un autre terminal :

```bash
sudo mariadb simulation_trafic -e "SELECT id, date_mesure, vehicules_actifs, vehicules_arrives, vehicules_prioritaires, temps_moyen_trajet, vehicules_attente_feu, vehicules_bouchon FROM statistiques ORDER BY id DESC LIMIT 10;"
```

De nouvelles lignes doivent apparaître pendant que la simulation fonctionne, environ une toutes les cinq secondes. `temps_moyen_trajet` peut être `0` tant qu'aucun trajet n'est terminé. Si le serveur n'est pas joignable, l'interface continue la simulation mais le terminal Windows affiche une erreur d'envoi et aucune nouvelle ligne n'est insérée.

## 10. Mise à jour d'une installation existante

Cette procédure ne s'applique pas à une VM vierge. Avant toute modification, arrêtez le serveur TCP, confirmez le nom de la base et faites une sauvegarde non vide. Ne lancez pas `init_db.sql` pour tenter de réparer une installation existante et ne supprimez aucune base.

Vérifiez d'abord les tables et colonnes actuelles :

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

Vérifiez que le fichier existe et n'est pas vide. Puis, si la table `statistiques` existe et que l'objectif est seulement d'ajouter les trois nouvelles mesures, lancez la migration réexécutable :

```bash
cd "$HOME/Les_Nameks/deploiement_debian"
sudo mariadb < migration_stats.sql
```

Revérifiez les colonnes avec `SHOW COLUMNS`. La migration n'efface pas les lignes et ajoute `DEFAULT 0` aux nouvelles colonnes. En cas d'erreur ou si la base diffère de ce schéma, arrêtez-vous et demandez conseil à l'administrateur plutôt que de réinitialiser la base.

## 11. Problèmes fréquents et solutions

| Symptôme | Cause probable | Vérification et solution |
| --- | --- | --- |
| `is not in the sudoers file` | L'utilisateur n'a pas le droit d'utiliser `sudo`. | Section 0 : `su -`, `usermod -aG sudo etudiant`, puis se déconnecter et se reconnecter. |
| `sudo: command not found` | Paquet sudo absent. | Section 0 : `su -` puis `apt-get install -y sudo`. |
| `scp` ou `ssh` : `Connection timed out` | La VM n'est pas joignable : mode NAT, mauvaise adresse ou PC sur des réseaux différents. | Section 1.1 (Accès par pont) puis 1.2 (relever l'adresse) ; tester avec `Test-NetConnection -ComputerName <adresse> -Port 22`. |
| `scp` ou `ssh` : `Connection refused` | La VM est joignable mais le serveur SSH ne tourne pas. | Sur la VM : `sudo systemctl enable --now ssh`, puis `sudo systemctl is-active ssh`. |
| `Permission denied, please try again.` | Mauvais nom d'utilisateur ou mot de passe Debian. | Utiliser le nom affiché par `whoami` **sur la VM** et son mot de passe. Le compte `root` est refusé par SSH : utilisez votre utilisateur normal. |
| `WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!` | La VM a été réinstallée ou l'adresse est réutilisée par une autre machine. | Sur le PC Windows : `ssh-keygen -R 192.168.1.50` (avec l'adresse de la VM), puis relancer `scp` et répondre `yes`. |
| `scp : Le terme « scp » n'est pas reconnu…` | Client OpenSSH absent de Windows (rare). | Paramètres Windows → Système → Fonctionnalités facultatives → Ajouter une fonctionnalité → **Client OpenSSH**, puis rouvrir PowerShell. |
| `cd: …/Les_Nameks: No such file or directory` | Dossier extrait sous un autre nom ou ailleurs. | `ls "$HOME"`, puis renommer le dossier en `Les_Nameks` (section 1). |
| `$'\r': command not found` en lançant `installer.sh` | Le script a été enregistré avec des fins de ligne Windows. | `sed -i 's/\r$//' installer.sh`, puis relancer `bash installer.sh`. |
| `python3: command not found` | Python absent ou PATH inhabituel. | `sudo apt-get install -y python3`. |
| `No module named pymysql` | Paquet système absent. | `sudo apt-get install -y python3-pymysql`. |
| Le serveur ou le test affiche `Configuration … impossible à lire` | Fichier absent du dossier exact ou valeur requise vide. | Créer `deploiement_debian/.env` depuis `.env.example` (section 5) ; ne pas afficher son contenu. |
| Accès MariaDB refusé (1045) | Nom d'utilisateur, mot de passe ou hôte de compte incorrect. | Vérifier les paramètres localement et `SHOW GRANTS` ; rétablir les droits sans partager le secret. |
| MariaDB arrêtée / connexion locale refusée (2003) | Service arrêté ou mauvais `DB_HOST` ou port. | `sudo systemctl status mariadb --no-pager` ; `.env` doit utiliser `127.0.0.1` et `3306`. |
| Base ou table inconnue | Scripts SQL non appliqués ou mauvais nom. | `sudo mariadb -e "SHOW TABLES IN simulation_trafic;"` ; sur une VM neuve, suivre les deux commandes de la section 3. |
| Colonne inconnue dans INSERT | Migration absente. | `SHOW COLUMNS FROM statistiques` ; ne migrer une base existante qu'après sauvegarde et selon la section 10. |
| `Impossible de démarrer le serveur TCP : le port 5000 est peut-être déjà utilisé.` | Un autre processus utilise déjà le port 5000 (souvent un serveur déjà lancé dans un autre terminal). | `sudo ss -ltnp \| grep ':5000'` ; identifier le processus avant toute action, ne pas l'arrêter à l'aveugle. |
| Windows indique `Connection refused` | Serveur arrêté ou port bloqué. | Debian : vérifier `ss` ; Windows : `Test-NetConnection -ComputerName $env:NAMEKS_SERVER_HOST -Port 5000`. |
| Windows indique timeout / inaccessible | VM en mode NAT, adresse d'une mauvaise interface ou pare-feu. | Comparer l'adresse avec `ip -4 -brief address` ; passer la VM en Accès par pont ou ajouter la redirection du port 5000 (README principal, étape 4.1). |
| Simulation active, aucune ligne n'arrive | Port injoignable, mauvais `.env`, colonnes manquantes ou serveur arrêté. | Lire les deux terminaux, refaire le test de la section 6, `Test-NetConnection`, puis la requête de la section 9. |

Ne désactivez pas le pare-feu et n'exposez pas MariaDB pour contourner une erreur réseau. Le port `3306` doit rester local à Debian ; seul le port TCP `5000` doit être autorisé depuis le réseau de TP concerné.
