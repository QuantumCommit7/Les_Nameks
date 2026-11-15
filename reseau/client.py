"""Client TCP : envoie un message texte (ici un relevé JSON) au serveur Debian.

Utilisé par interface.py via ``envoyer_message``. Peut aussi être lancé seul
(``python reseau\\client.py``) pour tester la connexion avec un message texte.
"""

import os
import socket
import sys


# Cette variable PowerShell permet d'adapter le client à l'adresse de la VM.
# Si NAMEKS_SERVER_HOST n'est pas définie (ou vide), on garde l'adresse historique.
ADRESSE_SERVEUR = os.environ.get("NAMEKS_SERVER_HOST", "").strip() or "10.128.238.191"
PORT = 5000


def envoyer_message(message, timeout=5):
    """Envoie une ligne UTF-8 au serveur puis ferme le côté écriture.

    ``timeout`` borne le temps d'établissement de la connexion TCP.
    """
    # create_connection ouvre la socket TCP et se connecte au serveur.
    # Le bloc « with » garantit la fermeture de la socket à la fin.
    with socket.create_connection(
        (ADRESSE_SERVEUR, PORT),
        timeout=timeout
    ) as client:
        # Protocole : un seul message par connexion, terminé par "\n".
        # On retire d'éventuels sauts de ligne existants pour n'en garder qu'un.
        # encode("utf-8") transforme le texte en octets, seul format envoyable.
        client.sendall((message.rstrip("\r\n") + "\n").encode("utf-8"))
        # Signale au serveur qu'on n'enverra plus rien.
        client.shutdown(socket.SHUT_WR)


def main():
    """Petit test manuel : demande un texte et l'envoie au serveur."""
    message_par_defaut = "Bonjour depuis Windows !"
    message = input(f"Message à envoyer [{message_par_defaut}] : ").strip()
    if not message:
        message = message_par_defaut

    try:
        envoyer_message(message)
        print("Message envoyé avec succès.")
    except OSError as erreur:
        print(
            f"Connexion impossible à {ADRESSE_SERVEUR}:{PORT}. "
            f"Vérifiez que le serveur est lancé et que le port {PORT} est accessible. "
            f"Détail : {erreur}"
        )
        sys.exit(1)


# main() ne s'exécute que si on lance ce fichier directement,
# pas quand interface.py l'importe.
if __name__ == "__main__":
    main()
