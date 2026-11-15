"""Point d'entrée de l'application : fenêtre principale et boucle de simulation.

Lancement : ``python application\\interface.py`` depuis la racine du projet.

Organisation générale :
- ``Graphes`` (graphes.py) contient les données du réseau ;
- ``SceneGraphe`` (scene_graphe.py) dessine ce réseau ;
- ``Vehicule`` (vehicule.py) calcule la progression de chaque véhicule ;
- ``FenetrePrincipale`` (ce fichier) relie le tout : boutons, minuteries,
  règles entre véhicules, statistiques et envoi réseau.
"""

import json
import sys
import math
import threading
import time
from pathlib import Path

# On ajoute la racine du projet (dossier parent de application/) au chemin
# de recherche des modules, pour pouvoir importer reseau/client.py.
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
    """Assemble l'interface et coordonne la simulation du trafic."""

    # ==================================================================
    # 1. Construction de la fenêtre
    # ==================================================================

    def __init__(self):
        """Initialise l'état, la scène, les widgets et les minuteries Qt."""
        super().__init__()

        self.setWindowTitle("Simulateur de trafic")
        self.resize(1000, 700)

        # --- État de la simulation ---
        self.graphe = Graphes()
        self.vehicules = []
        self.vehicule_selectionne = None
        # Mémorise l'apparence des routes avant de les colorer en orange,
        # pour pouvoir la rétablir à la désélection.
        self.pen_routes_avant_selection = {}
        # Écarts exprimés en proportion de la longueur de l'arête.
        self.distance_securite = 0.08
        self.distance_laisser_passer = 0.20
        # Multiplicateur du décalage graphique d'une voie pour laisser passer.
        self.decalage_laisser_passer = 2
        self.simulation_active = False
        # Densité voulue : nombre de véhicules à maintenir sur le réseau.
        self.nombre_vehicules_voulu = 0

        # --- Compteurs pour les statistiques ---
        self.vehicules_arrives = 0
        # Temps de simulation « active » (sans les pauses), en secondes.
        self.temps_simulation_actif = 0.0
        self.dernier_instant_actif = None
        self.temps_total_trajets_termines = 0.0
        self.nombre_trajets_termines = 0

        # Verrou : empêche de lancer un nouvel envoi réseau tant que le
        # précédent n'est pas terminé.
        self.verrou_envoi_statistiques = threading.Lock()

        # --- Éléments purement visuels ---
        # Véhicule prioritaire -> (rectangle bleu, rectangle rouge) du gyrophare.
        self.gyrophare_vehicules = {}
        self.gyrophare_bleu_actif = True
        # Véhicule -> position (x, y) au moment où il a changé de route,
        # pour animer ce changement en douceur.
        self.transitions_feux = {}
        self.couleurs_vehicules_normaux = [
            QColor("#2676b8"),
            QColor("#7b4ab2"),
            QColor("#08a6b8"),
            QColor("#b98500"),
            QColor("#cb6c27"),
        ]

        # La scène dessine le réseau; la vue ajoute zoom et déplacement.
        self.scene = SceneGraphe(self.graphe)
        # La scène a besoin de la fenêtre (liste des véhicules, barre d'état).
        self.scene.fenetre = self
        self.view = VueGraphe(self.scene)

        # Phase commune à tous les feux : True = phase 0, False = phase 1.
        self.feu_vert = True

        # Les boutons relient les actions visibles aux méthodes de la fenêtre.
        # clicked.connect(f) : « quand on clique, appeler f » (signal -> slot).
        self.bouton_noeud = QPushButton("Ajouter un nœud")
        self.bouton_noeud.clicked.connect(self.scene.activer_ajout_noeud)

        self.bouton_vehicule = QPushButton("Créer véhicule")
        self.bouton_vehicule.clicked.connect(self.creer_vehicule)

        self.bouton_feu = QPushButton("Ajouter un feu")
        self.bouton_feu.clicked.connect(self.configurer_feu)

        self.bouton_graphe_test = QPushButton("Graphe de test")
        self.bouton_graphe_test.clicked.connect(self.creer_graphe_test)

        self.bouton_simulation = QPushButton("Démarrer")
        # Le nom d'objet permet de lui donner un style particulier (voir setStyleSheet).
        self.bouton_simulation.setObjectName("boutonSimulation")
        self.bouton_simulation.clicked.connect(self.demarrer_pause)

        self.combo_densite = QComboBox()
        self.combo_densite.addItems(list(DENSITES_TEST.keys()))
        self.combo_densite.setCurrentText("Faible")

        # Construire le panneau latéral par sections : simulation, véhicules, graphe, mesures.
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

        # Tableau à deux colonnes : intitulé à gauche, valeur à droite.
        section_statistiques = QGroupBox("STATISTIQUES")
        layout_statistiques = QGridLayout()
        # Clé de la statistique -> QLabel qui affiche sa valeur.
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

        # Le panneau peut défiler si la fenêtre est trop petite.
        panneau_defilant = QScrollArea()
        panneau_defilant.setWidgetResizable(True)
        panneau_defilant.setFixedWidth(280)
        panneau_defilant.setWidget(panneau)

        # Disposition horizontale : panneau à gauche, vue du graphe à droite.
        conteneur = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(panneau_defilant)
        layout.addWidget(self.view, 1)

        conteneur.setLayout(layout)

        # Placer le panneau et la vue dans la fenêtre, puis appliquer le style commun.
        # La feuille de style utilise une syntaxe proche du CSS.
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

        # Chaque minuterie Qt appelle sa méthode dans le fil de l'interface.
        # Elles sont seulement créées ici ; start() les lancera plus tard.
        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)

        self.timer_feux = QTimer()
        self.timer_feux.timeout.connect(self.changer_feux)

        self.timer_statistiques = QTimer()
        self.timer_statistiques.timeout.connect(self.envoyer_statistiques)

        self.timer_gyrophare = QTimer()
        self.timer_gyrophare.timeout.connect(self.changer_gyrophare)
        self.actualiser_statistiques_interface()

    # ==================================================================
    # 2. Feux de circulation
    # ==================================================================

    def trouver_groupes(self, noeud):
        """Répartit quatre routes en deux phases opposées selon leur angle."""
        routes = list(self.graphe.aretes[noeud].keys())

        x, y = self.scene.positions[noeud]

        directions = []

        # Calculer l'angle de chaque route vue depuis le carrefour.
        for route in routes:
            xr, yr = self.scene.positions[route]

            dx = xr - x
            dy = yr - y

            # atan2 donne l'angle (en radians, entre -pi et pi) du vecteur (dx, dy).
            angle = math.atan2(dy, dx)

            directions.append({
                "nom": route,
                "angle": angle
            })

        # Trier les routes dans l'ordre où on les rencontre en tournant autour du carrefour.
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
        """Bouton « Ajouter un feu » : demande un carrefour et y installe un feu."""
        noeud, valide = QInputDialog.getItem(
            self,
            "Ajouter un feu",
            "Choisissez le carrefour :",
            list(self.graphe.noeuds.keys()),
            0,
            False
        )

        # valide vaut False si l'utilisateur a cliqué sur « Annuler ».
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

        # D'abord le modèle, puis le dessin.
        self.graphe.definir_feu(noeud, phases)

        self.scene.dessiner_feu(noeud, groupes)
        self.statusBar().showMessage(f"Feu ajouté au carrefour {noeud}", 3000)

        print(f"Feu ajouté au carrefour {noeud}")
        print(f"Groupe vert : {groupes[0]}")
        print(f"Groupe rouge : {groupes[1]}")

    # ==================================================================
    # 3. Graphe de test
    # ==================================================================

    def creer_graphe_test(self):
        """Réinitialise la scène puis construit le réseau et les véhicules de test."""
        self.deselectionner_vehicule()

        # Remise à zéro des compteurs.
        densite = self.combo_densite.currentText()
        self.nombre_vehicules_voulu = DENSITES_TEST[densite]
        self.vehicules_arrives = 0
        self.temps_simulation_actif = 0.0
        self.dernier_instant_actif = None
        self.temps_total_trajets_termines = 0.0
        self.nombre_trajets_termines = 0

        # Arrêt de la simulation en cours.
        self.simulation_active = False
        self.timer.stop()
        self.timer_feux.stop()
        self.timer_statistiques.stop()
        self.timer_gyrophare.stop()
        self.gyrophare_vehicules = {}
        self.transitions_feux = {}
        self.bouton_simulation.setText("Démarrer")

        # Nouveau modèle vide.
        self.graphe = Graphes()
        self.vehicules = []
        self.feu_vert = True

        # scene.clear() supprime tous les objets dessinés ; on vide aussi
        # les dictionnaires de la scène qui pointaient vers eux.
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

        # Construction du réseau : nœuds, routes, puis feux.
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

        # Véhicules de départ, selon la densité choisie.
        for i in range(self.nombre_vehicules_voulu):
            self.creer_vehicule_aleatoire()

        self.view.ajuster_au_graphe()
        print("Graphe de test créé")
        print(f"Véhicules créés : {len(self.vehicules)}")
        print(f"Feux : {FEUX_TEST}")
        self.actualiser_statistiques_interface()
        self.statusBar().showMessage("Graphe de test créé", 3000)

    def mettre_a_jour_feux(self):
        """Applique la phase courante à chaque feu et rafraîchit son dessin."""

        # Tous les feux suivent la même phase (feux synchronisés).
        for noeud in self.scene.feux:

            if self.feu_vert:
                self.graphe.changer_phase(noeud, 0)
            else:
                self.graphe.changer_phase(noeud, 1)

        self.afficher_feux_selon_graphe()

    def afficher_feux_selon_graphe(self):
        """Colore chaque pastille selon la phase active enregistrée dans le modèle."""
        for noeud in self.scene.feux:

            phase_active = self.graphe.noeuds[noeud]["phase_active"]

            for voisin in self.scene.feux[noeud]:

                feu = self.scene.feux[noeud][voisin]
                graphique = feu["graphique"]
                groupe = feu["groupe"]

                # La pastille est verte si sa route appartient à la phase active.
                if groupe == phase_active:
                    graphique.setBrush(
                        QBrush(QColor("green"))
                    )
                else:
                    graphique.setBrush(
                        QBrush(QColor("red"))
                    )

    # ==================================================================
    # 4. Création et sélection des véhicules
    # ==================================================================

    def ajouter_vehicule(self, depart, destination, vitesse, est_urgent=False, afficher_erreur=True):
        """Crée le modèle et le rectangle graphique d'un véhicule.

        Un véhicule prioritaire reçoit une vitesse augmentée selon les règles
        actuelles et des éléments graphiques de gyrophare.
        """
        if est_urgent:
            # Le bonus de vitesse est plafonné à 1 pour rester dans la plage choisie.
            vitesse = vitesse * 1.3

            if vitesse > 1.0:
                vitesse = 1.0

        # 1. Le modèle : Vehicule calcule son chemin avec Dijkstra.
        try:
            vehicule = Vehicule(
                self.graphe,
                depart,
                vitesse,
                destination,
                est_urgent=est_urgent
            )
        except ValueError as erreur:
            # Pas de chemin possible : on prévient l'utilisateur (sauf pour
            # les véhicules aléatoires, créés silencieusement).
            if afficher_erreur:
                QMessageBox.warning(self, "Trajet impossible", str(erreur))
            return None

        # On note l'heure de départ pour calculer la durée du trajet à l'arrivée.
        vehicule.temps_debut_trajet_actif = self.obtenir_temps_simulation_actif()

        self.vehicules.append(vehicule)

        x, y = self.scene.positions[depart]

        # 2. Le dessin : un rectangle de 18 x 10 pixels centré sur (0, 0).
        voiture_graphique = QGraphicsRectItem(-9, -5, 18, 10)

        if est_urgent:
            couleur = QColor("black")
            voiture_graphique.setPen(QPen(QColor("#303840"), 1))

            # Les deux moitiés du gyrophare sont des « enfants » du rectangle :
            # elles se déplacent et tournent automatiquement avec lui.
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

        # Le véhicule garde une référence vers son dessin.
        vehicule.graphique = voiture_graphique
        self.mettre_a_jour_position_vehicule(vehicule)

        # Le clignotement du gyrophare n'est lancé que s'il y a un prioritaire.
        if est_urgent:
            self.gyrophare_vehicules[vehicule] = (gyro_bleu, gyro_rouge)
            if not self.timer_gyrophare.isActive():
                self.timer_gyrophare.start(200)

        return vehicule

    def selectionner_vehicule(self, vehicule):
        """Colore en orange le chemin Dijkstra du véhicule cliqué.

        Un second clic sur le même véhicule annule la sélection.
        """
        if vehicule == self.vehicule_selectionne:
            self.deselectionner_vehicule()
            return

        self.deselectionner_vehicule()
        self.vehicule_selectionne = vehicule

        chemin = vehicule.chemin
        if not isinstance(chemin, (list, tuple)):
            return

        # zip(chemin, chemin[1:]) donne les routes successives :
        # ['A', 'B', 'G'] -> ('A', 'B'), ('B', 'G').
        for depart, arrivee in zip(chemin, chemin[1:]):
            cle = self.scene.cle_arete(depart, arrivee)
            for ligne in self.scene.lignes_aretes.get(cle, []):
                # Sauvegarder le style d'origine avant de le modifier.
                self.pen_routes_avant_selection[ligne] = QPen(ligne.pen())
                pen = QPen(ligne.pen())
                pen.setColor(QColor("orange"))
                pen.setWidthF(3.0)
                ligne.setPen(pen)

    def deselectionner_vehicule(self):
        """Rend aux routes leur style d'origine."""
        for ligne, pen in self.pen_routes_avant_selection.items():
            ligne.setPen(pen)

        self.pen_routes_avant_selection = {}
        self.vehicule_selectionne = None

    def creer_vehicule_aleatoire(self):
        """Crée un véhicule normal entre deux nœuds tirés au hasard."""
        noeuds = list(self.graphe.noeuds.keys())

        if len(noeuds) < 2:
            return None

        depart = random.choice(noeuds)
        destination = random.choice(noeuds)

        # Retirer au sort tant que la destination est égale au départ.
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
        """Demande les paramètres à l'utilisateur puis ajoute le véhicule choisi."""
        # Chaque boîte de dialogue renvoie (valeur, valide) ;
        # valide vaut False si l'utilisateur clique sur « Annuler ».
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

        # Arguments : valeur par défaut 0.1, minimum 0.01, maximum 1.0, 2 décimales.
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

    # ==================================================================
    # 5. Minuteries : feux, gyrophare, démarrage / pause
    # ==================================================================

    def changer_feux(self):
        """Appelée toutes les 5 s : inverse la phase de tous les feux."""
        if self.simulation_active == False:
            return

        self.feu_vert = not self.feu_vert
        self.mettre_a_jour_feux()

    def changer_gyrophare(self):
        """Alterne les couleurs actives des gyrophares prioritaires."""
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
        """Démarre ou suspend les minuteries de simulation, de feux et de mesures."""
        if self.simulation_active:
            # Mise en pause : on ajoute au compteur le temps écoulé depuis
            # le dernier démarrage, puis on arrête les minuteries.
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
            # Un tick d'animation toutes les 20 ms; feux et relevés toutes les 5 s.
            self.timer.start(20)
            self.timer_feux.start(5000)
            self.timer_statistiques.start(5000)
            self.statusBar().showMessage("Simulation démarrée", 3000)

    # ==================================================================
    # 6. Temps et statistiques
    # ==================================================================

    def actualiser_temps_simulation_actif(self):
        """Ajoute au compteur le temps écoulé depuis la dernière mise à jour."""
        # time.monotonic() est une horloge qui ne recule jamais (contrairement
        # à l'heure système) : idéale pour mesurer des durées.
        if self.simulation_active and self.dernier_instant_actif is not None:
            maintenant = time.monotonic()
            self.temps_simulation_actif += maintenant - self.dernier_instant_actif
            self.dernier_instant_actif = maintenant

    def obtenir_temps_simulation_actif(self):
        """Renvoie le temps actif total, sans modifier le compteur."""
        temps = self.temps_simulation_actif
        if self.simulation_active and self.dernier_instant_actif is not None:
            temps += time.monotonic() - self.dernier_instant_actif
        return temps

    def calculer_temps_moyen_trajet(self):
        """Moyenne des durées des trajets terminés (0 s'il n'y en a aucun)."""
        if self.nombre_trajets_termines == 0:
            return 0.0
        return self.temps_total_trajets_termines / self.nombre_trajets_termines

    def obtenir_statistiques(self):
        """Construit le relevé utilisé à la fois par l'interface et le client TCP."""
        return {
            # "type" permet au serveur de reconnaître un relevé de statistiques.
            "type": "statistiques",
            "vehicules_actifs": len(self.vehicules),
            "vehicules_arrives": self.vehicules_arrives,
            # sum(1 for ... if ...) compte les éléments qui vérifient la condition.
            "vehicules_prioritaires": sum(
                1 for vehicule in self.vehicules if vehicule.est_urgent
            ),
            "temps_moyen_trajet": self.calculer_temps_moyen_trajet(),
            "vehicules_attente_feu": self.compter_vehicules_attente_feu(),
            "vehicules_bouchon": self.compter_vehicules_bouchon(),
        }

    def actualiser_statistiques_interface(self):
        """Recalcule les statistiques, les affiche et les renvoie."""
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

    # ==================================================================
    # 7. Règles de circulation entre véhicules
    # ==================================================================

    def feu_rouge_devant(self, vehicule):
        """Vrai si le feu au bout de la route actuelle interdit le passage.

        Sur la dernière route du trajet, le véhicule s'arrête à sa destination
        et ne traverse pas le carrefour : le feu ne le concerne donc pas.
        """
        if vehicule.est_sur_derniere_route():
            return False
        # est_vert(carrefour, route d'où l'on vient)
        return not self.graphe.est_vert(vehicule.arrivee, vehicule.depart)

    def vehicule_attend_au_feu(self, vehicule):
        """Vrai si le véhicule a atteint l'intersection et que son feu est rouge."""
        return (
            vehicule.avancement >= 1
            and self.feu_rouge_devant(vehicule)
        )

    def compter_vehicules_attente_feu(self):
        """Compte les véhicules qui patientent à un feu rouge."""
        return sum(1 for vehicule in self.vehicules if self.vehicule_attend_au_feu(vehicule))

    def vehicule_bloque_par_un_autre(self, vehicule):
        """Détecte un véhicule trop proche d'un autre sur la même arête."""
        indice_vehicule = self.vehicules.index(vehicule)

        for indice_autre, autre_vehicule in enumerate(self.vehicules):
            if autre_vehicule == vehicule:
                continue

            # Même route ET même sens : même depart et même arrivee.
            meme_depart = autre_vehicule.depart == vehicule.depart
            meme_arrivee = autre_vehicule.arrivee == vehicule.arrivee
            # L'autre est devant s'il a plus avancé. À égalité, celui créé en
            # premier (indice plus petit) est considéré comme devant, pour
            # éviter que deux véhicules se bloquent mutuellement.
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

                # Écart entre les deux véhicules, en proportion de la route.
                distance = autre_vehicule.avancement - vehicule.avancement
                # Marge visuelle plus distance que le véhicule parcourt au prochain tick.
                marge_pixels = 22 + vehicule.vitesse * (20 / 300) * longueur
                # Conversion des pixels en proportion de la route.
                distance_requise = max(self.distance_securite, marge_pixels / longueur)

                # Si le véhicule de devant est arrêté au feu, il est dessiné
                # 28 px avant le carrefour : il faut s'arrêter derrière lui.
                autre_au_feu_rouge = self.feu_rouge_devant(autre_vehicule)
                if autre_au_feu_rouge:
                    distance_arret = min(28, longueur * 0.5)
                    avancement_ligne_arret = 1 - distance_arret / longueur
                    if autre_vehicule.avancement >= avancement_ligne_arret:
                        distance_requise = max(
                            distance_requise,
                            (distance_arret + marge_pixels) / longueur
                        )

                if distance < distance_requise:
                    # Un prioritaire n'est pas bloqué par un véhicule qui
                    # s'écarte pour lui : il le dépasse.
                    if vehicule.est_urgent:
                        if self.vehicule_ecarte_pour_prioritaire(autre_vehicule, vehicule):
                            continue
                    return True

        return False

    def compter_vehicules_bouchon(self):
        """Compte les véhicules ralentis par un autre, hors attente au feu."""
        nombre = 0
        for vehicule in self.vehicules:
            # Arrêté au feu : compté dans l'autre statistique.
            if self.vehicule_attend_au_feu(vehicule):
                continue
            # Arrêté pour laisser passer un prioritaire : ce n'est pas un bouchon.
            if self.vehicule_doit_secarter(vehicule):
                continue
            if self.vehicule_bloque_par_un_autre(vehicule):
                nombre += 1
        return nombre

    # ==================================================================
    # 8. Envoi réseau des statistiques
    # ==================================================================

    def envoyer_statistiques(self):
        """Prépare un relevé et démarre son envoi réseau sans bloquer l'interface."""
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

        # Dictionnaire Python -> texte JSON.
        message = json.dumps(statistiques)

        # Un verrou évite de démarrer un nouvel envoi si le précédent est bloqué.
        # acquire(blocking=False) renvoie False immédiatement au lieu d'attendre.
        if not self.verrou_envoi_statistiques.acquire(blocking=False):
            return

        # L'envoi se fait dans un thread séparé : si le serveur ne répond pas,
        # c'est ce thread qui attend, pas l'interface.
        # daemon=True : le thread ne retient pas le programme à la fermeture.
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
        """Envoie le JSON au serveur et libère le verrou même en cas d'erreur."""
        try:
            envoyer_message(message, timeout=3)
        except OSError as erreur:
            # Serveur éteint, mauvaise adresse, délai dépassé... : on affiche
            # l'erreur et la simulation continue normalement.
            print(f"Envoi des statistiques impossible : {erreur}")
        except Exception as erreur:
            print(f"Erreur pendant l'envoi des statistiques : {type(erreur).__name__}")
        finally:
            # finally s'exécute dans tous les cas : le verrou est toujours libéré.
            self.verrou_envoi_statistiques.release()

    # ==================================================================
    # 9. Laisser passer les véhicules prioritaires
    # ==================================================================

    def vehicule_ecarte_pour_prioritaire(self, vehicule, vehicule_prioritaire):
        """Indique si un véhicule normal doit laisser de la place au prioritaire.

        La règle ne s'applique que sur la même arête, lorsque le véhicule
        prioritaire est derrière et suffisamment proche.
        """
        if vehicule.est_urgent:
            return False

        if vehicule_prioritaire.est_urgent == False:
            return False

        meme_depart = vehicule.depart == vehicule_prioritaire.depart
        meme_arrivee = vehicule.arrivee == vehicule_prioritaire.arrivee

        if meme_depart and meme_arrivee:
            if vehicule_prioritaire.avancement < vehicule.avancement:
                distance = vehicule.avancement - vehicule_prioritaire.avancement

                # Moins de 20 % de la route entre les deux : on s'écarte.
                if distance < self.distance_laisser_passer:
                    return True

        return False

    def vehicule_doit_secarter(self, vehicule):
        """Vrai si au moins un prioritaire arrive derrière ce véhicule."""
        for autre_vehicule in self.vehicules:
            if autre_vehicule != vehicule:
                if self.vehicule_ecarte_pour_prioritaire(vehicule, autre_vehicule):
                    return True

        return False

    def vehicule_peut_avancer(self, vehicule):
        """Un véhicule avance s'il ne s'écarte pas et s'il n'est pas bloqué."""
        if self.vehicule_doit_secarter(vehicule):
            return False

        return not self.vehicule_bloque_par_un_autre(vehicule)

    # ==================================================================
    # 10. Affichage des véhicules
    # ==================================================================

    def mettre_a_jour_position_vehicule(self, vehicule):
        """Calcule la position, le décalage de voie et l'orientation graphique."""
        x1, y1 = self.scene.positions[vehicule.depart]
        x2, y2 = self.scene.positions[vehicule.arrivee]

        dx = x2 - x1
        dy = y2 - y1
        # Position affichée ; peut différer de vehicule.avancement près d'un feu.
        avancement_visuel = vehicule.avancement
        longueur = math.sqrt(dx * dx + dy * dy)
        feu_rouge = self.feu_rouge_devant(vehicule)
        indice_vehicule = self.vehicules.index(vehicule)
        vehicule_devant = False

        # Y a-t-il un autre véhicule devant celui-ci sur la même voie ?
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

        # Limiter la position affichée avant le carrefour si le feu est rouge.
        # (Seul le premier de la file est concerné : les suivants sont déjà
        # retenus par la distance de sécurité.)
        if longueur > 0 and not vehicule_devant:
            if feu_rouge or vehicule.avancement >= 1:
                # Garder le véhicule à 28 pixels du nœud, ou plus près sur une petite arête.
                distance_arret = min(28, longueur * 0.5)
                avancement_arret = 1 - distance_arret / longueur
                avancement_visuel = min(vehicule.avancement, avancement_arret)

        # Interpolation entre les coordonnées des deux nœuds de l'arête.
        # avancement 0 -> (x1, y1) ; avancement 1 -> (x2, y2) ; 0.5 -> milieu.
        x = x1 + dx * avancement_visuel
        y = y1 + dy * avancement_visuel

        # Se placer sur sa voie (à droite de l'axe de la route).
        decalage_x, decalage_y = self.scene.calculer_decalage_perpendiculaire(
            x1,
            y1,
            x2,
            y2
        )

        x = x + decalage_x
        y = y + decalage_y

        # S'écarter davantage pour laisser passer un prioritaire.
        if self.vehicule_doit_secarter(vehicule):
            x = x + decalage_x * self.decalage_laisser_passer
            y = y + decalage_y * self.decalage_laisser_passer

        if vehicule in self.transitions_feux:
            depart_x, depart_y = self.transitions_feux[vehicule]
            # Lisser le changement d'arête sur les premiers 20 % du mouvement.
            progression_transition = min(vehicule.avancement / 0.20, 1)
            x = depart_x + (x - depart_x) * progression_transition
            y = depart_y + (y - depart_y) * progression_transition
            if progression_transition >= 1:
                del self.transitions_feux[vehicule]

        # atan2 fournit l'angle du segment, nécessaire à la rotation du rectangle.
        angle = math.degrees(math.atan2(dy, dx))
        vehicule.graphique.setRotation(angle)
        vehicule.graphique.setPos(x, y)

    def mettre_a_jour_positions_vehicules(self):
        """Replace tous les véhicules (utilisé quand on déplace un nœud)."""
        for vehicule in self.vehicules:
            self.mettre_a_jour_position_vehicule(vehicule)

    # ==================================================================
    # 11. Boucle principale de simulation
    # ==================================================================

    def tick(self):
        """Avance tous les véhicules, retire les arrivés et actualise les compteurs."""
        if self.simulation_active == False:
            return

        self.actualiser_temps_simulation_actif()

        # On construit la nouvelle liste des véhicules encore en route
        # plutôt que de supprimer des éléments pendant le parcours.
        vehicules_encore_actifs = []
        statistiques_a_actualiser = False
        for vehicule in self.vehicules:
            self.mettre_a_jour_position_vehicule(vehicule)
            # Mémoriser l'état avant le déplacement, pour détecter un changement de route.
            position_avant_avancement = vehicule.graphique.pos()
            depart_avant = vehicule.depart
            arrivee_avant = vehicule.arrivee
            fin_arete = vehicule.avancement >= 1

            if self.vehicule_peut_avancer(vehicule):
                resultat = vehicule.avancer(self.graphe)
                # Un prioritaire a pu changer un feu : on met à jour les couleurs.
                self.afficher_feux_selon_graphe()
                # Le véhicule vient de franchir un carrefour : on mémorise sa
                # position pour animer le passage sur la nouvelle route.
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
                # Bloqué ou en train de s'écarter : il ne bouge pas ce tick-ci.
                resultat = "en cours"

            if resultat != "en cours" and resultat != "attends feu":
                print(resultat)

            if resultat != "arrive":
                vehicules_encore_actifs.append(vehicule)
            else:
                # Arrivée : mise à jour des compteurs puis suppression du dessin.
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

        # Remplacer les véhicules arrivés pour garder la densité choisie.
        while self.nombre_vehicules_voulu > 0 and len(self.vehicules) < self.nombre_vehicules_voulu:
            vehicule = self.creer_vehicule_aleatoire()
            if vehicule is None:
                break

        if statistiques_a_actualiser:
            self.actualiser_statistiques_interface()

        # Plus aucun prioritaire : inutile de faire clignoter.
        if not self.gyrophare_vehicules:
            self.timer_gyrophare.stop()


# ----------------------------------------------------------------------
# Lancement de l'application
# ----------------------------------------------------------------------
# QApplication gère la boucle d'événements de Qt (clics, minuteries, dessin).
app = QApplication(sys.argv)

fenetre = FenetrePrincipale()
fenetre.show()

# app.exec() tourne jusqu'à la fermeture de la fenêtre.
sys.exit(app.exec())
