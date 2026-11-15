"""Vérifie, en lecture seule, le fichier .env et la connexion à MariaDB.

Lancement depuis la racine du projet : python3 deploiement_debian/tester_db.py
"""

import sys
from pathlib import Path

import pymysql

# On réutilise la lecture du .env écrite dans reseau/serveur.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "reseau"))
from serveur import lire_configuration_db

try:
    configuration = lire_configuration_db()
except (OSError, ValueError) as erreur:
    print(f"Configuration impossible à lire : {erreur}")
    raise SystemExit(1)

try:
    connexion = pymysql.connect(
        host=configuration["DB_HOST"], port=configuration["DB_PORT"],
        user=configuration["DB_USER"], password=configuration["DB_PASSWORD"],
        database=configuration["DB_NAME"], connect_timeout=5, charset="utf8mb4")
    with connexion.cursor() as curseur:
        curseur.execute("SELECT COUNT(*) FROM statistiques")
        nombre_lignes = curseur.fetchone()[0]
    connexion.close()
except pymysql.MySQLError as erreur:
    code = erreur.args[0] if erreur.args else "?"
    if code == 1045:
        print("Accès refusé par MariaDB (erreur 1045). Vérifie DB_USER, DB_PASSWORD et les droits du compte.")
    elif code == 2003:
        print("MariaDB est injoignable (erreur 2003). Vérifie que le service écoute sur DB_HOST et DB_PORT.")
    else:
        print(f"Erreur MariaDB (code {code}). Vérifie le service, la base, la table et les droits du compte.")
    raise SystemExit(1)

print(f"Connexion à MariaDB réussie. Lignes dans statistiques : {nombre_lignes}.")
