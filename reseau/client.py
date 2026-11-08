import os
import socket
import sys


# Cette variable PowerShell permet d'adapter le client à l'adresse de la VM.
ADRESSE_SERVEUR = os.environ.get("NAMEKS_SERVER_HOST", "").strip() or "10.128.238.191"
PORT = 5000


def envoyer_message(message, timeout=5):
    """Envoie une ligne UTF-8 au serveur puis ferme le côté écriture.

    ``timeout`` borne le temps d'établissement de la connexion TCP.
    """
    with socket.create_connection(
        (ADRESSE_SERVEUR, PORT),
        timeout=timeout
    ) as client:
        client.sendall((message.rstrip("\r\n") + "\n").encode("utf-8"))
        client.shutdown(socket.SHUT_WR)


def main():
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


if __name__ == "__main__":
    main()
