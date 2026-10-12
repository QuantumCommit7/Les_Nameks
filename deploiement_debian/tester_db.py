from pathlib import Path


FICHIER_ENV = Path(__file__).with_name(".env")


def lire_configuration(chemin):
    """Lit les quelques paramètres KEY=VALUE du fichier .env."""
    configuration = {}

    with chemin.open("r", encoding="utf-8") as fichier:
        for numero, ligne in enumerate(fichier, start=1):
            ligne = ligne.strip()
            if not ligne or ligne.startswith("#"):
                continue
            if "=" not in ligne:
                raise ValueError(f"Ligne {numero} invalide dans .env : le signe = manque.")

            cle, valeur = ligne.split("=", maxsplit=1)
            cle = cle.strip()
            valeur = valeur.strip()

            # Accepte une valeur entourée d'une paire de guillemets.
            if len(valeur) >= 2 and valeur[0] == valeur[-1] and valeur[0] in "\"'":
                valeur = valeur[1:-1]

            configuration[cle] = valeur

    champs_requis = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")
    manquants = [champ for champ in champs_requis if not configuration.get(champ)]
    if manquants:
        if "DB_PASSWORD" in manquants:
            raise ValueError("DB_PASSWORD est vide dans .env; renseigne-le localement.")
        raise ValueError("Paramètre(s) manquant(s) dans .env : " + ", ".join(manquants))

    try:
        configuration["DB_PORT"] = int(configuration["DB_PORT"])
    except ValueError as erreur:
        raise ValueError("DB_PORT doit être un nombre entier.") from erreur

    return configuration


try:
    configuration = lire_configuration(FICHIER_ENV)
except (OSError, ValueError) as erreur:
    print(f"Configuration impossible à lire : {erreur}")
    raise SystemExit(1)

try:
    import pymysql
except ImportError:
    print("PyMySQL est introuvable. Installe-le sur Debian avec : sudo apt-get install -y python3-pymysql")
    raise SystemExit(1)

connexion = None
try:
    connexion = pymysql.connect(
        host=configuration["DB_HOST"],
        port=configuration["DB_PORT"],
        user=configuration["DB_USER"],
        password=configuration["DB_PASSWORD"],
        database=configuration["DB_NAME"],
        connect_timeout=5,
        charset="utf8mb4",
    )

    with connexion.cursor() as curseur:
        curseur.execute("SELECT COUNT(*) FROM statistiques")
        nombre_lignes = curseur.fetchone()[0]

    print(f"Connexion à MariaDB réussie. Lignes dans statistiques : {nombre_lignes}.")
except pymysql.MySQLError as erreur:
    code = erreur.args[0] if erreur.args and isinstance(erreur.args[0], int) else "inconnu"
    if code == 1045:
        print("Accès refusé par MariaDB (erreur 1045). Vérifie DB_USER, DB_PASSWORD et les droits du compte.")
    elif code == 2003:
        print("MariaDB est injoignable (erreur 2003). Vérifie que le service écoute sur DB_HOST et DB_PORT.")
    else:
        print(f"Erreur MariaDB (code {code}). Vérifie le service, la base, la table et les droits du compte.")
except OSError:
    print("Erreur système pendant la connexion. Vérifie que MariaDB est actif et joignable localement.")
finally:
    if connexion is not None:
        connexion.close()
