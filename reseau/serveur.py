"""Serveur TCP qui valide les relevés JSON et les enregistre dans MariaDB."""

import json
import math
import socket
import threading
from pathlib import Path


ADRESSE_ECOUTE = "0.0.0.0"
PORT = 5000
TAILLE_MAX_MESSAGE = 64 * 1024  # 64 Kio
FICHIER_ENV = Path(__file__).resolve().parent.parent / "deploiement_debian" / ".env"


def lire_configuration_db():
    """Lit les paramètres MariaDB depuis deploiement_debian/.env."""
    configuration = {}

    with FICHIER_ENV.open("r", encoding="utf-8") as fichier:
        for numero, ligne in enumerate(fichier, start=1):
            ligne = ligne.strip()
            if not ligne or ligne.startswith("#"):
                continue
            if "=" not in ligne:
                raise ValueError(f"Ligne {numero} invalide dans le fichier .env.")

            cle, valeur = ligne.split("=", maxsplit=1)
            cle = cle.strip()
            valeur = valeur.strip()
            if len(valeur) >= 2 and valeur[0] == valeur[-1] and valeur[0] in "\"'":
                valeur = valeur[1:-1]
            configuration[cle] = valeur

    champs_requis = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")
    if any(not configuration.get(champ) for champ in champs_requis):
        raise ValueError("Le fichier .env est incomplet ou DB_PASSWORD est vide.")

    try:
        configuration["DB_PORT"] = int(configuration["DB_PORT"])
    except ValueError as erreur:
        raise ValueError("DB_PORT dans le fichier .env doit être un entier.") from erreur

    return configuration


def recevoir_message(connexion):
    """Lit au plus un message, jusqu'au saut de ligne ou à la fermeture du client.

    Retourne le texte UTF-8 et indique si le message était terminé par une
    nouvelle ligne, exigée pour accepter un relevé de statistiques.
    """
    donnees = bytearray()

    while b"\n" not in donnees:
        # TCP peut découper une ligne JSON en plusieurs blocs reçus.
        if len(donnees) > TAILLE_MAX_MESSAGE:
            raise ValueError("le message dépasse la taille maximale de 64 Kio")

        taille_restante = TAILLE_MAX_MESSAGE + 1 - len(donnees)
        bloc = connexion.recv(min(4096, taille_restante))
        if not bloc:
            break
        donnees.extend(bloc)

    termine_par_ligne = b"\n" in donnees
    if termine_par_ligne:
        message, reste = donnees.split(b"\n", maxsplit=1)
        if len(message) > TAILLE_MAX_MESSAGE:
            raise ValueError("le message dépasse la taille maximale de 64 Kio")
        if reste.strip(b" \t\r"):
            raise ValueError("un seul message est accepté par connexion")
    else:
        message = bytes(donnees)
        if len(message) > TAILLE_MAX_MESSAGE:
            raise ValueError("le message dépasse la taille maximale de 64 Kio")

    return message.decode("utf-8").rstrip("\r"), termine_par_ligne


def enregistrer_statistiques(donnees):
    """Insère un relevé en utilisant une connexion MariaDB propre au client."""
    connexion_db = None

    try:
        configuration = lire_configuration_db()
        import pymysql

        connexion_db = pymysql.connect(
            host=configuration["DB_HOST"],
            port=configuration["DB_PORT"],
            user=configuration["DB_USER"],
            password=configuration["DB_PASSWORD"],
            database=configuration["DB_NAME"],
            connect_timeout=5,
            charset="utf8mb4",
        )

        with connexion_db.cursor() as curseur:
            curseur.execute(
                """INSERT INTO statistiques
                   (vehicules_actifs, vehicules_arrives, vehicules_prioritaires,
                    temps_moyen_trajet, vehicules_attente_feu, vehicules_bouchon)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (
                    donnees["vehicules_actifs"],
                    donnees["vehicules_arrives"],
                    donnees["vehicules_prioritaires"],
                    donnees["temps_moyen_trajet"],
                    donnees["vehicules_attente_feu"],
                    donnees["vehicules_bouchon"],
                ),
            )
        # Confirmer l'insertion avant de fermer la connexion MariaDB.
        connexion_db.commit()
        print("Statistiques enregistrées dans MariaDB.")
    except ImportError:
        print("Erreur : PyMySQL n'est pas installé. Installe-le avec : sudo apt-get install -y python3-pymysql")
    except Exception as erreur:
        code = erreur.args[0] if erreur.args and isinstance(erreur.args[0], int) else "inconnu"
        print(
            f"Erreur MariaDB ({type(erreur).__name__}, code {code}). "
            "Vérifie le fichier .env, le service et les droits du compte trafic."
        )
        if connexion_db is not None:
            try:
                connexion_db.rollback()
            except Exception:
                pass
    finally:
        if connexion_db is not None:
            try:
                connexion_db.close()
            except Exception:
                print("Erreur lors de la fermeture de la connexion MariaDB.")


def traiter_message(message, adresse, termine_par_ligne):
    """Enregistre uniquement les objets JSON de type statistiques."""
    try:
        donnees = json.loads(message)
    except json.JSONDecodeError:
        if message.lstrip().startswith(("{", "[")):
            print(f"JSON invalide reçu de {adresse[0]}.")
        else:
            print(f"Message texte reçu de {adresse[0]} : {message}")
        return

    if not isinstance(donnees, dict) or donnees.get("type") != "statistiques":
        print(f"Message reçu de {adresse[0]} : {message}")
        return

    # Le saut de ligne marque la fin du message selon le protocole du client.
    if not termine_par_ligne:
        print(f"Statistiques invalides de {adresse[0]} : le JSON doit se terminer par un saut de ligne.")
        return

    champs_entiers = (
        "vehicules_actifs",
        "vehicules_arrives",
        "vehicules_prioritaires",
        "vehicules_attente_feu",
        "vehicules_bouchon",
    )
    for champ in champs_entiers:
        valeur = donnees.get(champ)
        if type(valeur) is not int or valeur < 0:
            print(f"Statistiques invalides de {adresse[0]} : {champ} doit être un entier positif ou nul.")
            return

    temps_moyen = donnees.get("temps_moyen_trajet")
    if isinstance(temps_moyen, bool) or not isinstance(temps_moyen, (int, float)):
        print(f"Statistiques invalides de {adresse[0]} : temps_moyen_trajet doit être un nombre fini positif ou nul.")
        return
    try:
        temps_valide = math.isfinite(temps_moyen) and temps_moyen >= 0
    except (OverflowError, TypeError):
        temps_valide = False
    if not temps_valide:
        print(f"Statistiques invalides de {adresse[0]} : temps_moyen_trajet doit être un nombre fini positif ou nul.")
        return

    enregistrer_statistiques(donnees)


def gerer_client(connexion, adresse):
    """Traite une connexion cliente puis la ferme, même si le message est invalide."""
    with connexion:
        print(f"Client connecté : {adresse[0]}:{adresse[1]}")
        try:
            message, termine_par_ligne = recevoir_message(connexion)
            traiter_message(message, adresse, termine_par_ligne)
        except UnicodeDecodeError:
            print(f"Message reçu de {adresse[0]} non valide : le texte doit être en UTF-8.")
        except ValueError as erreur:
            print(f"Message invalide reçu de {adresse[0]} : {erreur}.")
        except OSError as erreur:
            print(f"Erreur réseau avec {adresse[0]} ({type(erreur).__name__}).")
        except Exception as erreur:
            print(f"Erreur inattendue pour le client {adresse[0]} ({type(erreur).__name__}).")


try:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as serveur:
        serveur.bind((ADRESSE_ECOUTE, PORT))
        serveur.listen()
        print(f"Serveur en écoute sur {ADRESSE_ECOUTE}:{PORT}...")

        while True:
            try:
                connexion, adresse = serveur.accept()
            except OSError as erreur:
                print(f"Erreur réseau pendant l'écoute ({type(erreur).__name__}). Arrêt du serveur.")
                break

            # Un thread traite cette connexion pendant que l'écoute continue.
            thread = threading.Thread(
                target=gerer_client,
                args=(connexion, adresse),
                daemon=True,
            )
            thread.start()
except KeyboardInterrupt:
    print("\nArrêt du serveur demandé.")
except OSError as erreur:
    print(f"Impossible de démarrer le serveur TCP ({type(erreur).__name__}).")
