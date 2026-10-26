import json
import sys
import math
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from reseau.client import envoyer_message

from graphes import Graphes
from graphe_test import DENSITES_TEST, NOEUDS_TEST, ARETES_TEST, FEUX_TEST
from PyQt6.QtWidgets import QApplication, QComboBox, QGridLayout, QGroupBox, QInputDialog, QLabel, QMainWindow, QPushButton, QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QGraphicsRectItem, QMenu, QMessageBox
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QPen
from vue_graphe import VueGraphe
from scene_graphe import SceneGraphe
from vehicule import Vehicule
import random


class FenetrePrincipale(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Simulateur de trafic")
        self.resize(1000, 700)

        self.graphe = Graphes()
        self.vehicules = []
        self.vehicule_selectionne = None
        self.pen_routes_avant_selection = {}
        self.distance_securite = 0.08
        self.distance_laisser_passer = 0.20
        self.decalage_laisser_passer = 2
        self.simulation_active = False
        self.nombre_vehicules_voulu = 0
        self.vehicules_arrives = 0
        self.temps_simulation_actif = 0.0
        self.dernier_instant_actif = None
        self.temps_total_trajets_termines = 0.0
        self.nombre_trajets_termines = 0
        self.verrou_envoi_statistiques = threading.Lock()
        self.gyrophare_vehicules = {}
        self.gyrophare_bleu_actif = True
        self.transitions_feux = {}
        self.couleurs_vehicules_normaux = [
            QColor("#2676b8"),
            QColor("#7b4ab2"),
            QColor("#08a6b8"),
            QColor("#b98500"),
            QColor("#cb6c27"),
        ]

        self.scene = SceneGraphe(self.graphe)
        self.scene.fenetre = self
        self.view = VueGraphe(self.scene)

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
        self.bouton_simulation.setObjectName("boutonSimulation")
        self.bouton_simulation.clicked.connect(self.demarrer_pause)

        self.combo_densite = QComboBox()
        self.combo_densite.addItems(list(DENSITES_TEST.keys()))
        self.combo_densite.setCurrentText("Faible")

        panneau = QWidget()
        panneau.setObjectName("panneauLateral")
        panneau.setFixedWidth(260)
        layout_panneau = QVBoxLayout()
        layout_panneau.setSpacing(10)

        section_simulation = QGroupBox("SIMULATION")
        layout_simulation = QVBoxLayout()
        layout_simulation.addWidget(self.bouton_simulation)
        layout_simulation.addWidget(self.combo_densite)
        layout_simulation.addWidget(self.bouton_graphe_test)
        section_simulation.setLayout(layout_simulation)

        section_vehicules = QGroupBox("VÉHICULES")
        layout_vehicules = QVBoxLayout()
        layout_vehicules.addWidget(self.bouton_vehicule)
        section_vehicules.setLayout(layout_vehicules)

        section_graphe = QGroupBox("ÉDITION DU GRAPHE")
        layout_graphe = QVBoxLayout()
        layout_graphe.addWidget(self.bouton_noeud)
        layout_graphe.addWidget(self.bouton_feu)
        section_graphe.setLayout(layout_graphe)

        section_statistiques = QGroupBox("STATISTIQUES")
        layout_statistiques = QGridLayout()
        self.labels_statistiques = {}
        noms_statistiques = [
            ("vehicules_actifs", "Véhicules actifs"),
            ("vehicules_arrives", "Véhicules arrivés"),
            ("vehicules_prioritaires", "Véhicules prioritaires"),
            ("temps_moyen_trajet", "Temps moyen de trajet"),
            ("vehicules_attente_feu", "En attente au feu rouge"),
            ("vehicules_bouchon", "Bloqués dans un bouchon"),
        ]
        for ligne, (cle, nom) in enumerate(noms_statistiques):
            intitule = QLabel(nom)
            intitule.setStyleSheet("color: #64716e;")
            valeur = QLabel("0")
            valeur.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            valeur.setStyleSheet("font-size: 11pt; font-weight: bold; color: #263238;")
            self.labels_statistiques[cle] = valeur
            layout_statistiques.addWidget(intitule, ligne, 0)
            layout_statistiques.addWidget(valeur, ligne, 1)
        layout_statistiques.setColumnStretch(0, 1)
        section_statistiques.setLayout(layout_statistiques)

        section_legende = QGroupBox("LÉGENDE")
        layout_legende = QVBoxLayout()
        elements_legende = [
            ("#2676b8", "Véhicule normal (palette variée)"),
            ("red", "Véhicule prioritaire"),
            ("green", "Feu vert"),
            ("red", "Feu rouge"),
            ("orange", "Trajet Dijkstra sélectionné"),
        ]
        for couleur, texte in elements_legende:
            ligne_legende = QHBoxLayout()
            pastille = QLabel("●")
            pastille.setStyleSheet(f"color: {couleur}; font-size: 14pt;")
            texte_legende = QLabel(texte)
            texte_legende.setWordWrap(True)
            ligne_legende.addWidget(pastille)
            ligne_legende.addWidget(texte_legende)
            layout_legende.addLayout(ligne_legende)
        section_legende.setLayout(layout_legende)

        layout_panneau.addWidget(section_simulation)
        layout_panneau.addWidget(section_vehicules)
        layout_panneau.addWidget(section_graphe)
        layout_panneau.addWidget(section_statistiques)
        layout_panneau.addWidget(section_legende)
        layout_panneau.addStretch()
        panneau.setLayout(layout_panneau)

        panneau_defilant = QScrollArea()
        panneau_defilant.setWidgetResizable(True)
        panneau_defilant.setFixedWidth(280)
        panneau_defilant.setWidget(panneau)

        conteneur = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(panneau_defilant)
        layout.addWidget(self.view, 1)

        conteneur.setLayout(layout)

        self.setCentralWidget(conteneur)
        self.setMinimumSize(850, 560)
        self.setStyleSheet("""
            QWidget {
                background-color: #f3f6f5;
                color: #263238;
                font-family: "Segoe UI";
                font-size: 10pt;
            }
            QWidget#panneauLateral { background-color: #f3f6f5; }
            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #d5dfdc;
                border-radius: 5px;
                margin-top: 9px;
                padding: 8px;
                font-weight: bold;
                color: #344a46;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
            QPushButton, QComboBox {
                min-height: 30px;
                background-color: #ffffff;
                border: 1px solid #cbd6d2;
                border-radius: 4px;
                padding: 3px 8px;
            }
            QPushButton:hover { background-color: #e8efed; }
            QPushButton#boutonSimulation {
                background-color: #28766a;
                color: white;
                border: none;
                font-weight: bold;
            }
            QPushButton#boutonSimulation:hover { background-color: #206358; }
            QLabel { background-color: transparent; }
            QStatusBar { background-color: #ffffff; color: #344a46; }
        """)
        self.statusBar().showMessage("Simulation en pause")

        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)

        self.timer_feux = QTimer()
        self.timer_feux.timeout.connect(self.changer_feux)

        self.timer_statistiques = QTimer()
        self.timer_statistiques.timeout.connect(self.envoyer_statistiques)

        self.timer_gyrophare = QTimer()
        self.timer_gyrophare.timeout.connect(self.changer_gyrophare)
        self.actualiser_statistiques_interface()

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
        self.statusBar().showMessage(f"Feu ajouté au carrefour {noeud}", 3000)

        print(f"Feu ajouté au carrefour {noeud}")
        print(f"Groupe vert : {groupes[0]}")
        print(f"Groupe rouge : {groupes[1]}")

    def creer_graphe_test(self):
        self.deselectionner_vehicule()

        densite = self.combo_densite.currentText()
        self.nombre_vehicules_voulu = DENSITES_TEST[densite]
        self.vehicules_arrives = 0
        self.temps_simulation_actif = 0.0
        self.dernier_instant_actif = None
        self.temps_total_trajets_termines = 0.0
        self.nombre_trajets_termines = 0

        self.simulation_active = False
        self.timer.stop()
        self.timer_feux.stop()
        self.timer_statistiques.stop()
        self.timer_gyrophare.stop()
        self.gyrophare_vehicules = {}
        self.transitions_feux = {}
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

        self.view.ajuster_au_graphe()
        print("Graphe de test créé")
        print(f"Véhicules créés : {len(self.vehicules)}")
        print(f"Feux : {FEUX_TEST}")
        self.actualiser_statistiques_interface()
        self.statusBar().showMessage("Graphe de test créé", 3000)

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

    def ajouter_vehicule(self, depart, destination, vitesse, est_urgent=False, afficher_erreur=True):
        if est_urgent:
            vitesse = vitesse * 1.3

            if vitesse > 1.0:
                vitesse = 1.0

        try:
            vehicule = Vehicule(
                self.graphe,
                depart,
                vitesse,
                destination,
                est_urgent=est_urgent
            )
        except ValueError as erreur:
            if afficher_erreur:
                QMessageBox.warning(self, "Trajet impossible", str(erreur))
            return None

        vehicule.temps_debut_trajet_actif = self.obtenir_temps_simulation_actif()

        self.vehicules.append(vehicule)

        x, y = self.scene.positions[depart]

        voiture_graphique = QGraphicsRectItem(-9, -5, 18, 10)

        if est_urgent:
            couleur = QColor("black")
            voiture_graphique.setPen(QPen(QColor("#303840"), 1))

            gyro_bleu = QGraphicsRectItem(-4, -3, 4, 6, voiture_graphique)
            couleur_inactive = QColor("#59636d")
            if self.gyrophare_bleu_actif:
                gyro_bleu.setBrush(QBrush(QColor("blue")))
            else:
                gyro_bleu.setBrush(QBrush(couleur_inactive))
            gyro_bleu.setPen(QPen(Qt.PenStyle.NoPen))

            gyro_rouge = QGraphicsRectItem(0, -3, 4, 6, voiture_graphique)
            if self.gyrophare_bleu_actif:
                gyro_rouge.setBrush(QBrush(couleur_inactive))
            else:
                gyro_rouge.setBrush(QBrush(QColor("red")))
            gyro_rouge.setPen(QPen(Qt.PenStyle.NoPen))
        else:
            couleur = random.choice(self.couleurs_vehicules_normaux)

        voiture_graphique.setBrush(QBrush(couleur))
        voiture_graphique.setPos(x, y)

        self.scene.addItem(voiture_graphique)

        vehicule.graphique = voiture_graphique
        self.mettre_a_jour_position_vehicule(vehicule)

        if est_urgent:
            self.gyrophare_vehicules[vehicule] = (gyro_bleu, gyro_rouge)
            if not self.timer_gyrophare.isActive():
                self.timer_gyrophare.start(200)

        return vehicule

    def selectionner_vehicule(self, vehicule):
        if vehicule == self.vehicule_selectionne:
            self.deselectionner_vehicule()
            return

        self.deselectionner_vehicule()
        self.vehicule_selectionne = vehicule

        chemin = vehicule.chemin
        if not isinstance(chemin, (list, tuple)):
            return

        for depart, arrivee in zip(chemin, chemin[1:]):
            cle = self.scene.cle_arete(depart, arrivee)
            for ligne in self.scene.lignes_aretes.get(cle, []):
                self.pen_routes_avant_selection[ligne] = QPen(ligne.pen())
                pen = QPen(ligne.pen())
                pen.setColor(QColor("orange"))
                pen.setWidthF(3.0)
                ligne.setPen(pen)

    def deselectionner_vehicule(self):
        for ligne, pen in self.pen_routes_avant_selection.items():
            ligne.setPen(pen)

        self.pen_routes_avant_selection = {}
        self.vehicule_selectionne = None

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
            est_urgent=False,
            afficher_erreur=False
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

        vehicule = self.ajouter_vehicule(
            depart,
            destination,
            vitesse,
            est_urgent
        )

        if vehicule is None:
            return

        x, y = self.scene.positions[depart]
        print(f"Position du véhicule : {x}, {y}")
        print(f"Véhicule créé : {depart} -> {destination}")
        if est_urgent:
            self.statusBar().showMessage("Véhicule prioritaire créé", 3000)
        else:
            self.statusBar().showMessage("Véhicule créé", 3000)
        self.actualiser_statistiques_interface()

    def changer_feux(self):
        if self.simulation_active == False:
            return

        self.feu_vert = not self.feu_vert
        self.mettre_a_jour_feux()

    def changer_gyrophare(self):
        self.gyrophare_bleu_actif = not self.gyrophare_bleu_actif
        couleur_inactive = QColor("#59636d")

        for gyro_bleu, gyro_rouge in self.gyrophare_vehicules.values():
            if self.gyrophare_bleu_actif:
                gyro_bleu.setBrush(QBrush(QColor("blue")))
                gyro_rouge.setBrush(QBrush(couleur_inactive))
            else:
                gyro_bleu.setBrush(QBrush(couleur_inactive))
                gyro_rouge.setBrush(QBrush(QColor("red")))

    def demarrer_pause(self):
        if self.simulation_active:
            self.actualiser_temps_simulation_actif()
            self.simulation_active = False
            self.bouton_simulation.setText("Démarrer")
            self.timer.stop()
            self.timer_feux.stop()
            self.timer_statistiques.stop()
            self.statusBar().showMessage("Simulation en pause")
        else:
            self.simulation_active = True
            self.dernier_instant_actif = time.monotonic()
            self.bouton_simulation.setText("Pause")
            self.timer.start(20)
            self.timer_feux.start(5000)
            self.timer_statistiques.start(5000)
            self.statusBar().showMessage("Simulation démarrée", 3000)

    def actualiser_temps_simulation_actif(self):
        if self.simulation_active and self.dernier_instant_actif is not None:
            maintenant = time.monotonic()
            self.temps_simulation_actif += maintenant - self.dernier_instant_actif
            self.dernier_instant_actif = maintenant

    def obtenir_temps_simulation_actif(self):
        temps = self.temps_simulation_actif
        if self.simulation_active and self.dernier_instant_actif is not None:
            temps += time.monotonic() - self.dernier_instant_actif
        return temps

    def calculer_temps_moyen_trajet(self):
        if self.nombre_trajets_termines == 0:
            return 0.0
        return self.temps_total_trajets_termines / self.nombre_trajets_termines

    def obtenir_statistiques(self):
        return {
            "type": "statistiques",
            "vehicules_actifs": len(self.vehicules),
            "vehicules_arrives": self.vehicules_arrives,
            "vehicules_prioritaires": sum(
                1 for vehicule in self.vehicules if vehicule.est_urgent
            ),
            "temps_moyen_trajet": self.calculer_temps_moyen_trajet(),
            "vehicules_attente_feu": self.compter_vehicules_attente_feu(),
            "vehicules_bouchon": self.compter_vehicules_bouchon(),
        }

    def actualiser_statistiques_interface(self):
        statistiques = self.obtenir_statistiques()
        self.labels_statistiques["vehicules_actifs"].setText(
            str(statistiques["vehicules_actifs"])
        )
        self.labels_statistiques["vehicules_arrives"].setText(
            str(statistiques["vehicules_arrives"])
        )
        self.labels_statistiques["vehicules_prioritaires"].setText(
            str(statistiques["vehicules_prioritaires"])
        )
        self.labels_statistiques["temps_moyen_trajet"].setText(
            f"{statistiques['temps_moyen_trajet']:.2f} s"
        )
        self.labels_statistiques["vehicules_attente_feu"].setText(
            str(statistiques["vehicules_attente_feu"])
        )
        self.labels_statistiques["vehicules_bouchon"].setText(
            str(statistiques["vehicules_bouchon"])
        )
        return statistiques

    def vehicule_attend_au_feu(self, vehicule):
        return (
            vehicule.avancement >= 1
            and not self.graphe.est_vert(vehicule.arrivee, vehicule.depart)
        )

    def compter_vehicules_attente_feu(self):
        return sum(1 for vehicule in self.vehicules if self.vehicule_attend_au_feu(vehicule))

    def vehicule_bloque_par_un_autre(self, vehicule):
        indice_vehicule = self.vehicules.index(vehicule)

        for indice_autre, autre_vehicule in enumerate(self.vehicules):
            if autre_vehicule == vehicule:
                continue

            meme_depart = autre_vehicule.depart == vehicule.depart
            meme_arrivee = autre_vehicule.arrivee == vehicule.arrivee
            devant = (
                autre_vehicule.avancement > vehicule.avancement
                or (
                    autre_vehicule.avancement == vehicule.avancement
                    and indice_autre < indice_vehicule
                )
            )

            if meme_depart and meme_arrivee and devant:
                x1, y1 = self.scene.positions[vehicule.depart]
                x2, y2 = self.scene.positions[vehicule.arrivee]
                longueur = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

                if longueur == 0:
                    continue

                distance = autre_vehicule.avancement - vehicule.avancement
                marge_pixels = 22 + vehicule.vitesse * (20 / 300) * longueur
                distance_requise = max(self.distance_securite, marge_pixels / longueur)

                feu_rouge_devant = not self.graphe.est_vert(
                    autre_vehicule.arrivee,
                    autre_vehicule.depart
                )
                if feu_rouge_devant:
                    distance_arret = min(28, longueur * 0.5)
                    avancement_ligne_arret = 1 - distance_arret / longueur
                    if autre_vehicule.avancement >= avancement_ligne_arret:
                        distance_requise = max(
                            distance_requise,
                            (distance_arret + marge_pixels) / longueur
                        )

                if distance < distance_requise:
                    if vehicule.est_urgent:
                        if self.vehicule_ecarte_pour_prioritaire(autre_vehicule, vehicule):
                            continue
                    return True

        return False

    def compter_vehicules_bouchon(self):
        nombre = 0
        for vehicule in self.vehicules:
            if self.vehicule_attend_au_feu(vehicule):
                continue
            if self.vehicule_doit_secarter(vehicule):
                continue
            if self.vehicule_bloque_par_un_autre(vehicule):
                nombre += 1
        return nombre

    def envoyer_statistiques(self):
        if self.simulation_active == False:
            return

        statistiques = self.actualiser_statistiques_interface()
        temps_moyen = statistiques["temps_moyen_trajet"]
        vehicules_attente_feu = statistiques["vehicules_attente_feu"]
        vehicules_bouchon = statistiques["vehicules_bouchon"]
        print(
            f"Temps moyen trajet : {temps_moyen:.2f} s | "
            f"En attente au feu : {vehicules_attente_feu} | "
            f"En bouchon : {vehicules_bouchon}"
        )

        message = json.dumps(statistiques)

        # Un verrou évite de démarrer un nouvel envoi si le précédent est bloqué.
        if not self.verrou_envoi_statistiques.acquire(blocking=False):
            return

        thread = threading.Thread(
            target=self.envoyer_statistiques_thread,
            args=(message,),
            daemon=True,
        )
        try:
            thread.start()
        except RuntimeError as erreur:
            self.verrou_envoi_statistiques.release()
            print(f"Impossible de démarrer l'envoi des statistiques : {erreur}")

    def envoyer_statistiques_thread(self, message):
        try:
            envoyer_message(message, timeout=3)
        except OSError as erreur:
            print(f"Envoi des statistiques impossible : {erreur}")
        except Exception as erreur:
            print(f"Erreur pendant l'envoi des statistiques : {type(erreur).__name__}")
        finally:
            self.verrou_envoi_statistiques.release()

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

        return not self.vehicule_bloque_par_un_autre(vehicule)

    def mettre_a_jour_position_vehicule(self, vehicule):
        x1, y1 = self.scene.positions[vehicule.depart]
        x2, y2 = self.scene.positions[vehicule.arrivee]

        dx = x2 - x1
        dy = y2 - y1
        avancement_visuel = vehicule.avancement
        longueur = math.sqrt(dx * dx + dy * dy)
        feu_rouge = not self.graphe.est_vert(vehicule.arrivee, vehicule.depart)
        indice_vehicule = self.vehicules.index(vehicule)
        vehicule_devant = False

        for indice_autre, autre_vehicule in enumerate(self.vehicules):
            if autre_vehicule == vehicule:
                continue

            meme_depart = autre_vehicule.depart == vehicule.depart
            meme_arrivee = autre_vehicule.arrivee == vehicule.arrivee
            devant = (
                autre_vehicule.avancement > vehicule.avancement
                or (
                    autre_vehicule.avancement == vehicule.avancement
                    and indice_autre < indice_vehicule
                )
            )
            if meme_depart and meme_arrivee and devant:
                vehicule_devant = True
                break

        if longueur > 0 and not vehicule_devant:
            if feu_rouge or vehicule.avancement >= 1:
                distance_arret = min(28, longueur * 0.5)
                avancement_arret = 1 - distance_arret / longueur
                avancement_visuel = min(vehicule.avancement, avancement_arret)

        x = x1 + dx * avancement_visuel
        y = y1 + dy * avancement_visuel

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

        if vehicule in self.transitions_feux:
            depart_x, depart_y = self.transitions_feux[vehicule]
            progression_transition = min(vehicule.avancement / 0.20, 1)
            x = depart_x + (x - depart_x) * progression_transition
            y = depart_y + (y - depart_y) * progression_transition
            if progression_transition >= 1:
                del self.transitions_feux[vehicule]

        angle = math.degrees(math.atan2(dy, dx))
        vehicule.graphique.setRotation(angle)
        vehicule.graphique.setPos(x, y)

    def mettre_a_jour_positions_vehicules(self):
        for vehicule in self.vehicules:
            self.mettre_a_jour_position_vehicule(vehicule)

    def tick(self):
        if self.simulation_active == False:
            return

        self.actualiser_temps_simulation_actif()

        vehicules_encore_actifs = []
        statistiques_a_actualiser = False
        for vehicule in self.vehicules:
            self.mettre_a_jour_position_vehicule(vehicule)
            position_avant_avancement = vehicule.graphique.pos()
            depart_avant = vehicule.depart
            arrivee_avant = vehicule.arrivee
            fin_arete = vehicule.avancement >= 1

            if self.vehicule_peut_avancer(vehicule):
                resultat = vehicule.avancer(self.graphe)
                self.afficher_feux_selon_graphe()
                if (
                    fin_arete
                    and resultat != "arrive"
                    and (vehicule.depart != depart_avant or vehicule.arrivee != arrivee_avant)
                ):
                    self.transitions_feux[vehicule] = (
                        position_avant_avancement.x(),
                        position_avant_avancement.y()
                    )
            else:
                resultat = "en cours"

            if resultat != "en cours" and resultat != "attends feu":
                print(resultat)

            if resultat != "arrive":
                vehicules_encore_actifs.append(vehicule)
            else:
                statistiques_a_actualiser = True
                self.vehicules_arrives += 1
                duree_trajet = (
                    self.temps_simulation_actif - vehicule.temps_debut_trajet_actif
                )
                self.temps_total_trajets_termines += max(0.0, duree_trajet)
                self.nombre_trajets_termines += 1
                if vehicule == self.vehicule_selectionne:
                    self.deselectionner_vehicule()
                self.scene.removeItem(vehicule.graphique)
                self.transitions_feux.pop(vehicule, None)
                self.gyrophare_vehicules.pop(vehicule, None)

        self.vehicules = vehicules_encore_actifs

        while self.nombre_vehicules_voulu > 0 and len(self.vehicules) < self.nombre_vehicules_voulu:
            vehicule = self.creer_vehicule_aleatoire()
            if vehicule is None:
                break

        if statistiques_a_actualiser:
            self.actualiser_statistiques_interface()

        if not self.gyrophare_vehicules:
            self.timer_gyrophare.stop()


app = QApplication(sys.argv)

fenetre = FenetrePrincipale()
fenetre.show()

sys.exit(app.exec())
