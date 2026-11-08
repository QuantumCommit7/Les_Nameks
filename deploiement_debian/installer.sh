#!/usr/bin/env bash

set -euo pipefail

if ! command -v apt-get >/dev/null 2>&1; then
    echo "Erreur : apt-get est introuvable. Ce script est prévu pour Debian ou un système compatible avec apt." >&2
    exit 1
fi

if [[ ! -r /etc/os-release ]]; then
    echo "Erreur : impossible d'identifier le système avec /etc/os-release." >&2
    exit 1
fi

# /etc/os-release définit ID et parfois ID_LIKE pour les distributions dérivées.
. /etc/os-release
if [[ " ${ID:-} ${ID_LIKE:-} " != *debian* && " ${ID:-} ${ID_LIKE:-} " != *ubuntu* ]]; then
    echo "Erreur : ce script est prévu pour Debian ou une distribution compatible avec Debian." >&2
    exit 1
fi

# Utilise sudo si le script n'est pas déjà lancé en tant que root.
if [[ "$(id -u)" -eq 0 ]]; then
    SUDO=()
elif command -v sudo >/dev/null 2>&1; then
    SUDO=(sudo)
else
    echo "Erreur : lance ce script en tant que root ou installe sudo." >&2
    exit 1
fi

echo "Étape 1/3 : actualisation de la liste des paquets..."
"${SUDO[@]}" apt-get update

echo "Étape 2/3 : installation de MariaDB, PyMySQL et du support des environnements virtuels Python..."
"${SUDO[@]}" apt-get install -y mariadb-server python3-pymysql python3-venv

echo "Étape 3/3 : activation et démarrage de MariaDB..."
"${SUDO[@]}" systemctl enable --now mariadb

if "${SUDO[@]}" systemctl is-active --quiet mariadb; then
    echo "MariaDB est actif."
else
    echo "Erreur : MariaDB n'est pas actif. Consulte son état avec : sudo systemctl status mariadb --no-pager" >&2
    exit 1
fi

echo "Étapes suivantes : depuis ce dossier, exécute 'sudo mariadb < init_db.sql', puis suis README.md pour créer le compte trafic et configurer .env."
