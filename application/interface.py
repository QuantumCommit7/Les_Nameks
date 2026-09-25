import sys
from graphes import Graphes
from PyQt6.QtWidgets import QApplication, QInputDialog, QMainWindow, QGraphicsScene, QGraphicsView
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor

class SceneGraphe(QGraphicsScene):
    def __init__(self, graphe: Graphes):
        super().__init__()
        self.graphe = graphe
        self.cercles = {}
        self.noeud_en_attente = None

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

        poids, valide = QInputDialog.getDouble(None, "Poids de l'arête", "Poids :")
        if valide == False:
            return

        if poids <= 0:
            print("Impossible d'avoir une ponderation negative")
            return

        self.graphe.ajouter_arete(depart, arrivee, poids)
        self.dessiner_arete(depart, arrivee)

    def creer_noeud(self, x, y):
        nom, valide = QInputDialog.getText(None, "Nouveau nœud", "Nom du nœud :")
        if valide == False:
            return
        if nom == "":
            print("Aucun nom n'a été donné")
            return
        try:
            self.graphe.ajouter_noeud(nom)
        except ValueError:
            print(f"le noeud {nom} existe déjà")
            return

        cercle = self.addEllipse(x - 15, y - 15, 30, 30)
        cercle.setBrush(QBrush(QColor("lightblue")))
        self.cercles[cercle] = nom

        self.positions = getattr(self, "positions", {})
        self.positions[nom] = (x, y)

        texte = self.addText(nom)
        texte.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.cercles[texte] = nom
        largeur = texte.boundingRect().width()
        hauteur = texte.boundingRect().height()
        texte.setPos(x - largeur / 2, y - hauteur / 2)

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

        self.addLine(x1_bord, y1_bord, x2_bord, y2_bord)

class FenetrePrincipale(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simulateur de trafic")
        self.resize(1000, 700)

        self.graphe = Graphes()
        self.scene = SceneGraphe(self.graphe)
        self.view = QGraphicsView(self.scene)

        self.setCentralWidget(self.view)


app = QApplication(sys.argv)
fenetre = FenetrePrincipale()
fenetre.show()
sys.exit(app.exec())