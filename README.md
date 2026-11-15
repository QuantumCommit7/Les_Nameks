# Les_Nameks — simulateur de trafic routier

## Identification

| | |
| --- | --- |
| **Nom du groupe** | Les Nameks |
| **Étudiant 1** | SCHNEIDER FETIQUE Nathan |
| **Étudiant 2** | SICHARD Lommé |
| **Formation** | BUT2 R&T, IUT de Colmar |
| **Dépôt** | <https://github.com/QuantumCommit7/Les_Nameks> |

## Sommaire

1. [Ce que fait le projet](#ce-que-fait-le-projet)
2. [Choisir votre configuration](#choisir-votre-configuration)
3. [Installation — configuration A : application Windows + serveur Debian](#étape-1--cloner-le-dépôt-windows)
4. [Utilisation et exemples](#utiliser-linterface)
5. [Installation — configuration B : deux VM Debian](#variante-b--deux-vm-debian-sans-zip)
6. [Organisation et conventions du code](#organisation-et-conventions-du-code)
7. [Dépannage](#problèmes-fréquents)

Ce guide permet à un groupe qui découvre le projet de l'installer, de lancer le simulateur, puis d'enregistrer ses statistiques sur une VM Debian. **Suivez les étapes dans l'ordre, sans en sauter.** Chaque étape se termine par un résultat attendu : ne passez à la suivante que lorsque vous l'avez obtenu.

## Ce que fait le projet

Les_Nameks est un simulateur pédagogique de circulation routière. L'application PyQt6 représente les routes par un graphe pondéré, calcule les chemins avec Dijkstra, puis anime des véhicules, des feux et des véhicules prioritaires. Elle affiche six mesures et les envoie au serveur Debian. Le serveur Python reçoit les messages par TCP et les enregistre dans MariaDB.

Les composants réseau sont simples : le client ouvre une connexion TCP au serveur sur le port `5000`, envoie un objet JSON UTF-8 terminé par un saut de ligne, puis ferme la connexion. Des threads évitent de bloquer l'interface et permettent au serveur de traiter plusieurs clients. MariaDB n'est utilisée que par le serveur sur la VM, via PyMySQL. Ce service scolaire n'est pas conçu pour être exposé sur Internet.

## Choisir votre configuration

Le projet a deux parties : **l'application** (le simulateur avec sa fenêtre) et **le serveur** (qui enregistre les statistiques dans MariaDB). Le serveur est toujours sur une VM Debian ; l'application peut être sur Windows ou sur une seconde VM Debian.

| Configuration | Application | Serveur | Suivre |
| --- | --- | --- | --- |
| **A** | PC Windows | VM Debian | Les étapes 1 à 6 ci-dessous |
| **B** | VM Debian (avec bureau graphique) | Une seconde VM Debian | La [Variante B — deux VM Debian](#variante-b--deux-vm-debian-sans-zip), plus bas |

Si l'enseignant impose deux VM, choisissez la configuration B.

## Vue d'ensemble du déploiement (configuration A)

| Étape | Où | Ce que l'on obtient |
| --- | --- | --- |
| 1. Cloner le dépôt | Windows | Le dossier `C:\Les_Nameks` |
| 2. Installer et lancer l'application | Windows | Le simulateur fonctionne (sans serveur) |
| 3. Installer le serveur | Debian | MariaDB et le serveur TCP en écoute sur le port 5000 |
| 4. Relier Windows à Debian | Windows + hyperviseur | `TcpTestSucceeded : True` |
| 5. Lancer la simulation complète | Windows | Les statistiques partent toutes les 5 s |
| 6. Vérifier la base | Debian | Les lignes apparaissent dans MariaDB |

L'application Windows fonctionne seule : les étapes 1 et 2 suffisent pour voir le simulateur. Le serveur Debian ne sert qu'à enregistrer les statistiques.

## Fichiers utiles

- `application/` : interface et simulation PyQt6. `interface.py` est le point de lancement.
- `reseau/client.py` et `reseau/serveur.py` : client (côté application) et serveur (côté VM Debian).
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

`.venv/`, `__pycache__/` et les fichiers `.pyc` sont des éléments générés automatiquement : ils ne font pas partie du dépôt (voir `.gitignore`).

---

## Étape 1 — Cloner le dépôt (Windows)

**Dans PowerShell** (menu Démarrer → « PowerShell »), vérifiez d'abord que Git est installé :

```powershell
git --version
```

Si la commande affiche une version (par exemple `git version 2.47.0.windows.1`), passez à la suite. Sinon, installez Git, puis **fermez et rouvrez PowerShell** :

```powershell
winget install --id Git.Git -e
```

(ou téléchargez l'installateur sur <https://git-scm.com/download/win> et gardez les options par défaut).

Clonez ensuite le dépôt dans `C:\Les_Nameks` :

```powershell
cd C:\
git clone https://github.com/QuantumCommit7/Les_Nameks.git
cd C:\Les_Nameks
dir
```

**Résultat attendu :** `dir` affiche `README.md`, `requirements.txt`, `application`, `reseau` et `deploiement_debian`.

**Mettre à jour plus tard** avec la dernière version du dépôt : `cd C:\Les_Nameks` puis `git pull`.

**Sans Git :** sur la page GitHub du dépôt, cliquez sur **Code → Download ZIP**, faites un clic droit sur le fichier téléchargé → **Extraire tout…**, choisissez `C:\` comme destination, puis renommez le dossier obtenu `C:\Les_Nameks-main` en `C:\Les_Nameks`.

Ne copiez pas un dossier `.venv` venant d'une autre machine : un environnement virtuel dépend du système et du chemin Python qui l'a créé. Il sera créé à l'étape 2.

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

`py -m venv .venv` crée un **environnement virtuel** : un dossier `.venv` qui contient un Python propre au projet, pour que les bibliothèques installées n'interfèrent pas avec le reste de l'ordinateur. Les commandes suivantes utilisent directement le Python de cet environnement (`.venv\Scripts\python.exe`) : il n'est donc pas nécessaire de l'« activer », ce qui évite les blocages de la politique d'exécution PowerShell. `requirements.txt` contient PyQt6 (l'interface) et PyMySQL (utilisé seulement côté serveur, sans effet sur Windows).

Si vous préférez activer l'environnement (facultatif), tapez `.\.venv\Scripts\Activate.ps1` : `(.venv)` apparaît au début de la ligne, et `python` désigne alors le Python de l'environnement. Si PowerShell refuse (« l'exécution de scripts est désactivée »), gardez simplement la méthode ci-dessus.

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
| Tout effacer | **Réinitialiser (tout effacer)** : arrête la simulation et vide le tableau (nœuds, routes, feux, véhicules). |
| Lancer / suspendre | **Démarrer** / **Pause**. La simulation démarre toujours en pause. |
| Zoomer / se déplacer | Molette pour zoomer ; clic du milieu, ou clic droit dans le vide, maintenu pour déplacer la vue. |
| Ajouter un nœud | **Ajouter un nœud**, puis clic gauche dans une zone vide, puis saisir un nom. |
| Créer une route | Clic gauche sur un premier nœud, puis sur un second, puis saisir la distance et choisir son unité (**m** ou **km**). La distance est enregistrée en mètres et sert à Dijkstra pour trouver le chemin le plus court ; elle s'affiche en km au-delà de 1 000 m. |
| Déplacer un nœud | Clic gauche maintenu sur le nœud, puis glisser. |
| Renommer / supprimer un nœud | Clic droit sur le nœud. Possible uniquement s'il n'y a aucun véhicule : recréez le **Graphe de test** avec la densité **Aucun**, ou partez d'un tableau vide avec **Réinitialiser**. |
| Ajouter un feu | **Ajouter un feu**, puis choisir un carrefour qui a **exactement 4 routes**. |
| Créer un véhicule | **Créer véhicule**, puis choisir départ, destination et type (Normal ou Prioritaire). La vitesse suit le code de la route : tous les véhicules normaux roulent à la même vitesse limite, les prioritaires plus vite, et les véhicules se rangent sur le côté pour les laisser passer. |
| Voir le trajet d'un véhicule | Clic gauche sur le véhicule : son chemin Dijkstra s'affiche en orange. Second clic pour l'effacer. |

### Exemples d'utilisation

**Exemple 1 — démonstration en 30 secondes**

1. Lancez l'application : `.\.venv\Scripts\python.exe application\interface.py`.
2. Choisissez la densité **Moyen**, puis cliquez sur **Graphe de test** : 26 carrefours (A à Z), 7 feux et 12 véhicules apparaissent.
3. Cliquez sur **Démarrer**. Les véhicules roulent à la même vitesse limite, s'arrêtent aux feux rouges et repartent au vert ; les feux changent toutes les 5 secondes.
4. Observez le panneau **STATISTIQUES** : véhicules arrivés, temps moyen de trajet, véhicules en attente au feu ou dans un bouchon. Chaque véhicule arrivé est remplacé pour garder 12 véhicules.

**Exemple 2 — un véhicule d'urgence**

1. Avec le graphe de test chargé, cliquez sur **Créer véhicule** : départ `A`, destination `Z`, type **Prioritaire**.
2. Le véhicule blanc à gyrophare bleu et rouge roule plus vite que les autres. Les véhicules qu'il rattrape se rangent sur le côté et s'arrêtent pour le laisser passer ; à l'approche d'un feu rouge, il le fait passer au vert.
3. Cliquez sur lui : son trajet Dijkstra s'affiche en orange.

**Exemple 3 — construire son propre réseau**

1. Cliquez sur **Réinitialiser (tout effacer)**.
2. **Ajouter un nœud** puis clic dans le vide : créez ainsi `A`, `B` et `C`.
3. Cliquez sur `A` puis sur `B`, saisissez `500` et l'unité `m` ; cliquez sur `B` puis sur `C`, saisissez `1,2` (ou `1.2` si Windows est en anglais) et l'unité `km`. Les routes affichent « 500 m » et « 1,2 km ».
4. **Créer véhicule** de `A` vers `C`, type Normal, puis **Démarrer** : le véhicule passe par `B`.

## Étape 3 — Installer le serveur (Debian)

Toute la partie Debian est décrite dans **[`deploiement_debian/README.md`](deploiement_debian/README.md)**. Suivez ce guide **de la section 0 à la section 8, dans l'ordre**, puis revenez ici.

Sa **section 1** explique comment mettre le projet sur la VM : le plus simple est de **cloner le dépôt directement sur la VM** avec `git clone` (section 1.0). Si la VM n'a pas accès à Internet, la suite de la section 1 explique pas à pas comment l'envoyer depuis ce PC Windows avec `scp`, même si la VM tourne sur un autre PC.

Ne lancez pas le serveur avant d'avoir créé le compte MariaDB et le fichier `.env` (sections 4 et 5 du guide) : sans `.env`, le serveur refuse de démarrer et affiche `Configuration MariaDB impossible à lire`.

**Liste de contrôle à la fin du guide Debian :**

- [ ] `sudo systemctl is-active mariadb` affiche `active` ;
- [ ] `python3 deploiement_debian/tester_db.py` affiche `Connexion à MariaDB réussie` ;
- [ ] le serveur affiche `Serveur en écoute sur 0.0.0.0:5000...` et son terminal reste ouvert ;
- [ ] vous avez noté l'adresse IPv4 de la VM (section 7 du guide).

## Étape 4 — Relier Windows à Debian

Windows doit pouvoir joindre le port TCP `5000` de la VM. C'est l'étape qui pose le plus souvent problème en TP, à cause du mode réseau de la VM.

### 4.1 Vérifier le mode réseau de la VM

Dans VirtualBox, VM arrêtée ou non : **Configuration → Réseau → Carte 1 → Mode d'accès réseau**.

Si vous avez envoyé le projet avec `scp` (section 1 du guide Debian), la VM est déjà en **Accès par pont** et joignable : utilisez ci-dessous **la même adresse** que pour `scp`, et passez à l'étape 4.2.

- **Accès par pont** (recommandé, et obligatoire si la VM tourne sur un autre PC) : la VM obtient une adresse du réseau de la salle, du type `192.168.x.x` ou `10.x.x.x`, directement joignable depuis les autres postes. Utilisez cette adresse ci-dessous.
- **NAT** (mode par défaut de VirtualBox) : la VM n'est **pas joignable** depuis un autre poste (son adresse est souvent `10.0.2.15`). Passez en **Accès par pont**, redémarrez la VM et relevez la nouvelle adresse.
  - Cas particulier, seulement si l'application et la VM sont sur **le même PC** : on peut garder NAT et ajouter une redirection (**Avancé → Redirection de ports → +**, protocole `TCP`, port hôte `5000`, port invité `5000`), puis utiliser l'adresse `127.0.0.1`.

Avec VMware, l'équivalent est le mode **Bridged**. Si le mode réseau est imposé par la salle, demandez à l'enseignant lequel utiliser.

### 4.2 Indiquer l'adresse à l'application

**Dans le PowerShell qui servira à lancer l'application**, depuis `C:\Les_Nameks` :

```powershell
$env:NAMEKS_SERVER_HOST = "192.168.1.50"
Test-NetConnection -ComputerName $env:NAMEKS_SERVER_HOST -Port 5000
```

Remplacez `192.168.1.50` par l'adresse de la VM (ou par `127.0.0.1` dans le cas particulier de la redirection NAT sur le même PC).

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

## Variante B — Deux VM Debian, sans ZIP

Cette partie remplace les étapes 1 à 6 quand **l'application et le serveur tournent chacun sur une VM Debian**. Dans les exemples :

| VM | Rôle | Adresse d'exemple |
| --- | --- | --- |
| **VM-APP** | lance le simulateur (fenêtre PyQt6) | `192.168.1.60` |
| **VM-SERVEUR** | serveur TCP + MariaDB | `192.168.1.50` |

```text
   VM-APP (Debian + bureau)                      VM-SERVEUR (Debian)
   ┌──────────────────────────┐   TCP port 5000   ┌──────────────────────────┐
   │ application/interface.py ├──────────────────►│ reseau/serveur.py        │
   │ reseau/client.py         │   relevés JSON    │ MariaDB (locale)         │
   └──────────────────────────┘                   └──────────────────────────┘
```

Remplacez partout les adresses d'exemple par les vôtres, et `etudiant` par votre nom d'utilisateur Debian.

### B.1 Préparer les deux VM (sur chacune)

1. **Réseau** : dans VirtualBox, **Configuration → Réseau → Carte 1 → Accès par pont**, comme à la [section 1.1 du guide Debian](deploiement_debian/README.md#11-mettre-la-vm-sur-le-réseau-de-la-salle-sur-le-pc-2). Les deux VM obtiennent ainsi une adresse sur le réseau de la salle et peuvent se joindre, qu'elles tournent sur le même PC ou sur deux PC différents.
2. **`sudo`** : vérifiez qu'il fonctionne ([section 0 du guide Debian](deploiement_debian/README.md#0-vérifier-que-sudo-fonctionne)).
3. **SSH et adresse** : dans un terminal de la VM :

   ```bash
   sudo apt-get update
   sudo apt-get install -y openssh-server
   sudo systemctl enable --now ssh
   ip -4 -brief address
   whoami
   ```

   Notez l'adresse de la VM (ligne qui n'est pas `lo`) et le nom d'utilisateur.

4. **Sur VM-APP uniquement, un bureau graphique est obligatoire** : le simulateur est une fenêtre. Si la VM démarre seulement sur un écran noir en mode texte, installez un bureau léger puis redémarrez (téléchargement d'environ 1 Go) :

   ```bash
   sudo apt-get install -y task-xfce-desktop
   sudo reboot
   ```

### B.2 Copier le projet sur les deux VM, sans ZIP

Le projet doit arriver dans `~/Les_Nameks` sur **chacune** des deux VM.

**Méthode 1 (recommandée) — cloner le dépôt sur chaque VM**, si les VM ont accès à Internet. Dans un terminal de **chaque** VM :

```bash
sudo apt-get install -y git
git clone https://github.com/QuantumCommit7/Les_Nameks.git ~/Les_Nameks
```

Pour récupérer plus tard une nouvelle version : `cd ~/Les_Nameks && git pull`.

**Méthode 2 — sans Internet sur les VM, le dossier du projet est sur un PC Windows** (PowerShell sur ce PC). Pour chaque VM, créez le dossier de destination, puis copiez-y les fichiers utiles :

```powershell
ssh etudiant@192.168.1.50 "mkdir -p ~/Les_Nameks"
scp -r C:\Les_Nameks\application C:\Les_Nameks\reseau C:\Les_Nameks\deploiement_debian C:\Les_Nameks\README.md C:\Les_Nameks\requirements.txt etudiant@192.168.1.50:~/Les_Nameks/
```

Refaites les deux commandes avec l'adresse de l'autre VM (`192.168.1.60`). Le mot de passe Debian est demandé à chaque commande, et `yes` à la toute première connexion (voir la [section 1.4 du guide Debian](deploiement_debian/README.md#14-envoyer-le-zip-powershell-pc-1) pour le détail de ce qui s'affiche). On liste les dossiers un par un pour **ne pas copier** un éventuel dossier `.venv` de Windows, inutile et très lourd.

**Méthode 3 — le projet est déjà sur l'une des VM** : copiez-le vers l'autre, depuis un terminal de la VM qui l'a :

```bash
scp -r ~/Les_Nameks etudiant@192.168.1.50:~/
```

**Vérification, sur chaque VM :**

```bash
ls ~/Les_Nameks
```

**Résultat attendu :** `application`, `reseau`, `deploiement_debian` et `README.md` apparaissent.

### B.3 Installer le serveur (VM-SERVEUR)

Suivez le [guide Debian](deploiement_debian/README.md) **sections 0 et 2 à 8** : la section 1 (récupération du projet) est remplacée par l'étape B.2. À la fin, le serveur affiche `Serveur en écoute sur 0.0.0.0:5000...` : laissez ce terminal ouvert.

### B.4 Installer et lancer l'application (VM-APP)

Ouvrez un terminal **dans le bureau graphique de VM-APP** (pas par `ssh` : une fenêtre ne peut pas s'afficher à travers une connexion SSH simple).

**Installer PyQt6.** Vérifiez d'abord la version de Debian :

```bash
cat /etc/debian_version
```

- **Debian 12 ou plus récent** (le résultat commence par `12` ou `13`) : PyQt6 est fourni par Debian, une seule commande suffit.

  ```bash
  sudo apt-get update
  sudo apt-get install -y python3-pyqt6
  python3 -c "import PyQt6.QtWidgets; print('PyQt6 OK')"
  ```

  Résultat attendu : `PyQt6 OK`. Dans la suite, la commande pour lancer Python est `python3`.

- **Debian 11** (le résultat commence par `11`) : le paquet `python3-pyqt6` n'existe pas. Installez PyQt6 dans un environnement virtuel :

  ```bash
  sudo apt-get install -y python3-venv libxcb-cursor0 libgl1 libegl1 libxkbcommon-x11-0
  python3 -m venv ~/Les_Nameks/.venv
  ~/Les_Nameks/.venv/bin/python -m pip install --upgrade pip
  ~/Les_Nameks/.venv/bin/python -m pip install PyQt6
  ```

  Dans la suite, remplacez `python3` par `~/Les_Nameks/.venv/bin/python`.

PyMySQL n'est pas nécessaire sur VM-APP : seule VM-SERVEUR parle à MariaDB.

**Premier lancement, sans serveur :**

```bash
cd ~/Les_Nameks
python3 application/interface.py
```

**Résultat attendu :** la fenêtre « Simulateur de trafic » s'ouvre ; **Graphe de test** puis **Démarrer** font circuler les véhicules. Le message `Envoi des statistiques impossible` dans le terminal est normal tant que l'étape B.5 n'est pas faite. Fermez la fenêtre.

### B.5 Relier VM-APP à VM-SERVEUR

Sur VM-APP, dans le terminal du bureau, indiquez l'adresse de VM-SERVEUR puis envoyez un message de test avec le client du projet :

```bash
cd ~/Les_Nameks
export NAMEKS_SERVER_HOST=192.168.1.50
python3 reseau/client.py
```

**Résultat attendu :** `Message envoyé avec succès.` sur VM-APP, et sur le terminal du serveur (VM-SERVEUR) : `Message texte reçu de 192.168.1.60 : Bonjour depuis le client Les_Nameks !`

Si vous obtenez `Connexion impossible`, vérifiez que le serveur tourne, l'adresse de VM-SERVEUR, le mode « Accès par pont » des deux VM et, si un pare-feu est actif sur VM-SERVEUR, la [section 7 du guide Debian](deploiement_debian/README.md#7-trouver-ladresse-debian-et-préparer-le-réseau) (autorisez l'adresse de VM-APP).

Lancez ensuite la simulation **dans ce même terminal** :

```bash
python3 application/interface.py
```

Cliquez sur **Graphe de test** puis **Démarrer**. Toutes les 5 secondes, le terminal du serveur affiche `Statistiques enregistrées dans MariaDB.`

`export` ne vaut que pour le terminal courant. Pour ne plus avoir à le retaper, ajoutez-le une fois pour toutes à la configuration du terminal, puis ouvrez un nouveau terminal :

```bash
echo 'export NAMEKS_SERVER_HOST=192.168.1.50' >> ~/.bashrc
```

### B.6 Vérifier les statistiques (VM-SERVEUR)

Comme à l'[étape 6](#étape-6--vérifier-les-six-statistiques-dans-mariadb-debian) :

```bash
sudo mariadb simulation_trafic -e "SELECT id, date_mesure, vehicules_actifs, vehicules_arrives, temps_moyen_trajet FROM statistiques ORDER BY id DESC LIMIT 5;"
```

### Problèmes propres à la variante B

| Symptôme | Cause probable | Solution |
| --- | --- | --- |
| `E: Unable to locate package python3-pyqt6` | Debian 11 ou plus ancien. | Utiliser la méthode « Debian 11 » de l'étape B.4 (environnement virtuel). |
| `ModuleNotFoundError: No module named 'PyQt6'` | PyQt6 non installé, ou lancé avec un autre Python que celui où il est installé. | Debian 12 : `sudo apt-get install -y python3-pyqt6`. Debian 11 : lancer avec `~/Les_Nameks/.venv/bin/python`. |
| `qt.qpa.plugin: Could not load the Qt platform plugin "xcb"` | Bibliothèque graphique manquante (surtout avec l'installation par pip). | `sudo apt-get install -y libxcb-cursor0 libxkbcommon-x11-0 libgl1 libegl1`. |
| `could not connect to display` | Application lancée par `ssh` ou depuis une console sans bureau. | Lancer depuis un terminal ouvert **dans le bureau graphique** de VM-APP (étape B.1, point 4). |
| `ssh: connect to host … Connection timed out` pendant la copie | Les VM ne se voient pas. | Vérifier l'Accès par pont des deux VM et leurs adresses (`ip -4 -brief address`). |
| Le client envoie vers `10.128.238.191` | `NAMEKS_SERVER_HOST` n'est pas défini dans ce terminal. | Refaire `export NAMEKS_SERVER_HOST=…` dans le terminal qui lance l'application. |

---

## Organisation et conventions du code

```text
Les_Nameks/
├── application/            l'application graphique (PyQt6)
│   ├── interface.py        point d'entrée : fenêtre, minuteries, règles de circulation
│   ├── scene_graphe.py     dessin du réseau et gestion de la souris
│   ├── vue_graphe.py       zoom et déplacement de la vue
│   ├── graphes.py          modèle du réseau : nœuds, routes, feux
│   ├── dijkstra.py         calcul du plus court chemin
│   ├── vehicule.py         progression d'un véhicule sur son chemin
│   └── graphe_test.py      données du réseau de démonstration
├── reseau/
│   ├── client.py           envoi des relevés JSON par TCP
│   └── serveur.py          réception, validation et enregistrement dans MariaDB
├── deploiement_debian/     installation du serveur (script, SQL, .env.example, test, guide)
├── requirements.txt        dépendances Python
└── README.md               ce document
```

- **Docstrings** : chaque module, classe et fonction a une docstring au **format Google** : une phrase de résumé, une explication si nécessaire, puis les rubriques `Args:` (paramètres), `Returns:` (valeur renvoyée), `Raises:` (exceptions) et `Attributes:` (attributs d'une classe). Exemple, dans `application/dijkstra.py` :

  ```python
  def dijkstra(graphe, depart, arrivee):
      """Calcule le chemin le plus court (en mètres) entre deux nœuds.

      Args:
          graphe (Graphes): réseau routier ; les poids des routes doivent être positifs.
          depart (str): nœud de départ.
          arrivee (str): nœud d'arrivée.

      Returns:
          list[str] | None: les nœuds du chemin, ou None si aucun chemin n'existe.
      """
  ```

  Dans un terminal Python, `help(dijkstra)` affiche cette documentation.
- **Commentaires** : en français, ils expliquent le *pourquoi* des lignes moins évidentes (calculs de position, règles de priorité, verrou réseau…).
- **Séparation des rôles** : le modèle (`graphes.py`, `vehicule.py`, `dijkstra.py`) ne dépend pas de l'interface ; l'interface (`interface.py`, `scene_graphe.py`, `vue_graphe.py`) ne fait qu'afficher et appeler le modèle ; la partie réseau (`reseau/`) est indépendante des deux.
- **Réglages** regroupés en constantes en haut des fichiers (vitesses et distances du code de la route dans `interface.py`, port et adresse dans `reseau/`).

## Dépendances et limitations connues

Les dépendances Python sont `PyQt6` et `PyMySQL` dans `requirements.txt`. Côté Debian, l'installateur fournit PyMySQL par le paquet système `python3-pymysql` ; la VM serveur n'a pas besoin de PyQt6. Dans la variante B, la VM application utilise le paquet `python3-pyqt6` (Debian 12 et plus) ou PyQt6 installé par pip (Debian 11), et n'a pas besoin de PyMySQL.

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
| Le serveur affiche `Configuration MariaDB impossible à lire` | Le fichier `deploiement_debian/.env` n'existe pas ou est incomplet. | Guide Debian, section 5. |
| Le serveur affiche une autre `Erreur MariaDB` | Compte, mot de passe, table ou colonnes incorrects. | Guide Debian, sections 3 à 6 et tableau de dépannage. |
| Aucune ligne, interface fonctionne | Simulation en pause, réseau inaccessible ou erreur SQL serveur. | Laisser tourner plus de cinq secondes, lire les terminaux Windows et Debian, refaire la requête de l'étape 6. |
| Impossible de renommer ou supprimer un nœud | Des véhicules sont présents (protection volontaire). | Recréer le **Graphe de test** avec la densité **Aucun**. |
| « Le carrefour doit avoir 4 routes » | Un feu ne s'installe que sur un carrefour à exactement 4 routes. | Choisir un autre carrefour ou ajouter/supprimer des routes. |

Pour les problèmes propres à Debian (`sudo`, MariaDB, `.env`, port déjà utilisé), consultez le tableau de dépannage du [guide Debian](deploiement_debian/README.md#11-problèmes-fréquents-et-solutions).

## Annexe — partager le projet sans Git (ZIP)

Le projet se récupère normalement en clonant le dépôt GitHub (étape 1). Si vous devez tout de même le transmettre sous forme de ZIP (clé USB, machine sans Internet), le ZIP doit s'extraire en un dossier nommé exactement `Les_Nameks`, et ne contenir aucun secret.

1. Dans l'Explorateur, créez un dossier vide `C:\livrable`, puis à l'intérieur un dossier **`Les_Nameks`** (ce nom exact, car toutes les commandes des guides l'utilisent). Ne modifiez pas votre dossier de travail.
2. Copiez dans `C:\livrable\Les_Nameks` : `README.md`, `requirements.txt`, `.gitattributes`, les dossiers `application` et `reseau`.
3. Créez `C:\livrable\Les_Nameks\deploiement_debian` et copiez-y uniquement : `README.md`, `installer.sh`, `init_db.sql`, `migration_stats.sql`, `tester_db.py` et `.env.example`. **Ne copiez jamais `.env`** : il contient le mot de passe MariaDB.
4. Dans les dossiers copiés, supprimez les éventuels dossiers `__pycache__` (ce sont des fichiers générés). Ne copiez pas `.git`, `.venv`, ni de fichiers personnels ou temporaires.
5. Faites un clic droit sur `C:\livrable\Les_Nameks` → **Envoyer vers → Dossier compressé**. Vous obtenez `Les_Nameks.zip`.
6. Ouvrez le ZIP pour vérifier : il doit contenir un seul dossier `Les_Nameks`, avec `README.md` à l'intérieur, et aucun fichier `.env` (seulement `.env.example`).
