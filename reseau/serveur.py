import socket


ADRESSE_ECOUTE = "0.0.0.0"
PORT = 5000


# Le serveur accepte une seule connexion, puis se termine.
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as serveur:
    serveur.bind((ADRESSE_ECOUTE, PORT))
    serveur.listen(1)
    print(f"Serveur en attente sur le port {PORT}...")

    connexion, adresse_client = serveur.accept()
    with connexion:
        print(f"Client connecté : {adresse_client[0]}:{adresse_client[1]}")

        # Lire jusqu'à la fermeture du côté écriture par le client permet
        # de recevoir le message complet, même s'il arrive en plusieurs morceaux.
        with connexion.makefile("r", encoding="utf-8") as flux:
            message = flux.read()
        print(f"Message reçu : {message}")

print("Connexion terminée.")
