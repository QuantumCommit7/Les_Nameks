"""Serveur TCP (Debian) : reçoit les relevés JSON et les enregistre dans MariaDB.

Lancement depuis la racine du projet : python3 reseau/serveur.py

Parcours d'un relevé : accept() -> thread gerer_client -> recevoir_message
-> json.loads -> verifier_statistiques -> enregistrer_statistiques (INSERT).
"""

import json
import math
import socket
import threading
from pathlib import Path

import pymysql

ADRESSE_ECOUTE = "0.0.0.0"  # écouter sur toutes les interfaces réseau de la VM
PORT = 5000
TAILLE_MAX_MESSAGE = 64 * 1024  # 64 Kio : protège le serveur contre un message énorme
FICHIER_ENV = Path(__file__).resolve().parent.parent / "deploiement_debian" / ".env"

CHAMPS_ENTIERS = ("vehicules_actifs", "vehicules_arrives", "vehicules_prioritaires",
                  "vehicules_attente_feu", "vehicules_bouchon")


def lire_configuration_db():
    """Lit le fichier .env (une ligne CLE=VALEUR par paramètre)."""
    configuration = {}
    with FICHIER_ENV.open(encoding="utf-8") as fichier:
        for ligne in fichier:
            ligne = ligne.strip()
            if ligne and not ligne.startswith("#") and "=" in ligne:
                cle, valeur = ligne.split("=", 1)
                configuration[cle.strip()] = valeur.strip().strip("\"'")  # retire les guillemets éventuels
    for champ in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"):
        if not configuration.get(champ):
            raise ValueError(f"{champ} manque ou est vide dans .env")
    configuration["DB_PORT"] = int(configuration["DB_PORT"])
    return configuration


def recevoir_message(connexion):
    """Lit jusqu'au saut de ligne (ou jusqu'à la fermeture par le client)."""
    donnees = b""
    # TCP peut découper un message en plusieurs morceaux : on lit en boucle.
    while b"\n" not in donnees:
        morceau = connexion.recv(4096)
        if not morceau:
            break  # le client a fermé la connexion
        donnees += morceau
        if len(donnees) > TAILLE_MAX_MESSAGE:
            raise ValueError("message trop long (64 Kio maximum)")
    return donnees.split(b"\n")[0].decode("utf-8").strip()


def verifier_statistiques(donnees):
    """Renvoie un message d'erreur, ou None si le relevé est correct."""
    for champ in CHAMPS_ENTIERS:
        valeur = donnees.get(champ)
        # type(...) is int refuse aussi True/False.
        if type(valeur) is not int or valeur < 0:
            return f"{champ} doit être un entier positif ou nul"
    temps = donnees.get("temps_moyen_trajet")
    # 0 <= temps < infini refuse les négatifs, l'infini et NaN (« pas un nombre »).
    if type(temps) not in (int, float) or not 0 <= temps < math.inf:
        return "temps_moyen_trajet doit être un nombre positif ou nul"
    return None


def enregistrer_statistiques(donnees, configuration):
    """Ouvre une connexion MariaDB, insère le relevé, puis ferme la connexion."""
    connexion_db = None
    try:
        connexion_db = pymysql.connect(
            host=configuration["DB_HOST"], port=configuration["DB_PORT"],
            user=configuration["DB_USER"], password=configuration["DB_PASSWORD"],
            database=configuration["DB_NAME"], connect_timeout=5, charset="utf8mb4")
        with connexion_db.cursor() as curseur:
            # Requête paramétrée : PyMySQL remplace les %s par les valeurs de façon sûre.
            # On ne colle jamais les données reçues dans le texte SQL (injection SQL).
            curseur.execute(
                """INSERT INTO statistiques
                   (vehicules_actifs, vehicules_arrives, vehicules_prioritaires,
                    temps_moyen_trajet, vehicules_attente_feu, vehicules_bouchon)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (donnees["vehicules_actifs"], donnees["vehicules_arrives"],
                 donnees["vehicules_prioritaires"], donnees["temps_moyen_trajet"],
                 donnees["vehicules_attente_feu"], donnees["vehicules_bouchon"]))
        connexion_db.commit()  # valide l'insertion
        print("Statistiques enregistrées dans MariaDB.")
    except pymysql.MySQLError as erreur:
        # On affiche le code d'erreur, jamais le mot de passe.
        print(f"Erreur MariaDB (code {erreur.args[0] if erreur.args else '?'}). "
              "Vérifie le fichier .env, le service et les droits du compte trafic.")
    finally:
        if connexion_db is not None:
            connexion_db.close()


def gerer_client(connexion, adresse, configuration):
    """Traite un client (dans son propre thread), puis ferme sa connexion."""
    ip = adresse[0]
    with connexion:
        print(f"Client connecté : {ip}")
        connexion.settimeout(10)  # un client muet ne bloque pas ce thread indéfiniment
        try:
            message = recevoir_message(connexion)
        except (ValueError, OSError) as erreur:
            print(f"Message illisible reçu de {ip} : {erreur}")
            return

    try:
        donnees = json.loads(message)  # texte JSON -> dictionnaire Python
    except ValueError:
        print(f"Message texte reçu de {ip} : {message}")  # ex. : test avec client.py
        return
    if not isinstance(donnees, dict) or donnees.get("type") != "statistiques":
        print(f"Message reçu de {ip} : {message}")
        return
    erreur = verifier_statistiques(donnees)
    if erreur:
        print(f"Statistiques invalides de {ip} : {erreur}.")
        return
    enregistrer_statistiques(donnees, configuration)


def main():
    # On lit la configuration dès le démarrage : sans .env valide, inutile de continuer.
    try:
        configuration = lire_configuration_db()
    except (OSError, ValueError) as erreur:
        print(f"Configuration MariaDB impossible à lire ({FICHIER_ENV}) : {erreur}")
        return

    # AF_INET = IPv4, SOCK_STREAM = TCP.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as serveur:
        try:
            serveur.bind((ADRESSE_ECOUTE, PORT))
        except OSError:
            print(f"Impossible de démarrer le serveur TCP : le port {PORT} est peut-être déjà utilisé.")
            return
        serveur.listen()
        print(f"Serveur en écoute sur {ADRESSE_ECOUTE}:{PORT}...")
        while True:
            connexion, adresse = serveur.accept()  # attend le prochain client
            # Un thread par client : l'écoute continue pendant le traitement.
            threading.Thread(target=gerer_client, args=(connexion, adresse, configuration),
                             daemon=True).start()


# main() ne s'exécute que si on lance ce fichier directement (pas lors d'un import).
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:  # Ctrl+C
        print("\nArrêt du serveur demandé.")
