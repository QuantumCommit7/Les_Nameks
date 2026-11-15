"""Client TCP : envoie un message texte (ici un relevé JSON) au serveur Debian.

Utilisé par interface.py. On peut aussi le lancer seul pour tester la connexion :
    python reseau\\client.py
"""

import os
import socket

# Adresse de la VM, réglable dans PowerShell : $env:NAMEKS_SERVER_HOST = "192.168.1.50"
ADRESSE_SERVEUR = os.environ.get("NAMEKS_SERVER_HOST", "").strip() or "10.128.238.191"
PORT = 5000


def envoyer_message(message, timeout=5):
    """Ouvre une connexion, envoie une ligne terminée par "\\n", puis ferme."""
    # « with » ferme la connexion automatiquement à la fin du bloc.
    with socket.create_connection((ADRESSE_SERVEUR, PORT), timeout=timeout) as connexion:
        # encode : texte -> octets, seul format qu'on peut envoyer sur le réseau.
        connexion.sendall((message.strip() + "\n").encode("utf-8"))


if __name__ == "__main__":
    try:
        envoyer_message("Bonjour depuis Windows !")
        print("Message envoyé avec succès.")
    except OSError as erreur:
        print(f"Connexion impossible à {ADRESSE_SERVEUR}:{PORT} : {erreur}")
