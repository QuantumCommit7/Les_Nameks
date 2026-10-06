import sys
import math
from graphes import Graphes
from PyQt6.QtWidgets import QApplication, QInputDialog, QMainWindow, QGraphicsScene, QGraphicsView, QPushButton, QWidget, QVBoxLayout, QGraphicsEllipseItem
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QBrush, QColor
from vehicule import Vehicule
import random


class SceneGraphe(QGraphicsScene):
    def __init__(self, graphe: Graphes):
        super().__init__()
        self.graphe = graphe
        self.cercles = {}
        self.noeud_en_attente = None
        self.feux = {}

    def mousePressEvent(self, event):
        position = event.scenePos()
        x = position.x()
        y = position.y()

        item_clique = self.itemAt(position, self.views()[0].transform())

        if item_clique in self.cercles:
            nom_clique = self.cercles[item_clique]
            self.gerer_clic_sur_noeud(nom_clique)
            return

        self.creer_noeud(x, y)

    def gerer_clic_sur_noeud(self, nom):
        if self.noeud_en_attente is None:
            self.noeud_en_attente = nom
            print(f"{nom} sélectionné comme départ, cliquez sur le nœud d'arrivée")
            return

        depart = self.noeud_en_attente
        arrivee = nom
        self.noeud_en_attente = None

        if depart == arrivee:
            print("impossible de relier un nœud à lui-même")
            return

        poids, valide = QInputDialog.getDouble(
            None,
            "Poids de l'arête",
            "Poids :"
        )

        if valide == False:
            return

        if poids <= 0:
            print("Impossible d'avoir une ponderation negative")
            return

        self.graphe.ajouter_arete(depart, arrivee, poids)
        self.dessiner_arete(depart, arrivee)

        print(self.graphe.aretes)

    def creer_noeud(self, x, y):
        nom, valide = QInputDialog.getText(
            None,
            "Nouveau nœud",
            "Nom du nœud :"
        )

        if valide == False:
            return

        if nom == "":
            print("Aucun nom n'a été donné")
            return

        try:
            self.graphe.ajouter_noeud(nom)
            print(self.graphe.noeuds)
        except ValueError:
            print(f"le noeud {nom} existe déjà")
            return

        cercle = self.addEllipse(
            x - 15,
            y - 15,
            30,
            30
        )

        cercle.setBrush(QBrush(QColor("lightblue")))
        self.cercles[cercle] = nom

        self.positions = getattr(self, "positions", {})
        self.positions[nom] = (x, y)

        texte = self.addText(nom)
        texte.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.cercles[texte] = nom

        largeur = texte.boundingRect().width()
        hauteur = texte.boundingRect().height()

        texte.setPos(
            x - largeur / 2,
            y - hauteur / 2
        )

    def dessiner_arete(self, depart, arrivee):
        x1, y1 = self.positions[depart]
        x2, y2 = self.positions[arrivee]

        rayon = 15

        dx = x2 - x1
        dy = y2 - y1

        distance = (dx ** 2 + dy ** 2) ** 0.5

        dx_norm = dx / distance
        dy_norm = dy / distance

        x1_bord = x1 + dx_norm * rayon
        y1_bord = y1 + dy_norm * rayon

        x2_bord = x2 - dx_norm * rayon
        y2_bord = y2 - dy_norm * rayon

        self.addLine(
            x1_bord,
            y1_bord,
            x2_bord,
            y2_bord
        )

    def dessiner_feu(self, noeud, groupes):
        x, y = self.positions[noeud]

        self.feux[noeud] = {}

        for groupe in range(2):

            for voisin in groupes[groupe]:

                xv, yv = self.positions[voisin]

                dx = xv - x
                dy = yv - y

                facteur = 0.25

                feu_x = x + dx * facteur
                feu_y = y + dy * facteur

                feu = self.addEllipse(
                    feu_x - 6,
                    feu_y - 6,
                    12,
                    12
                )

                if groupe == 0:
                    feu.setBrush(QBrush(QColor("green")))
                else:
                    feu.setBrush(QBrush(QColor("red")))

                self.feux[noeud][voisin] = {
                    "graphique": feu,
                    "groupe": groupe
                }


class FenetrePrincipale(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Simulateur de trafic")
        self.resize(1000, 700)

        self.graphe = Graphes()
        self.vehicules = []

        self.scene = SceneGraphe(self.graphe)
        self.view = QGraphicsView(self.scene)

        self.feu_vert = True

        self.bouton_vehicule = QPushButton("Créer véhicule")
        self.bouton_vehicule.clicked.connect(self.creer_vehicule)

        self.bouton_feu = QPushButton("Ajouter un feu")
        self.bouton_feu.clicked.connect(self.configurer_feu)

        conteneur = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(self.bouton_vehicule)
        layout.addWidget(self.bouton_feu)
        layout.addWidget(self.view)

        conteneur.setLayout(layout)

        self.setCentralWidget(conteneur)

        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)
        self.timer.start(20)

        self.timer_feux = QTimer()
        self.timer_feux.timeout.connect(self.changer_feux)
        self.timer_feux.start(5000)

    def trouver_groupes(self, noeud):
        routes = list(self.graphe.aretes[noeud].keys())

        x, y = self.scene.positions[noeud]

        directions = []

        for route in routes:
            xr, yr = self.scene.positions[route]

            dx = xr - x
            dy = yr - y

            angle = math.atan2(dy, dx)

            directions.append({
                "nom": route,
                "angle": angle
            })

        directions.sort(key=lambda element: element["angle"])

        groupes = [
            [],
            []
        ]

        if len(directions) == 4:

            # Les routes sont triées autour du carrefour.
            # Deux routes séparées de deux positions sont
            # celles qui sont face à face.

            groupes[0].append(directions[0]["nom"])
            groupes[0].append(directions[2]["nom"])

            groupes[1].append(directions[1]["nom"])
            groupes[1].append(directions[3]["nom"])

        else:
            print("Pour l'instant, le carrefour doit avoir 4 routes")
            return None

        return groupes

    def configurer_feu(self):
        noeud, valide = QInputDialog.getItem(
            self,
            "Ajouter un feu",
            "Choisissez le carrefour :",
            list(self.graphe.noeuds.keys()),
            0,
            False
        )

        if valide == False:
            return

        if noeud not in self.graphe.aretes:
            print("Ce carrefour n'a aucune route")
            return

        routes = list(self.graphe.aretes[noeud].keys())

        if len(routes) != 4:
            print("Pour l'instant, le carrefour doit avoir exactement 4 routes")
            return

        groupes = self.trouver_groupes(noeud)

        if groupes is None:
            return

        # Le premier groupe est vert.
        # Le deuxième groupe est rouge.
        phases = [
            groupes[0],
            groupes[1]
        ]

        self.graphe.definir_feu(noeud, phases)

        self.scene.dessiner_feu(noeud, groupes)

        print(f"Feu ajouté au carrefour {noeud}")
        print(f"Groupe vert : {groupes[0]}")
        print(f"Groupe rouge : {groupes[1]}")

    def mettre_a_jour_feux(self):

        for noeud in self.scene.feux:

            for voisin in self.scene.feux[noeud]:

                feu = self.scene.feux[noeud][voisin]

                graphique = feu["graphique"]
                groupe = feu["groupe"]

                if self.feu_vert:

                    if groupe == 0:
                        graphique.setBrush(
                            QBrush(QColor("green"))
                        )
                    else:
                        graphique.setBrush(
                            QBrush(QColor("red"))
                        )

                else:

                    if groupe == 0:
                        graphique.setBrush(
                            QBrush(QColor("red"))
                        )
                    else:
                        graphique.setBrush(
                            QBrush(QColor("green"))
                        )

            if self.feu_vert:
                self.graphe.changer_phase(noeud, 0)
            else:
                self.graphe.changer_phase(noeud, 1)

    def creer_vehicule(self):
        depart, valide = QInputDialog.getItem(
            self,
            "Départ",
            "Choisissez le départ :",
            list(self.graphe.noeuds.keys()),
            0,
            False
        )

        if valide == False:
            return

        print(f"Départ choisi : {depart}")

        destination, valide = QInputDialog.getItem(
            self,
            "Destination",
            "Choisissez la destination :",
            list(self.graphe.noeuds.keys()),
            0,
            False
        )

        if valide == False:
            return

        print(f"Destination choisie : {destination}")

        vitesse, valide = QInputDialog.getDouble(
            self,
            "Vitesse",
            "Choisissez la vitesse :",
            0.1,
            0.01,
            1.0,
            2
        )

        if valide == False:
            return

        print(f"Vitesse choisie : {vitesse}")

        vehicule = Vehicule(
            self.graphe,
            depart,
            vitesse,
            destination
        )

        self.vehicules.append(vehicule)

        x, y = self.scene.positions[depart]

        voiture_graphique = QGraphicsEllipseItem(
            -7,
            -7,
            14,
            14
        )

        couleur = QColor(
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 255)
        )

        voiture_graphique.setBrush(QBrush(couleur))

        self.scene.addItem(voiture_graphique)

        vehicule.graphique = voiture_graphique

        print(f"Position du véhicule : {x}, {y}")
        print(f"Véhicule créé : {depart} -> {destination}")

    def changer_feux(self):
        self.feu_vert = not self.feu_vert
        self.mettre_a_jour_feux()

    def tick(self):
        vehicules_encore_actifs = []
        for vehicule in self.vehicules:
            if vehicule.avancement < 1:
                x1, y1 = self.scene.positions[vehicule.depart]
                x2, y2 = self.scene.positions[vehicule.arrivee]

                x = x1 + (x2 - x1) * vehicule.avancement
                y = y1 + (y2 - y1) * vehicule.avancement

                vehicule.graphique.setPos(x, y)

            resultat = vehicule.avancer(self.graphe)

            if resultat != "en cours":
                print(resultat)

            if resultat != "arrive":
                vehicules_encore_actifs.append(vehicule)
            else:
                self.scene.removeItem(vehicule.graphique)

        self.vehicules = vehicules_encore_actifs


app = QApplication(sys.argv)

fenetre = FenetrePrincipale()
fenetre.show()

sys.exit(app.exec())