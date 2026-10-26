import json
import sys
import math
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from reseau.client import envoyer_message
try:
    from carte import PanneauCarte, RAISON_CARTE_INDISPONIBLE
except ImportError as erreur_carte:
    PanneauCarte = None
    RAISON_CARTE_INDISPONIBLE = (f"carte.py est introuvable ou n'est pas à jour ({erreur_carte}).\n"
                                 "Copiez la dernière version de carte.py dans le dossier de interface.py.")

from graphes import Graphes
from graphe_test import DENSITES_TEST, NOEUDS_TEST, ARETES_TEST, FEUX_TEST
from PyQt6.QtWidgets import QApplication, QInputDialog, QMainWindow, QGraphicsScene, QGraphicsView, QPushButton, QWidget, QVBoxLayout, QHBoxLayout, QGraphicsEllipseItem, QMenu, QMessageBox, QTabWidget, QLabel
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QPen
from fond_carte import FondCarte
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

        self.bouton_lieu = QPushButton("Choisir le lieu")
        self.bouton_lieu.clicked.connect(self.choisir_lieu)
        self.scene.fond.lieux_trouves.connect(self.lieux_recus)
        self.scene.fond.erreur_recherche.connect(self.erreur_lieu)

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
        layout_boutons.addWidget(self.bouton_lieu)
        layout_boutons.addWidget(self.bouton_graphe_test)
        layout_boutons.addWidget(self.bouton_simulation)

        layout.addLayout(layout_boutons)

        self.onglets = QTabWidget()
        self.onglets.addTab(self.view, "Schéma")
        self.compteur_carte = 0
        if PanneauCarte is not None:
            self.panneau_carte = PanneauCarte()
            self.onglets.addTab(self.panneau_carte, "Carte")
        else:
            self.panneau_carte = None
            indisponible = QLabel("La carte est indisponible.\n\n" + (RAISON_CARTE_INDISPONIBLE or "Raison inconnue."))
            indisponible.setWordWrap(True)
            indisponible.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.onglets.addTab(indisponible, "Carte")
        self.onglets.currentChanged.connect(self.onglet_change)
        layout.addWidget(self.onglets)

        conteneur.setLayout(layout)

        self.setCentralWidget(conteneur)

        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)

        self.timer_feux = QTimer()
        self.timer_feux.timeout.connect(self.changer_feux)

        self.timer_statistiques = QTimer()
        self.timer_statistiques.timeout.connect(self.envoyer_statistiques)

    def choisir_lieu(self):
        texte, valide = QInputDialog.getText(
            self,
            "Choisir le lieu",
            "Ville ou adresse :"
        )

        if valide == False or texte.strip() == "":
            return

        self.bouton_lieu.setEnabled(False)
        self.scene.fond.chercher_lieu(texte.strip())

    def lieux_recus(self, lieux):
        self.bouton_lieu.setEnabled(True)

        if len(lieux) == 0:
            QMessageBox.information(self, "Choisir le lieu", "Aucun résultat pour cette recherche.")
            return

        if len(lieux) == 1:
            choix = lieux[0]
        else:
            noms = [lieu[0] for lieu in lieux]
            nom, valide = QInputDialog.getItem(
                self,
                "Choisir le lieu",
                "Plusieurs résultats :",
                noms,
                0,
                False
            )
            if valide == False:
                return
            choix = lieux[noms.index(nom)]

        nom, latitude, longitude = choix

        # Le lieu choisi est placé au centre de ce qu'on voit à l'écran.
        centre = self.view.mapToScene(self.view.viewport().rect().center())
        self.scene.fond.definir_centre(latitude, longitude, centre.x(), centre.y())
        self.view.viewport().update()
        print(f"Lieu choisi : {nom} ({latitude:.5f}, {longitude:.5f})")

        self.mettre_a_jour_carte(reconstruire=True)

    def erreur_lieu(self, message):
        self.bouton_lieu.setEnabled(True)
        QMessageBox.warning(self, "Choisir le lieu", f"Recherche impossible :\n{message}")

    def carte_visible(self):
        return self.panneau_carte is not None and self.onglets.currentWidget() is self.panneau_carte

    def onglet_change(self, index):
        self.mettre_a_jour_carte(reconstruire=True)

    def mettre_a_jour_carte(self, reconstruire=False):
        """reconstruire=True : le graphe a changé, on redessine la carte.
        Sinon : simple rafraîchissement des feux et des véhicules (appelé à chaque tick)."""
        if not self.carte_visible():
            return
        if reconstruire:
            self.panneau_carte.afficher_reseau(self.graphe, self.scene.positions, self.vehicules)
            return
        self.compteur_carte = (self.compteur_carte + 1) % 5     # la carte suit 1 tick sur 5 (10 fois par seconde)
        if self.compteur_carte == 0:
            self.panneau_carte.mettre_a_jour(self.graphe, self.vehicules)

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

        self.mettre_a_jour_carte(reconstruire=True)

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

        self.deselectionner_vehicule()

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

        self.mettre_a_jour_carte(reconstruire=True)

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
        vehicule.temps_debut_trajet_actif = self.obtenir_temps_simulation_actif()

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

        self.mettre_a_jour_carte()

    def changer_feux(self):
        if self.simulation_active == False:
            return

        self.feu_vert = not self.feu_vert
        self.mettre_a_jour_feux()

    def demarrer_pause(self):
        if self.simulation_active:
            self.actualiser_temps_simulation_actif()
            self.simulation_active = False
            self.bouton_simulation.setText("Démarrer")
            self.timer.stop()
            self.timer_feux.stop()
            self.timer_statistiques.stop()
        else:
            self.simulation_active = True
            self.dernier_instant_actif = time.monotonic()
            self.bouton_simulation.setText("Pause")
            self.timer.start(20)
            self.timer_feux.start(5000)
            self.timer_statistiques.start(5000)

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

    def vehicule_attend_au_feu(self, vehicule):
        return (
            vehicule.avancement >= 1
            and not self.graphe.est_vert(vehicule.arrivee, vehicule.depart)
        )

    def compter_vehicules_attente_feu(self):
        return sum(1 for vehicule in self.vehicules if self.vehicule_attend_au_feu(vehicule))

    def vehicule_bloque_par_un_autre(self, vehicule):
        for autre_vehicule in self.vehicules:
            if autre_vehicule == vehicule:
                continue

            meme_depart = autre_vehicule.depart == vehicule.depart
            meme_arrivee = autre_vehicule.arrivee == vehicule.arrivee
            devant = autre_vehicule.avancement > vehicule.avancement

            if meme_depart and meme_arrivee and devant:
                distance = autre_vehicule.avancement - vehicule.avancement
                if distance < self.distance_securite:
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

        temps_moyen = self.calculer_temps_moyen_trajet()
        vehicules_attente_feu = self.compter_vehicules_attente_feu()
        vehicules_bouchon = self.compter_vehicules_bouchon()
        print(
            f"Temps moyen trajet : {temps_moyen:.2f} s | "
            f"En attente au feu : {vehicules_attente_feu} | "
            f"En bouchon : {vehicules_bouchon}"
        )

        statistiques = {
            "type": "statistiques",
            "vehicules_actifs": len(self.vehicules),
            "vehicules_arrives": self.vehicules_arrives,
            "vehicules_prioritaires": sum(
                1 for vehicule in self.vehicules if vehicule.est_urgent
            ),
            "temps_moyen_trajet": temps_moyen,
            "vehicules_attente_feu": vehicules_attente_feu,
            "vehicules_bouchon": vehicules_bouchon,
        }
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

        self.actualiser_temps_simulation_actif()

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
                self.vehicules_arrives += 1
                duree_trajet = (
                    self.temps_simulation_actif - vehicule.temps_debut_trajet_actif
                )
                self.temps_total_trajets_termines += max(0.0, duree_trajet)
                self.nombre_trajets_termines += 1
                if vehicule == self.vehicule_selectionne:
                    self.deselectionner_vehicule()
                self.scene.removeItem(vehicule.graphique)

        self.vehicules = vehicules_encore_actifs

        while self.nombre_vehicules_voulu > 0 and len(self.vehicules) < self.nombre_vehicules_voulu:
            vehicule = self.creer_vehicule_aleatoire()
            if vehicule is None:
                break

        self.mettre_a_jour_carte()


app = QApplication(sys.argv)

fenetre = FenetrePrincipale()
fenetre.show()

sys.exit(app.exec())
