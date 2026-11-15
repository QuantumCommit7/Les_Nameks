"""Point d'entrée de l'application : fenêtre principale et boucle de simulation.

Lancement depuis la racine du projet : python application\\interface.py

- Graphes (graphes.py)          : les données du réseau ;
- SceneGraphe (scene_graphe.py) : le dessin du réseau ;
- Vehicule (vehicule.py)        : la progression de chaque véhicule ;
- FenetrePrincipale (ici)       : boutons, minuteries, règles entre véhicules,
                                  statistiques et envoi réseau.
"""

import json
import math
import random
import sys
import threading
import time
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QPen
from PyQt6.QtWidgets import (QApplication, QComboBox, QGraphicsEllipseItem, QGraphicsRectItem,
                             QGridLayout, QGroupBox,
                             QHBoxLayout, QInputDialog, QLabel, QMainWindow, QMessageBox,
                             QPushButton, QScrollArea, QVBoxLayout, QWidget)

from graphes import Graphes
from graphe_test import ARETES_TEST, DENSITES_TEST, FEUX_TEST, NOEUDS_TEST
from scene_graphe import SceneGraphe, cle_arete, decalage_perpendiculaire
from vehicule import DUREE_TICK, Vehicule
from vue_graphe import VueGraphe

# On ajoute la racine du projet aux chemins d'import pour trouver reseau/client.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from reseau.client import envoyer_message

# Code de la route. Vitesses en pixels par seconde, distances en pixels.
VITESSE_LIMITE = 60          # tous les véhicules normaux respectent la même limitation
VITESSE_PRIORITAIRE = 100    # un véhicule d'urgence roule plus vite que tous les autres
DISTANCE_SECURITE = 22       # écart minimal avec le véhicule de devant
DISTANCE_LAISSER_PASSER = 80 # un prioritaire à moins de 80 px derrière : on se range sur le côté
ARRET_FEU_PIXELS = 28        # un véhicule arrêté au feu est dessiné 28 px avant le carrefour

COULEURS_VEHICULES = ["#2676b8", "#7b4ab2", "#08a6b8", "#b98500", "#cb6c27"]
GRIS_GYROPHARE = "#3a4249"   # couleur d'une lampe éteinte

STATISTIQUES = [
    ("vehicules_actifs", "Véhicules actifs"),
    ("vehicules_arrives", "Véhicules arrivés"),
    ("vehicules_prioritaires", "Véhicules prioritaires"),
    ("temps_moyen_trajet", "Temps moyen de trajet"),
    ("vehicules_attente_feu", "En attente au feu rouge"),
    ("vehicules_bouchon", "Bloqués dans un bouchon"),
]

LEGENDE = [
    ("#2676b8", "Véhicule normal (palette variée)"),
    ("red", "Véhicule prioritaire (gyrophare bleu / rouge)"),
    ("green", "Feu vert"),
    ("red", "Feu rouge"),
    ("orange", "Trajet Dijkstra sélectionné"),
]

STYLE = """
    QWidget { background-color: #f3f6f5; color: #263238; font-family: "Segoe UI"; font-size: 10pt; }
    QGroupBox { background-color: #ffffff; border: 1px solid #d5dfdc; border-radius: 5px;
                margin-top: 9px; padding: 8px; font-weight: bold; color: #344a46; }
    QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
    QPushButton, QComboBox { min-height: 30px; background-color: #ffffff; border: 1px solid #cbd6d2;
                             border-radius: 4px; padding: 3px 8px; }
    QPushButton:hover { background-color: #e8efed; }
    QPushButton#boutonSimulation { background-color: #28766a; color: white; border: none; font-weight: bold; }
    QPushButton#boutonSimulation:hover { background-color: #206358; }
    QLabel { background-color: transparent; }
    QStatusBar { background-color: #ffffff; color: #344a46; }
"""


class FenetrePrincipale(QMainWindow):

    # ==================== 1. Construction de la fenêtre ====================

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simulateur de trafic")
        self.resize(1000, 700)
        self.setMinimumSize(850, 560)
        # Style appliqué à toute l'application : fenêtre, boîtes de dialogue et menus
        # restent lisibles même si Windows est en thème sombre.
        QApplication.instance().setStyleSheet(STYLE)

        self.graphe = Graphes()
        self.vehicules = []
        self.nombre_vehicules_voulu = 0   # densité à maintenir
        self.numero_prochain_vehicule = 0
        self.vehicule_selectionne = None
        self.styles_avant_selection = {}  # ligne de route -> son style avant la sélection
        self.simulation_active = False
        self.feu_vert = True              # phase commune à tous les feux : True = 0, False = 1
        self.gyrophares = {}              # véhicule prioritaire -> (moitié bleue, moitié rouge)
        self.gyrophare_bleu_actif = True
        self.transitions = {}             # véhicule -> (x, y) quand il a changé de route
        # Verrou : un seul envoi réseau à la fois.
        self.verrou_envoi = threading.Lock()
        self.reinitialiser_compteurs()

        # La scène dessine le réseau ; la vue ajoute zoom et déplacement.
        self.scene = SceneGraphe(self.graphe)
        self.scene.fenetre = self
        self.view = VueGraphe(self.scene)

        # clicked.connect(f) : « quand on clique sur le bouton, appeler f ».
        self.bouton_simulation = self.creer_bouton("Démarrer", self.demarrer_pause)
        self.bouton_simulation.setObjectName("boutonSimulation")  # style particulier (voir STYLE)
        self.combo_densite = QComboBox()
        self.combo_densite.addItems(list(DENSITES_TEST))
        self.combo_densite.setCurrentText("Faible")

        panneau = QVBoxLayout()
        panneau.addWidget(self.creer_section("SIMULATION", [
            self.bouton_simulation, self.combo_densite,
            self.creer_bouton("Graphe de test", self.creer_graphe_test),
            self.creer_bouton("Réinitialiser (tout effacer)", self.reinitialiser)]))
        panneau.addWidget(self.creer_section("VÉHICULES", [
            self.creer_bouton("Créer véhicule", self.creer_vehicule)]))
        panneau.addWidget(self.creer_section("ÉDITION DU GRAPHE", [
            self.creer_bouton("Ajouter un nœud", self.scene.activer_ajout_noeud),
            self.creer_bouton("Ajouter un feu", self.configurer_feu)]))
        panneau.addWidget(self.creer_section_statistiques())
        panneau.addWidget(self.creer_section_legende())
        panneau.addStretch()

        # Panneau à gauche (avec barre de défilement si besoin), vue du graphe à droite.
        widget_panneau = QWidget()
        widget_panneau.setLayout(panneau)
        defilement = QScrollArea()
        defilement.setWidgetResizable(True)
        defilement.setFixedWidth(280)
        defilement.setWidget(widget_panneau)
        disposition = QHBoxLayout()
        disposition.addWidget(defilement)
        disposition.addWidget(self.view, 1)
        conteneur = QWidget()
        conteneur.setLayout(disposition)
        self.setCentralWidget(conteneur)
        self.statusBar().showMessage("Simulation en pause")

        # Minuteries : chacune appelle sa méthode à intervalle régulier une fois démarrée.
        self.timer = self.creer_minuterie(self.tick)                     # 20 ms
        self.timer_feux = self.creer_minuterie(self.changer_feux)        # 5 s
        self.timer_statistiques = self.creer_minuterie(self.envoyer_statistiques)  # 5 s
        self.timer_gyrophare = self.creer_minuterie(self.changer_gyrophare)        # 200 ms
        self.actualiser_statistiques()

    def creer_bouton(self, texte, action):
        bouton = QPushButton(texte)
        bouton.clicked.connect(action)
        return bouton

    def creer_minuterie(self, action):
        minuterie = QTimer()
        minuterie.timeout.connect(action)
        return minuterie

    def creer_section(self, titre, widgets):
        """Un cadre titré qui empile des widgets verticalement."""
        section = QGroupBox(titre)
        layout = QVBoxLayout()
        for widget in widgets:
            layout.addWidget(widget)
        section.setLayout(layout)
        return section

    def creer_section_statistiques(self):
        """Tableau à deux colonnes : intitulé à gauche, valeur à droite."""
        section = QGroupBox("STATISTIQUES")
        grille = QGridLayout()
        self.labels_statistiques = {}
        for ligne, (cle, nom) in enumerate(STATISTIQUES):
            intitule = QLabel(nom)
            intitule.setStyleSheet("color: #64716e;")
            valeur = QLabel("0")
            valeur.setAlignment(Qt.AlignmentFlag.AlignRight)
            valeur.setStyleSheet("font-size: 11pt; font-weight: bold;")
            grille.addWidget(intitule, ligne, 0)
            grille.addWidget(valeur, ligne, 1)
            self.labels_statistiques[cle] = valeur
        grille.setColumnStretch(0, 1)
        section.setLayout(grille)
        return section

    def creer_section_legende(self):
        section = QGroupBox("LÉGENDE")
        layout = QVBoxLayout()
        for couleur, texte in LEGENDE:
            ligne = QHBoxLayout()
            pastille = QLabel("●")
            pastille.setStyleSheet(f"color: {couleur}; font-size: 14pt;")
            texte_legende = QLabel(texte)
            texte_legende.setWordWrap(True)  # retour à la ligne si le texte est long
            ligne.addWidget(pastille)
            ligne.addWidget(texte_legende, 1)
            layout.addLayout(ligne)
        section.setLayout(layout)
        return section

    def demander_choix(self, titre, question, choix):
        """Liste déroulante dans une boîte de dialogue. Renvoie None si on annule."""
        valeur, valide = QInputDialog.getItem(self, titre, question, choix, 0, False)
        return valeur if valide else None

    # ==================== 2. Feux ====================

    def trouver_groupes(self, noeud):
        """Répartit les 4 routes d'un carrefour en deux phases de routes face à face.

        On trie les routes selon leur angle autour du carrefour : la 1re et la 3e
        sont alors face à face, de même que la 2e et la 4e.
        """
        routes = list(self.graphe.aretes.get(noeud, {}))
        if len(routes) != 4:
            print("Le carrefour doit avoir exactement 4 routes")
            return None
        x, y = self.scene.positions[noeud]
        # atan2 donne l'angle (en radians) de la direction de chaque route.
        routes.sort(key=lambda r: math.atan2(self.scene.positions[r][1] - y,
                                             self.scene.positions[r][0] - x))
        return [[routes[0], routes[2]], [routes[1], routes[3]]]

    def configurer_feu(self):
        """Bouton « Ajouter un feu »."""
        noeud = self.demander_choix("Ajouter un feu", "Choisissez le carrefour :", list(self.graphe.noeuds))
        if noeud is None:
            return
        groupes = self.trouver_groupes(noeud)
        if groupes is None:
            return
        self.graphe.definir_feu(noeud, groupes)
        self.scene.dessiner_feu(noeud, groupes)
        self.statusBar().showMessage(f"Feu ajouté au carrefour {noeud}", 3000)

    def changer_feux(self):
        """Toutes les 5 s : tous les feux changent de phase en même temps."""
        self.feu_vert = not self.feu_vert
        self.mettre_a_jour_feux()

    def mettre_a_jour_feux(self):
        phase = 0 if self.feu_vert else 1
        for noeud in self.scene.feux:
            self.graphe.changer_phase(noeud, phase)
        self.colorer_feux()

    def colorer_feux(self):
        """Pastille verte si sa route fait partie de la phase active, rouge sinon."""
        for noeud, pastilles in self.scene.feux.items():
            phase_active = self.graphe.noeuds[noeud]["phase_active"]
            for feu in pastilles.values():
                couleur = "green" if feu["groupe"] == phase_active else "red"
                feu["graphique"].setBrush(QBrush(QColor(couleur)))

    # ==================== 3. Graphe de test ====================

    def reinitialiser_compteurs(self):
        self.vehicules_arrives = 0
        self.temps_actif = 0.0              # temps de simulation sans les pauses (s)
        self.dernier_instant = None
        self.temps_total_trajets = 0.0
        self.nombre_trajets = 0

    def reinitialiser(self):
        """Bouton « Réinitialiser » : arrête la simulation et vide complètement le tableau."""
        if self.simulation_active:
            self.demarrer_pause()  # met la simulation en pause
        self.timer_gyrophare.stop()
        self.deselectionner_vehicule()
        self.reinitialiser_compteurs()
        self.nombre_vehicules_voulu = 0
        self.vehicules = []
        self.gyrophares = {}
        self.transitions = {}
        self.feu_vert = True
        self.graphe = Graphes()
        self.scene.reinitialiser(self.graphe)
        self.actualiser_statistiques()
        self.statusBar().showMessage("Tableau vidé", 3000)

    def creer_graphe_test(self):
        """Vide le tableau, construit le réseau de graphe_test.py et ajoute les véhicules."""
        self.reinitialiser()
        self.nombre_vehicules_voulu = DENSITES_TEST[self.combo_densite.currentText()]

        for nom, (x, y) in NOEUDS_TEST.items():
            self.graphe.ajouter_noeud(nom)
            self.scene.dessiner_noeud(nom, x, y)
        for depart, arrivee, poids in ARETES_TEST:
            self.graphe.ajouter_arete(depart, arrivee, poids)
            self.scene.dessiner_arete(depart, arrivee)
        for noeud in FEUX_TEST:
            groupes = self.trouver_groupes(noeud)
            self.graphe.definir_feu(noeud, groupes)
            self.scene.dessiner_feu(noeud, groupes)

        for _ in range(self.nombre_vehicules_voulu):
            self.creer_vehicule_aleatoire()
        self.view.ajuster_au_graphe()
        self.actualiser_statistiques()
        self.statusBar().showMessage("Graphe de test créé", 3000)

    # ==================== 4. Création et sélection des véhicules ====================

    def ajouter_vehicule(self, depart, destination, est_urgent=False, afficher_erreur=True):
        """Crée un véhicule (modèle + rectangle dessiné). Renvoie None si pas de chemin.

        La vitesse n'est pas choisie : elle suit le code de la route
        (limitation pour tous, vitesse plus élevée pour les prioritaires).
        """
        vitesse = VITESSE_PRIORITAIRE if est_urgent else VITESSE_LIMITE
        try:
            vehicule = Vehicule(self.graphe, depart, vitesse, destination, est_urgent)
        except ValueError as erreur:
            if afficher_erreur:
                QMessageBox.warning(self, "Trajet impossible", str(erreur))
            return None

        vehicule.numero = self.numero_prochain_vehicule  # ordre de création
        self.numero_prochain_vehicule += 1
        vehicule.debut_trajet = self.obtenir_temps_actif()

        # Rectangle de 18 x 10 pixels centré sur (0, 0).
        vehicule.graphique = QGraphicsRectItem(-9, -5, 18, 10)
        if est_urgent:
            # Véhicule de secours : carrosserie blanche bordée de rouge + gyrophare.
            vehicule.graphique.setBrush(QBrush(QColor("white")))
            vehicule.graphique.setPen(QPen(QColor("red"), 1.5))
            self.gyrophares[vehicule] = self.creer_gyrophare(vehicule.graphique)
            self.changer_gyrophare(inverser=False)
            self.timer_gyrophare.start(150)
        else:
            vehicule.graphique.setBrush(QBrush(QColor(random.choice(COULEURS_VEHICULES))))
        self.scene.addItem(vehicule.graphique)

        self.vehicules.append(vehicule)
        self.placer_vehicule(vehicule)
        return vehicule

    def creer_gyrophare(self, carrosserie):
        """Rampe lumineuse sur le toit : une lampe bleue et une lampe rouge, chacune avec un halo.

        Ce sont des « enfants » de la carrosserie : ils bougent et tournent avec elle.
        Renvoie une liste de (lampe, halo, couleur).
        """
        lampes = []
        for couleur, x in (("#1e6bff", -7), ("#ff2020", 2)):
            # Halo : grand disque transparent autour de la lampe, visible quand elle est allumée.
            halo = QGraphicsEllipseItem(x - 6.5, -9, 18, 18, carrosserie)
            couleur_halo = QColor(couleur)
            couleur_halo.setAlpha(110)  # 0 = invisible, 255 = opaque
            halo.setBrush(QBrush(couleur_halo))
            halo.setPen(QPen(Qt.PenStyle.NoPen))
            lampe = QGraphicsRectItem(x, -4, 5, 8, carrosserie)
            lampe.setPen(QPen(QColor("black"), 0.5))
            lampes.append((lampe, halo, couleur))
        return lampes

    def creer_vehicule_aleatoire(self):
        """Véhicule normal entre deux nœuds différents tirés au hasard."""
        if len(self.graphe.noeuds) < 2:
            return None
        depart, destination = random.sample(list(self.graphe.noeuds), 2)
        return self.ajouter_vehicule(depart, destination, afficher_erreur=False)

    def creer_vehicule(self):
        """Bouton « Créer véhicule » : on demande les paramètres un par un."""
        noeuds = list(self.graphe.noeuds)
        if len(noeuds) < 2:
            QMessageBox.warning(self, "Erreur", "Créez d'abord au moins deux nœuds reliés par une route.")
            return
        depart = self.demander_choix("Départ", "Choisissez le départ :", noeuds)
        if depart is None:
            return
        destination = self.demander_choix("Destination", "Choisissez la destination :", noeuds)
        if destination is None:
            return
        if depart == destination:
            QMessageBox.warning(self, "Erreur", "Le départ et la destination doivent être différents.")
            return
        type_vehicule = self.demander_choix("Type de véhicule", "Choisissez le type :", ["Normal", "Prioritaire"])
        if type_vehicule is None:
            return

        est_urgent = type_vehicule == "Prioritaire"
        if self.ajouter_vehicule(depart, destination, est_urgent) is not None:
            self.statusBar().showMessage("Véhicule prioritaire créé" if est_urgent else "Véhicule créé", 3000)

    def selectionner_vehicule(self, vehicule):
        """Clic sur un véhicule : son chemin passe en orange. Second clic : on annule."""
        deja_selectionne = vehicule == self.vehicule_selectionne
        self.deselectionner_vehicule()
        if deja_selectionne:
            return
        self.vehicule_selectionne = vehicule
        # zip(chemin, chemin[1:]) donne les routes : [A, B, G] -> (A, B), (B, G).
        for depart, arrivee in zip(vehicule.chemin, vehicule.chemin[1:]):
            for ligne in self.scene.lignes_aretes.get(cle_arete(depart, arrivee), []):
                self.styles_avant_selection[ligne] = ligne.pen()
                pen = QPen(ligne.pen())
                pen.setColor(QColor("orange"))
                pen.setWidthF(3.0)
                ligne.setPen(pen)

    def deselectionner_vehicule(self):
        for ligne, pen in self.styles_avant_selection.items():
            ligne.setPen(pen)
        self.styles_avant_selection = {}
        self.vehicule_selectionne = None

    def changer_gyrophare(self, inverser=True):
        """Toutes les 150 ms : la lampe bleue et la lampe rouge s'allument à tour de rôle."""
        if inverser:
            self.gyrophare_bleu_actif = not self.gyrophare_bleu_actif
        for lampes in self.gyrophares.values():
            for numero, (lampe, halo, couleur) in enumerate(lampes):
                # Lampe 0 (bleue) allumée quand gyrophare_bleu_actif, lampe 1 (rouge) sinon.
                allumee = (numero == 0) == self.gyrophare_bleu_actif
                lampe.setBrush(QBrush(QColor(couleur if allumee else GRIS_GYROPHARE)))
                halo.setVisible(allumee)

    # ==================== 5. Démarrage / pause et temps ====================

    def demarrer_pause(self):
        if self.simulation_active:
            self.actualiser_temps_actif()
            self.simulation_active = False
            for minuterie in (self.timer, self.timer_feux, self.timer_statistiques):
                minuterie.stop()
            self.bouton_simulation.setText("Démarrer")
            self.statusBar().showMessage("Simulation en pause")
        else:
            self.simulation_active = True
            self.dernier_instant = time.monotonic()
            self.timer.start(20)
            self.timer_feux.start(5000)
            self.timer_statistiques.start(5000)
            self.bouton_simulation.setText("Pause")
            self.statusBar().showMessage("Simulation démarrée", 3000)

    def actualiser_temps_actif(self):
        """Ajoute le temps écoulé depuis la dernière mise à jour.

        time.monotonic() est une horloge qui ne recule jamais : idéale pour les durées.
        """
        maintenant = time.monotonic()
        self.temps_actif += maintenant - self.dernier_instant
        self.dernier_instant = maintenant

    def obtenir_temps_actif(self):
        if self.simulation_active:
            return self.temps_actif + time.monotonic() - self.dernier_instant
        return self.temps_actif

    # ==================== 6. Statistiques et envoi réseau ====================

    def obtenir_statistiques(self):
        """Relevé utilisé à la fois par l'affichage et par l'envoi au serveur."""
        temps_moyen = self.temps_total_trajets / self.nombre_trajets if self.nombre_trajets else 0.0
        return {
            "type": "statistiques",  # permet au serveur de reconnaître le message
            "vehicules_actifs": len(self.vehicules),
            "vehicules_arrives": self.vehicules_arrives,
            "vehicules_prioritaires": len([v for v in self.vehicules if v.est_urgent]),
            "temps_moyen_trajet": temps_moyen,
            "vehicules_attente_feu": len([v for v in self.vehicules if self.attend_au_feu(v)]),
            "vehicules_bouchon": len([v for v in self.vehicules if self.est_dans_un_bouchon(v)]),
        }

    def actualiser_statistiques(self):
        statistiques = self.obtenir_statistiques()
        for cle, label in self.labels_statistiques.items():
            label.setText(str(statistiques[cle]))
        self.labels_statistiques["temps_moyen_trajet"].setText(f"{statistiques['temps_moyen_trajet']:.2f} s")
        return statistiques

    def envoyer_statistiques(self):
        """Toutes les 5 s : envoie le relevé au serveur sans bloquer l'interface."""
        message = json.dumps(self.actualiser_statistiques())  # dictionnaire -> texte JSON
        # Si l'envoi précédent n'est pas fini, on saute ce relevé.
        # acquire(blocking=False) renvoie False tout de suite au lieu d'attendre.
        if not self.verrou_envoi.acquire(blocking=False):
            return
        # L'envoi se fait dans un thread : si le serveur ne répond pas, c'est ce thread
        # qui attend, pas la fenêtre. daemon=True : il ne bloque pas la fermeture.
        threading.Thread(target=self.envoyer_dans_un_thread, args=(message,), daemon=True).start()

    def envoyer_dans_un_thread(self, message):
        try:
            envoyer_message(message, timeout=3)
        except OSError as erreur:
            # Serveur éteint, mauvaise adresse, délai dépassé... la simulation continue.
            print(f"Envoi des statistiques impossible : {erreur}")
        finally:
            self.verrou_envoi.release()  # toujours exécuté, même en cas d'erreur

    # ==================== 7. Règles de circulation ====================

    def longueur_route(self, vehicule):
        x1, y1 = self.scene.positions[vehicule.depart]
        x2, y2 = self.scene.positions[vehicule.arrivee]
        return math.hypot(x2 - x1, y2 - y1)

    def ligne_arret(self, longueur):
        """Avancement (0 à 1) de la ligne d'arrêt : 28 px avant le carrefour,
        ou au milieu de la route si elle est très courte."""
        return 1 - min(ARRET_FEU_PIXELS, longueur * 0.5) / longueur

    def est_devant(self, autre, vehicule):
        """Vrai si `autre` roule devant `vehicule`, sur la même route et dans le même sens.

        À égalité d'avancement, le plus ancien est devant (sinon deux véhicules
        pourraient se bloquer l'un l'autre).
        """
        if autre is vehicule or (autre.depart, autre.arrivee) != (vehicule.depart, vehicule.arrivee):
            return False
        if autre.avancement != vehicule.avancement:
            return autre.avancement > vehicule.avancement
        return autre.numero < vehicule.numero

    def feu_rouge_devant(self, vehicule):
        """Le feu au bout de la route est-il rouge pour ce véhicule ?

        Sur la dernière route, il ne traverse pas le carrefour : le feu ne compte pas.
        """
        if vehicule.est_sur_derniere_route():
            return False
        return not self.graphe.est_vert(vehicule.arrivee, vehicule.depart)

    def attend_au_feu(self, vehicule):
        return vehicule.avancement >= 1 and self.feu_rouge_devant(vehicule)

    def laisse_passer(self, vehicule, prioritaire):
        """Un véhicule normal se range sur le côté si un prioritaire arrive derrière lui,
        sur la même route et dans le même sens, à moins de DISTANCE_LAISSER_PASSER pixels."""
        if vehicule.est_urgent or not prioritaire.est_urgent:
            return False
        if (vehicule.depart, vehicule.arrivee) != (prioritaire.depart, prioritaire.arrivee):
            return False
        # Écart en pixels (positif si le prioritaire est derrière).
        ecart = (vehicule.avancement - prioritaire.avancement) * self.longueur_route(vehicule)
        return 0 < ecart < DISTANCE_LAISSER_PASSER

    def doit_s_ecarter(self, vehicule):
        # any(...) : vrai si au moins un véhicule vérifie la condition.
        return any(self.laisse_passer(vehicule, autre) for autre in self.vehicules)

    def est_bloque(self, vehicule):
        """Vrai si un véhicule devant est trop proche (distance de sécurité)."""
        longueur = self.longueur_route(vehicule)
        if longueur == 0:
            return False
        for autre in self.vehicules:
            if not self.est_devant(autre, vehicule):
                continue
            # Distance de sécurité + distance parcourue en un tick, convertie en proportion.
            distance_requise = (DISTANCE_SECURITE + vehicule.vitesse * DUREE_TICK) / longueur
            # Le véhicule de devant est arrêté au feu, dessiné avant la ligne d'arrêt :
            # il faut aussi garder cet écart pour s'arrêter derrière lui.
            ligne = self.ligne_arret(longueur)
            if self.feu_rouge_devant(autre) and autre.avancement >= ligne:
                distance_requise += 1 - ligne
            if autre.avancement - vehicule.avancement < distance_requise:
                # Un prioritaire n'est pas bloqué par un véhicule qui s'écarte pour lui.
                if not self.laisse_passer(autre, vehicule):
                    return True
        return False

    def est_dans_un_bouchon(self, vehicule):
        """Bloqué par un autre véhicule, hors attente au feu et hors « laisser passer »."""
        return (not self.attend_au_feu(vehicule) and not self.doit_s_ecarter(vehicule)
                and self.est_bloque(vehicule))

    # ==================== 8. Affichage des véhicules ====================

    def placer_vehicule(self, vehicule):
        """Calcule où dessiner le véhicule : sur sa route, sur sa voie, bien orienté."""
        x1, y1 = self.scene.positions[vehicule.depart]
        x2, y2 = self.scene.positions[vehicule.arrivee]
        longueur = math.hypot(x2 - x1, y2 - y1)
        avancement = vehicule.avancement

        # Le premier de la file s'arrête visuellement à la ligne d'arrêt
        # (les suivants sont déjà retenus par la distance de sécurité).
        premier_de_la_file = not any(self.est_devant(autre, vehicule) for autre in self.vehicules)
        if longueur > 0 and premier_de_la_file and (self.feu_rouge_devant(vehicule) or avancement >= 1):
            avancement = min(avancement, self.ligne_arret(longueur))

        # avancement 0 -> premier nœud, 1 -> second nœud, 0.5 -> milieu.
        # On ajoute le décalage de la voie (x3 s'il s'écarte pour un prioritaire).
        dec_x, dec_y = decalage_perpendiculaire(x1, y1, x2, y2)
        facteur = 3 if self.doit_s_ecarter(vehicule) else 1
        x = x1 + (x2 - x1) * avancement + dec_x * facteur
        y = y1 + (y2 - y1) * avancement + dec_y * facteur

        # Juste après un carrefour, on glisse en douceur depuis l'ancienne position
        # pendant les premiers 20 % de la nouvelle route.
        if vehicule in self.transitions:
            ancien_x, ancien_y = self.transitions[vehicule]
            t = min(vehicule.avancement / 0.20, 1)
            x = ancien_x + (x - ancien_x) * t
            y = ancien_y + (y - ancien_y) * t
            if t >= 1:
                del self.transitions[vehicule]

        vehicule.graphique.setRotation(math.degrees(math.atan2(y2 - y1, x2 - x1)))
        vehicule.graphique.setPos(x, y)

    def mettre_a_jour_positions_vehicules(self):
        for vehicule in self.vehicules:
            self.placer_vehicule(vehicule)

    # ==================== 9. Boucle de simulation (toutes les 20 ms) ====================

    def tick(self):
        self.actualiser_temps_actif()
        encore_en_route = []
        for vehicule in self.vehicules:
            self.placer_vehicule(vehicule)
            resultat = "en cours"
            # Un véhicule qui s'écarte ou qui est bloqué ne bouge pas pendant ce tick.
            if not self.doit_s_ecarter(vehicule) and not self.est_bloque(vehicule):
                position_avant = vehicule.graphique.pos()
                route_avant = vehicule.depart
                etait_au_bout = vehicule.avancement >= 1
                resultat = vehicule.avancer(self.graphe, self.longueur_route(vehicule))
                # Il était arrêté au bout de la route et vient de franchir le carrefour :
                # on mémorise d'où il part pour animer son passage.
                if etait_au_bout and resultat == "en cours" and vehicule.depart != route_avant:
                    self.transitions[vehicule] = (position_avant.x(), position_avant.y())

            if resultat == "arrive":
                self.retirer_vehicule_arrive(vehicule)
            else:
                encore_en_route.append(vehicule)
        self.vehicules = encore_en_route

        # On remplace les véhicules arrivés pour garder la densité choisie.
        while len(self.vehicules) < self.nombre_vehicules_voulu:
            if self.creer_vehicule_aleatoire() is None:
                break
        self.colorer_feux()  # un prioritaire a pu changer un feu
        self.actualiser_statistiques()

    def retirer_vehicule_arrive(self, vehicule):
        self.vehicules_arrives += 1
        self.temps_total_trajets += self.temps_actif - vehicule.debut_trajet
        self.nombre_trajets += 1
        if vehicule == self.vehicule_selectionne:
            self.deselectionner_vehicule()
        self.scene.removeItem(vehicule.graphique)
        self.transitions.pop(vehicule, None)
        self.gyrophares.pop(vehicule, None)
        if not self.gyrophares:
            self.timer_gyrophare.stop()


# QApplication gère la boucle d'événements de Qt (clics, minuteries, dessin).
# app.exec() tourne jusqu'à la fermeture de la fenêtre.
app = QApplication(sys.argv)
fenetre = FenetrePrincipale()
fenetre.show()
sys.exit(app.exec())
