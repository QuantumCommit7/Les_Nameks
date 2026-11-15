"""Données fixes utilisées par le bouton « Graphe de test »."""

# Nombre de véhicules maintenus en permanence sur le réseau selon la densité.
# Quand un véhicule arrive, un autre est créé pour garder ce nombre.
DENSITES_TEST = {
    "Aucun": 0,
    "Faible": 5,
    "Moyen": 12,
    "Fort": 20
}

# Position (x, y) de chaque nœud dans la scène, en pixels.
# L'axe y descend vers le bas, comme toujours en Qt.
NOEUDS_TEST = {
    "A": (80, 90),
    "B": (220, 60),
    "C": (370, 120),
    "D": (530, 70),
    "E": (700, 140),
    "F": (130, 230),
    "G": (280, 210),
    "H": (450, 240),
    "I": (630, 230),
    "J": (820, 260),
    "K": (90, 390),
    "L": (240, 360),
    "M": (390, 420),
    "N": (560, 360),
    "O": (740, 410),
    "P": (180, 540),
    "Q": (350, 560),
    "R": (530, 520),
    "S": (700, 570),
    "T": (860, 500),
    "U": (40, 260),
    "V": (315, 40),
    "W": (470, 610),
    "X": (610, 120),
    "Y": (790, 80),
    "Z": (910, 380)
}

# Routes : (nœud 1, nœud 2, distance en mètres). Dijkstra cherche le chemin
# le plus court en mètres (la distance n'est pas liée à la longueur dessinée).
ARETES_TEST = [
    ("A", "B", 500),
    ("A", "F", 600),
    ("A", "U", 800),
    ("B", "C", 600),
    ("B", "G", 500),
    ("B", "V", 400),
    ("C", "D", 800),
    ("C", "G", 300),
    ("C", "H", 400),
    ("C", "V", 500),
    ("D", "E", 700),
    ("D", "X", 400),
    ("E", "X", 300),
    ("E", "Y", 400),
    ("F", "U", 300),
    ("F", "G", 400),
    ("F", "L", 500),
    ("G", "H", 400),
    ("H", "I", 500),
    ("H", "N", 600),
    ("I", "X", 400),
    ("I", "J", 600),
    ("I", "N", 400),
    ("I", "O", 600),
    ("J", "Y", 500),
    ("J", "Z", 600),
    ("K", "U", 500),
    ("K", "L", 400),
    ("K", "P", 500),
    ("L", "M", 500),
    ("L", "P", 400),
    ("M", "N", 500),
    ("M", "Q", 600),
    ("M", "R", 500),
    ("N", "R", 400),
    ("O", "S", 500),
    ("O", "T", 700),
    ("O", "Z", 500),
    ("P", "Q", 400),
    ("Q", "R", 400),
    ("Q", "W", 500),
    ("R", "S", 500),
    ("R", "W", 400),
    ("S", "T", 500),
    ("S", "W", 600),
    ("T", "Z", 400)
]

# Carrefours équipés d'un feu. Chacun a exactement 4 routes, condition
# imposée par FenetrePrincipale.trouver_groupes().
FEUX_TEST = ["F", "G", "H", "L", "M", "N", "O"]
