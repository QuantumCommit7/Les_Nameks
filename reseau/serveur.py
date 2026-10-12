import socket
import threading


ADRESSE_ECOUTE = "0.0.0.0"
PORT = 5000


def gerer_client(connexion, adresse):
    """Reçoit et affiche le message d'un client, puis ferme sa connexion."""
    with connexion:
        print(f"Client connecté : {adresse[0]}:{adresse[1]}")

        # Le client ferme son côté écriture après l'envoi du message.
        with connexion.makefile("r", encoding="utf-8") as flux:
            message = flux.read()

        print(f"Message reçu de {adresse[0]} : {message}")


try:
    # Le serveur reste en écoute et crée un thread pour chaque client.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as serveur:
        serveur.bind((ADRESSE_ECOUTE, PORT))
        serveur.listen()
        print(f"Serveur en écoute sur {ADRESSE_ECOUTE}:{PORT}...")

        while True:
            connexion, adresse = serveur.accept()
            thread = threading.Thread(
                target=gerer_client,
                args=(connexion, adresse),
                daemon=True
            )
            thread.start()
except KeyboardInterrupt:
    print("\nArrêt du serveur demandé.")
