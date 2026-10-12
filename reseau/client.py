import socket
import sys


ADRESSE_SERVEUR = "10.128.238.191"
PORT = 5000
MESSAGE = "Bonjour depuis Windows !"


try:
    # Le context manager ferme la socket, même si une erreur survient.
    with socket.create_connection((ADRESSE_SERVEUR, PORT), timeout=5) as client:
        client.sendall(MESSAGE.encode("utf-8"))
        # Signale au serveur que tout le message a été envoyé.
        client.shutdown(socket.SHUT_WR)

    print("Message envoyé avec succès.")
except OSError as erreur:
    print(
        f"Connexion impossible à {ADRESSE_SERVEUR}:{PORT}. "
        f"Vérifiez que le serveur est lancé et que le port {PORT} est accessible. "
        f"Détail : {erreur}"
    )
    sys.exit(1)
