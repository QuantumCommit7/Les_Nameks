import math

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import QGraphicsScene, QInputDialog, QMenu

from graphes import Graphes
from fond_carte import FondCarte

class SceneGraphe(QGraphicsScene):
    def __init__(self, graphe: Graphes):
        super().__init__()
        self.graphe = graphe
        self.cercles = {}
        self.elements_noeuds = {}
        self.positions = {}
        self.lignes_aretes = {}
        self.textes_poids = {}
        self.decalage_voies = 8
        self.noeud_en_attente = None
        self.feux = {}
        self.mode_ajout_noeud = False
        self.noeud_a_deplacer = None
        self.deplacement_en_cours = False
        self.fenetre = None
        self.fond = FondCarte()
        self.fond.tuile_prete.connect(self.rafraichir_fond)

    def drawBackground(self, painter, rect):
        self.fond.dessiner(painter, rect)

    def rafraichir_fond(self, rect):
        self.invalidate(rect, QGraphicsScene.SceneLayer.BackgroundLayer)

    def mousePressEvent(self, event):
        position = event.scenePos()
        x = position.x()
        y = position.y()

        item_clique = self.itemAt(position, self.views()[0].transform())

        if event.button() == Qt.MouseButton.RightButton:
            if item_clique in self.cercles:
                nom_clique = self.cercles[item_clique]
                self.afficher_menu_noeud(nom_clique, event.screenPos())
                return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self.fenetre is not None:
            for vehicule in self.fenetre.vehicules:
                if item_clique == vehicule.graphique:
                    self.fenetre.selectionner_vehicule(vehicule)
                    return

        if item_clique in self.cercles:
            nom_clique = self.cercles[item_clique]
            self.noeud_a_deplacer = nom_clique
            self.deplacement_en_cours = False
            return

        if self.mode_ajout_noeud:
            self.creer_noeud(x, y)
            self.mode_ajout_noeud = False


    def mouseMoveEvent(self, event):
        if self.noeud_a_deplacer is None:
            return

        position = event.scenePos()
        self.deplacement_en_cours = True

        self.deplacer_noeud(
            self.noeud_a_deplacer,
            position.x(),
            position.y()
        )

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self.noeud_a_deplacer is not None:
            nom = self.noeud_a_deplacer
            clic_simple = self.deplacement_en_cours == False

            self.noeud_a_deplacer = None
            self.deplacement_en_cours = False

            if clic_simple:
                self.gerer_clic_sur_noeud(nom)

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

    def cle_arete(self, depart, arrivee):
        return tuple(sorted([depart, arrivee]))

    def calculer_decalage_perpendiculaire(self, x1, y1, x2, y2):
        dx = x2 - x1
        dy = y2 - y1

        longueur = math.sqrt(dx * dx + dy * dy)

        if longueur == 0:
            return 0, 0

        decalage_x = -dy / longueur
        decalage_y = dx / longueur

        return (
            decalage_x * self.decalage_voies,
            decalage_y * self.decalage_voies
        )

    def activer_ajout_noeud(self):
        self.mode_ajout_noeud = True
        self.noeud_en_attente = None
        print("Cliquez dans le vide pour placer le nouveau noeud")

    def afficher_menu_noeud(self, nom, position):
        menu = QMenu()
        action_modifier = menu.addAction("Modifier le nom")
        action_supprimer = menu.addAction("Supprimer")

        action = menu.exec(position)

        if action == action_modifier:
            self.modifier_nom_noeud(nom)
        elif action == action_supprimer:
            self.supprimer_noeud(nom)

    def modifier_nom_noeud(self, ancien_nom):
        nouveau_nom, valide = QInputDialog.getText(
            None,
            "Modifier le nom",
            "Nouveau nom :",
            text=ancien_nom
        )

        if valide == False:
            return

        if nouveau_nom == "":
            print("Aucun nom n'a été donné")
            return
        try:
            self.graphe.renommer_noeud(ancien_nom, nouveau_nom)
        except ValueError as erreur:
            print(erreur)
            return

        self.positions[nouveau_nom] = self.positions.pop(ancien_nom)
        self.elements_noeuds[nouveau_nom] = self.elements_noeuds.pop(ancien_nom)

        cercle = self.elements_noeuds[nouveau_nom]["cercle"]
        texte = self.elements_noeuds[nouveau_nom]["texte"]

        x, y = self.positions[nouveau_nom]

        self.cercles[cercle] = nouveau_nom
        self.cercles[texte] = nouveau_nom
        texte.setPlainText(nouveau_nom)
        self.mettre_a_jour_position_noeud(nouveau_nom, x, y)

        self.noeud_en_attente = None
        self.redessiner_toutes_aretes()
        self.mettre_a_jour_feux_graphique()

    def supprimer_noeud(self, nom):
        try:
            self.graphe.supprimer_noeud(nom)
        except ValueError as erreur:
            print(erreur)
            return

        if nom == self.noeud_en_attente:
            self.noeud_en_attente = None

        elements = self.elements_noeuds.pop(nom)
        self.removeItem(elements["cercle"])
        self.removeItem(elements["texte"])
        del self.cercles[elements["cercle"]]
        del self.cercles[elements["texte"]]

        del self.positions[nom]

        self.redessiner_toutes_aretes()
        self.mettre_a_jour_feux_graphique()

    def deplacer_noeud(self, nom, x, y):
        self.positions[nom] = (x, y)
        self.mettre_a_jour_position_noeud(nom, x, y)
        self.repositionner_aretes(nom)
        self.mettre_a_jour_feux_graphique()

        if self.fenetre is not None:
            self.fenetre.mettre_a_jour_positions_vehicules()
            self.fenetre.mettre_a_jour_feux()


    def mettre_a_jour_position_noeud(self, nom, x, y):
        elements = self.elements_noeuds[nom]
        cercle = elements["cercle"]
        texte = elements["texte"]

        cercle.setRect(
            x - 15,
            y - 15,
            30,
            30
        )

        largeur = texte.boundingRect().width()
        hauteur = texte.boundingRect().height()
        texte.setPos(
            x - largeur / 2,
            y - hauteur / 2
        )

    def repositionner_aretes(self, nom):
        if nom not in self.graphe.aretes:
            return

        for voisin in self.graphe.aretes[nom]:
            self.dessiner_arete(nom, voisin)

    def redessiner_toutes_aretes(self):

       for cle in self.lignes_aretes:
            for ligne in self.lignes_aretes[cle]:
                self.removeItem(ligne)

       for cle in self.textes_poids:
            self.removeItem(self.textes_poids[cle])

       self.lignes_aretes = {}
       self.textes_poids = {}

       for depart in self.graphe.aretes:
            for arrivee in self.graphe.aretes[depart]:
                if depart < arrivee:
                    self.dessiner_arete(depart, arrivee)

    def mettre_a_jour_feux_graphique(self):
        anciens_feux = self.feux
        self.feux = {}

        for noeud in anciens_feux:
            for voisin in anciens_feux[noeud]:
                self.removeItem(anciens_feux[noeud][voisin]["graphique"])

        for noeud in self.graphe.noeuds:
            if isinstance(self.graphe.noeuds[noeud], dict):
                groupes = self.graphe.noeuds[noeud]["phases"]
                self.dessiner_feu(noeud, groupes)


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

        self.dessiner_noeud(nom, x, y)

    def dessiner_noeud(self, nom, x, y):
        cercle = self.addEllipse(
            x - 15,
            y - 15,
            30,
            30)
        cercle.setBrush(QBrush(QColor("lightblue")))
        cercle.setZValue(2)
        self.cercles[cercle] = nom

        self.positions[nom] = (x, y)

        texte = self.addText(nom)
        texte.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        texte.setZValue(3)
        self.cercles[texte] = nom

        largeur = texte.boundingRect().width()
        hauteur = texte.boundingRect().height()

        texte.setPos(
            x - largeur / 2,
            y - hauteur / 2
        )

        self.elements_noeuds[nom] = {
            "cercle": cercle,
            "texte": texte
        }

    def dessiner_arete(self, depart, arrivee):
        cle = self.cle_arete(depart, arrivee)
        x1, y1 = self.positions[depart]
        x2, y2 = self.positions[arrivee]

        rayon = 15

        dx = x2 - x1
        dy = y2 - y1

        distance = (dx ** 2 + dy ** 2) ** 0.5

        if distance == 0:
            return

        dx_norm = dx / distance
        dy_norm = dy / distance

        x1_bord = x1 + dx_norm * rayon
        y1_bord = y1 + dy_norm * rayon

        x2_bord = x2 - dx_norm * rayon
        y2_bord = y2 - dy_norm * rayon

        decalage_x, decalage_y = self.calculer_decalage_perpendiculaire(
            x1,
            y1,
            x2,
            y2
        )

        if cle in self.lignes_aretes:

            self.lignes_aretes[cle][0].setLine(
                x1_bord + decalage_x,
                y1_bord + decalage_y,
                x2_bord + decalage_x,
                y2_bord + decalage_y
            )
            self.lignes_aretes[cle][1].setLine(
                x1_bord - decalage_x,
                y1_bord - decalage_y,
                x2_bord - decalage_x,
                y2_bord - decalage_y
            )
        else:
            ligne_1 = self.addLine(
                x1_bord + decalage_x,
                y1_bord + decalage_y,
                x2_bord + decalage_x,
                y2_bord + decalage_y
            )
            ligne_2 = self.addLine(
                x1_bord - decalage_x,
                y1_bord - decalage_y,
                x2_bord - decalage_x,
                y2_bord - decalage_y
            )
            ligne_1.setZValue(1)
            ligne_2.setZValue(1)
            self.lignes_aretes[cle] = [ligne_1, ligne_2]

        poids = self.graphe.aretes[depart][arrivee]
        milieu_x = (x1 + x2) / 2
        milieu_y = (y1 + y2) / 2

        if cle in self.textes_poids:
            texte_poids = self.textes_poids[cle]
            texte_poids.setPlainText(str(poids))
        else:
            texte_poids = self.addText(str(poids))
            texte_poids.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            texte_poids.setZValue(4)
            self.textes_poids[cle] = texte_poids

        largeur = texte_poids.boundingRect().width()
        hauteur = texte_poids.boundingRect().height()

        texte_poids.setPos(
            milieu_x - largeur / 2,
            milieu_y - hauteur / 2
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

