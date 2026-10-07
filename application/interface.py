import sys
import math
from graphes import Graphes
from graphe_test import DENSITES_TEST, NOEUDS_TEST, ARETES_TEST, FEUX_TEST
from PyQt6.QtWidgets import QApplication, QInputDialog, QMainWindow, QGraphicsScene, QGraphicsView, QPushButton, QWidget, QVBoxLayout, QHBoxLayout, QGraphicsEllipseItem, QMenu, QMessageBox
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QBrush, QColor
from vehicule import Vehicule
import random


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
            30
        )

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


class FenetrePrincipale(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Simulateur de trafic")
        self.resize(1000, 700)

        self.graphe = Graphes()
        self.vehicules = []
        self.distance_securite = 0.08
        self.distance_laisser_passer = 0.20
        self.decalage_laisser_passer = 2
        self.simulation_active = False
        self.nombre_vehicules_voulu = 0

        self.scene = SceneGraphe(self.graphe)
        self.scene.fenetre = self
        self.view = QGraphicsView(self.scene)

        self.feu_vert = True

        self.bouton_noeud = QPushButton("Ajouter un nœud")
        self.bouton_noeud.clicked.connect(self.scene.activer_ajout_noeud)

        self.bouton_vehicule = QPushButton("Créer véhicule")
        self.bouton_vehicule.clicked.connect(self.creer_vehicule)

        self.bouton_feu = QPushButton("Ajouter un feu")
        self.bouton_feu.clicked.connect(self.configurer_feu)

        self.bouton_graphe_test = QPushButton("Graphe de test")
        self.bouton_graphe_test.clicked.connect(self.creer_graphe_test)

        self.bouton_simulation = QPushButton("Démarrer")
        self.bouton_simulation.clicked.connect(self.demarrer_pause)

        conteneur = QWidget()
        layout = QVBoxLayout()
        layout_boutons = QHBoxLayout()

        layout_boutons.addWidget(self.bouton_noeud)
        layout_boutons.addWidget(self.bouton_vehicule)
        layout_boutons.addWidget(self.bouton_feu)
        layout_boutons.addWidget(self.bouton_graphe_test)
        layout_boutons.addWidget(self.bouton_simulation)

        layout.addLayout(layout_boutons)
        layout.addWidget(self.view)

        conteneur.setLayout(layout)

        self.setCentralWidget(conteneur)

        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)

        self.timer_feux = QTimer()
        self.timer_feux.timeout.connect(self.changer_feux)

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

    def creer_graphe_test(self):
        densite, valide = QInputDialog.getItem(
            self,
            "Densité du trafic",
            "Choisissez la densité :",
            ["Aucun", "Faible", "Moyen", "Fort"],
            0,
            False
        )

        if valide == False:
            return

        self.nombre_vehicules_voulu = DENSITES_TEST[densite]

        self.simulation_active = False
        self.timer.stop()
        self.timer_feux.stop()
        self.bouton_simulation.setText("Démarrer")

        self.graphe = Graphes()
        self.vehicules = []
        self.feu_vert = True

        self.scene.clear()
        self.scene.graphe = self.graphe
        self.scene.cercles = {}
        self.scene.elements_noeuds = {}
        self.scene.positions = {}
        self.scene.lignes_aretes = {}
        self.scene.textes_poids = {}
        self.scene.noeud_en_attente = None
        self.scene.feux = {}
        self.scene.mode_ajout_noeud = False
        self.scene.noeud_a_deplacer = None
        self.scene.deplacement_en_cours = False

        for nom in NOEUDS_TEST:
            x, y = NOEUDS_TEST[nom]
            self.graphe.ajouter_noeud(nom)
            self.scene.dessiner_noeud(nom, x, y)

        for depart, arrivee, poids in ARETES_TEST:
            self.graphe.ajouter_arete(depart, arrivee, poids)
            self.scene.dessiner_arete(depart, arrivee)

        for noeud in FEUX_TEST:
            groupes = self.trouver_groupes(noeud)
            if groupes is not None:
                self.graphe.definir_feu(noeud, groupes)
                self.scene.dessiner_feu(noeud, groupes)

        self.afficher_feux_selon_graphe()

        for i in range(self.nombre_vehicules_voulu):
            self.creer_vehicule_aleatoire()

        print("Graphe de test créé")
        print(f"Véhicules créés : {len(self.vehicules)}")
        print(f"Feux : {FEUX_TEST}")

    def mettre_a_jour_feux(self):

        for noeud in self.scene.feux:

            if self.feu_vert:
                self.graphe.changer_phase(noeud, 0)
            else:
                self.graphe.changer_phase(noeud, 1)

        self.afficher_feux_selon_graphe()

    def afficher_feux_selon_graphe(self):
        for noeud in self.scene.feux:

            phase_active = self.graphe.noeuds[noeud]["phase_active"]

            for voisin in self.scene.feux[noeud]:

                feu = self.scene.feux[noeud][voisin]
                graphique = feu["graphique"]
                groupe = feu["groupe"]

                if groupe == phase_active:
                    graphique.setBrush(
                        QBrush(QColor("green"))
                    )
                else:
                    graphique.setBrush(
                        QBrush(QColor("red"))
                    )

    def ajouter_vehicule(self, depart, destination, vitesse, est_urgent=False):
        if est_urgent:
            vitesse = vitesse * 1.3

            if vitesse > 1.0:
                vitesse = 1.0

        vehicule = Vehicule(
            self.graphe,
            depart,
            vitesse,
            destination,
            est_urgent=est_urgent
        )

        self.vehicules.append(vehicule)

        x, y = self.scene.positions[depart]

        voiture_graphique = QGraphicsEllipseItem(
            -7,
            -7,
            14,
            14
        )

        if est_urgent:
            couleur = QColor("red")
        else:
            couleur = QColor(
                random.randint(0, 255),
                random.randint(0, 255),
                random.randint(0, 255)
            )

        voiture_graphique.setBrush(QBrush(couleur))
        voiture_graphique.setPos(x, y)

        self.scene.addItem(voiture_graphique)

        vehicule.graphique = voiture_graphique

        return vehicule

    def creer_vehicule_aleatoire(self):
        noeuds = list(self.graphe.noeuds.keys())

        if len(noeuds) < 2:
            return None

        depart = random.choice(noeuds)
        destination = random.choice(noeuds)

        while destination == depart:
            destination = random.choice(noeuds)

        vitesse = round(random.uniform(0.05, 0.20), 2)

        return self.ajouter_vehicule(
            depart,
            destination,
            vitesse,
            est_urgent=False
        )

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

        if depart == destination:
            QMessageBox.warning(
                self,
                "Erreur",
                "Le départ et la destination doivent être différents."
            )
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

        type_vehicule, valide = QInputDialog.getItem(
            self,
            "Type de véhicule",
            "Choisissez le type :",
            ["Normal", "Prioritaire"],
            0,
            False
        )

        if valide == False:
            return

        if type_vehicule == "Prioritaire":
            est_urgent = True
        else:
            est_urgent = False

        self.ajouter_vehicule(
            depart,
            destination,
            vitesse,
            est_urgent
        )

        x, y = self.scene.positions[depart]
        print(f"Position du véhicule : {x}, {y}")
        print(f"Véhicule créé : {depart} -> {destination}")

    def changer_feux(self):
        if self.simulation_active == False:
            return

        self.feu_vert = not self.feu_vert
        self.mettre_a_jour_feux()

    def demarrer_pause(self):
        self.simulation_active = not self.simulation_active

        if self.simulation_active:
            self.bouton_simulation.setText("Pause")
            self.timer.start(20)
            self.timer_feux.start(5000)
        else:
            self.bouton_simulation.setText("Démarrer")
            self.timer.stop()
            self.timer_feux.stop()

    def vehicule_ecarte_pour_prioritaire(self, vehicule, vehicule_prioritaire):
        if vehicule.est_urgent:
            return False

        if vehicule_prioritaire.est_urgent == False:
            return False

        meme_depart = vehicule.depart == vehicule_prioritaire.depart
        meme_arrivee = vehicule.arrivee == vehicule_prioritaire.arrivee

        if meme_depart and meme_arrivee:
            if vehicule_prioritaire.avancement < vehicule.avancement:
                distance = vehicule.avancement - vehicule_prioritaire.avancement

                if distance < self.distance_laisser_passer:
                    return True

        return False

    def vehicule_doit_secarter(self, vehicule):
        for autre_vehicule in self.vehicules:
            if autre_vehicule != vehicule:
                if self.vehicule_ecarte_pour_prioritaire(vehicule, autre_vehicule):
                    return True

        return False

    def vehicule_peut_avancer(self, vehicule):
        if self.vehicule_doit_secarter(vehicule):
            return False

        for autre_vehicule in self.vehicules:
            if autre_vehicule != vehicule:

                meme_depart = autre_vehicule.depart == vehicule.depart
                meme_arrivee = autre_vehicule.arrivee == vehicule.arrivee

                if meme_depart and meme_arrivee:
                    if autre_vehicule.avancement > vehicule.avancement:
                        distance = autre_vehicule.avancement - vehicule.avancement

                        if distance < self.distance_securite:
                            if vehicule.est_urgent:
                                if self.vehicule_ecarte_pour_prioritaire(autre_vehicule, vehicule):
                                    continue

                            return False

        return True

    def mettre_a_jour_position_vehicule(self, vehicule):
        x1, y1 = self.scene.positions[vehicule.depart]
        x2, y2 = self.scene.positions[vehicule.arrivee]

        x = x1 + (x2 - x1) * vehicule.avancement
        y = y1 + (y2 - y1) * vehicule.avancement

        decalage_x, decalage_y = self.scene.calculer_decalage_perpendiculaire(
            x1,
            y1,
            x2,
            y2
        )

        x = x + decalage_x
        y = y + decalage_y

        if self.vehicule_doit_secarter(vehicule):
            x = x + decalage_x * self.decalage_laisser_passer
            y = y + decalage_y * self.decalage_laisser_passer

        vehicule.graphique.setPos(x, y)

    def mettre_a_jour_positions_vehicules(self):
        for vehicule in self.vehicules:
            self.mettre_a_jour_position_vehicule(vehicule)

    def tick(self):
        if self.simulation_active == False:
            return

        vehicules_encore_actifs = []
        for vehicule in self.vehicules:
            self.mettre_a_jour_position_vehicule(vehicule)

            if self.vehicule_peut_avancer(vehicule):
                resultat = vehicule.avancer(self.graphe)
                self.afficher_feux_selon_graphe()
            else:
                resultat = "en cours"

            if resultat != "en cours" and resultat != "attends feu":
                print(resultat)

            if resultat != "arrive":
                vehicules_encore_actifs.append(vehicule)
            else:
                self.scene.removeItem(vehicule.graphique)

        self.vehicules = vehicules_encore_actifs

        while self.nombre_vehicules_voulu > 0 and len(self.vehicules) < self.nombre_vehicules_voulu:
            vehicule = self.creer_vehicule_aleatoire()
            if vehicule is None:
                break


app = QApplication(sys.argv)

fenetre = FenetrePrincipale()
fenetre.show()

sys.exit(app.exec())
