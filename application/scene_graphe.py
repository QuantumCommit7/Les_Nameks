"""Dessin du réseau et gestion de la souris (nœuds, routes, feux)."""

import math

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import QGraphicsScene, QInputDialog, QMessageBox, QMenu

RAYON_NOEUD = 15
DECALAGE_VOIES = 8  # écart en pixels entre l'axe de la route et chaque voie
# Couleur des textes. Sans elle, Qt utilise la couleur du thème Windows
# (blanc en thème sombre), illisible sur le fond clair.
COULEUR_TEXTE = QColor("#263238")


def decalage_perpendiculaire(x1, y1, x2, y2):
    """Petit vecteur perpendiculaire à la route, pour placer les deux voies.

    (-dy, dx) est perpendiculaire à (dx, dy). On le divise par la longueur
    pour que l'écart soit le même sur toutes les routes.
    """
    dx, dy = x2 - x1, y2 - y1
    longueur = math.hypot(dx, dy)
    if longueur == 0:
        return 0, 0
    return -dy / longueur * DECALAGE_VOIES, dx / longueur * DECALAGE_VOIES


def formater_distance(metres):
    """Texte affiché sur une route : 500 -> "500 m", 1200 -> "1,2 km".

    Les distances sont toujours enregistrées en mètres ; au-delà de 1 000 m,
    on les affiche en kilomètres pour qu'elles restent faciles à lire.
    """
    if metres >= 1000:
        texte = f"{round(metres / 1000, 2):g} km"  # :g retire les zéros inutiles (1.50 -> 1.5)
    else:
        texte = f"{round(metres, 2):g} m"
    return texte.replace(".", ",")  # virgule décimale à la française


def cle_arete(a, b):
    """A-B et B-A désignent la même route : clé ("A", "B") dans les deux cas."""
    return tuple(sorted([a, b]))


class SceneGraphe(QGraphicsScene):
    """Le modèle (self.graphe) contient les données ; la scène contient les dessins.

    Les dictionnaires ci-dessous font le lien entre les deux.
    """

    def __init__(self, graphe):
        super().__init__()
        self.fenetre = None  # FenetrePrincipale, renseignée par interface.py
        self.setBackgroundBrush(QBrush(QColor("#eef3f1")))
        self.reinitialiser(graphe)

    def reinitialiser(self, graphe):
        """Efface tous les dessins et repart du graphe donné."""
        self.clear()
        self.graphe = graphe
        self.positions = {}        # nom du nœud -> (x, y)
        self.elements_noeuds = {}  # nom du nœud -> {"cercle": ..., "texte": ...}
        self.cercles = {}          # objet dessiné -> nom du nœud (pour les clics)
        self.lignes_aretes = {}    # ("A", "B") -> [voie 1, voie 2]
        self.textes_poids = {}     # ("A", "B") -> texte du poids
        self.feux = {}             # carrefour -> {voisin: {"graphique": pastille, "groupe": 0 ou 1}}
        self.noeud_en_attente = None  # 1er nœud cliqué pour créer une route
        self.mode_ajout_noeud = False
        self.noeud_a_deplacer = None
        self.deplacement_en_cours = False

    def afficher_message(self, texte):
        if self.fenetre is not None:
            self.fenetre.statusBar().showMessage(texte, 3000)

    # ---------------- Souris (méthodes appelées automatiquement par Qt) ----------------

    def mousePressEvent(self, event):
        position = event.scenePos()
        item = self.itemAt(position, self.views()[0].transform())  # objet sous la souris

        # Clic droit sur un nœud : menu « Modifier le nom / Supprimer ».
        if event.button() == Qt.MouseButton.RightButton and item in self.cercles:
            self.afficher_menu_noeud(self.cercles[item], event.screenPos())
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return

        # Clic sur un véhicule (ou sur son gyrophare) : on le sélectionne.
        if self.fenetre is not None and item is not None:
            for vehicule in self.fenetre.vehicules:
                if item == vehicule.graphique or vehicule.graphique.isAncestorOf(item):
                    self.fenetre.selectionner_vehicule(vehicule)
                    return

        # Clic sur un nœud : déplacement ou simple clic ? On le saura au relâchement.
        if item in self.cercles:
            self.noeud_a_deplacer = self.cercles[item]
            self.deplacement_en_cours = False
        elif self.mode_ajout_noeud:
            self.mode_ajout_noeud = False
            self.creer_noeud(position.x(), position.y())

    def mouseMoveEvent(self, event):
        if self.noeud_a_deplacer is not None:
            self.deplacement_en_cours = True  # la souris a bougé : ce n'est plus un clic
            self.deplacer_noeud(self.noeud_a_deplacer, event.scenePos().x(), event.scenePos().y())

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self.noeud_a_deplacer is None:
            return
        nom = self.noeud_a_deplacer
        clic_simple = not self.deplacement_en_cours
        self.noeud_a_deplacer = None
        if clic_simple:
            self.gerer_clic_sur_noeud(nom)

    def gerer_clic_sur_noeud(self, nom):
        """Deux clics sur deux nœuds = création d'une route entre eux."""
        if self.noeud_en_attente is None:
            self.noeud_en_attente = nom
            self.afficher_message("Sélectionnez le second nœud")
            return

        depart, self.noeud_en_attente = self.noeud_en_attente, None
        if depart == nom:
            return
        # Distance : valeur par défaut 1, minimum 0,01 (Dijkstra exige des poids positifs), 2 décimales.
        distance, valide = QInputDialog.getDouble(None, "Longueur de la route", "Distance :", 1, 0.01, 1000000, 2)
        if not valide:
            return
        unite, valide = QInputDialog.getItem(None, "Unité", "Unité de la distance :", ["m", "km"], 0, False)
        if not valide:
            return
        # On enregistre toujours en mètres : Dijkstra compare ainsi des valeurs dans la même unité.
        metres = distance * 1000 if unite == "km" else distance
        self.graphe.ajouter_arete(depart, nom, metres)
        self.dessiner_arete(depart, nom)
        self.afficher_message("Route créée")

    # ---------------- Édition des nœuds ----------------

    def activer_ajout_noeud(self):
        """Bouton « Ajouter un nœud » : le prochain clic dans le vide crée un nœud."""
        self.mode_ajout_noeud = True
        self.noeud_en_attente = None
        self.afficher_message("Cliquez dans le graphe pour placer un nœud")

    def creer_noeud(self, x, y):
        nom, valide = QInputDialog.getText(None, "Nouveau nœud", "Nom du nœud :")
        if not valide or nom == "" or nom in self.graphe.noeuds:
            return
        self.graphe.ajouter_noeud(nom)
        self.dessiner_noeud(nom, x, y)
        self.afficher_message("Nœud créé")

    def afficher_menu_noeud(self, nom, position):
        menu = QMenu()
        action_modifier = menu.addAction("Modifier le nom")
        action_supprimer = menu.addAction("Supprimer")
        action = menu.exec(position)  # attend le choix de l'utilisateur
        if action == action_modifier:
            self.modifier_nom_noeud(nom)
        elif action == action_supprimer:
            self.supprimer_noeud(nom)

    def vehicules_presents(self, action):
        """Protection : les chemins des véhicules contiennent des noms de nœuds.

        Renommer ou supprimer un nœud pendant qu'ils roulent casserait leurs chemins.
        """
        if self.fenetre is not None and self.fenetre.vehicules:
            QMessageBox.warning(self.fenetre, "Modification impossible",
                                f"Retirez d'abord tous les véhicules avant de {action} un nœud.")
            return True
        return False

    def modifier_nom_noeud(self, ancien):
        if self.vehicules_presents("renommer"):
            return
        nouveau, valide = QInputDialog.getText(None, "Modifier le nom", "Nouveau nom :", text=ancien)
        if not valide or nouveau == "" or nouveau in self.graphe.noeuds:
            return
        self.graphe.renommer_noeud(ancien, nouveau)

        self.positions[nouveau] = self.positions.pop(ancien)
        elements = self.elements_noeuds.pop(ancien)
        self.elements_noeuds[nouveau] = elements
        self.cercles[elements["cercle"]] = nouveau
        self.cercles[elements["texte"]] = nouveau
        elements["texte"].setPlainText(nouveau)
        self.placer_noeud(nouveau)
        self.noeud_en_attente = None
        self.redessiner_routes_et_feux()

    def supprimer_noeud(self, nom):
        if self.vehicules_presents("supprimer"):
            return
        self.graphe.supprimer_noeud(nom)
        elements = self.elements_noeuds.pop(nom)
        for item in elements.values():
            self.removeItem(item)
            del self.cercles[item]
        del self.positions[nom]
        if self.noeud_en_attente == nom:
            self.noeud_en_attente = None
        self.redessiner_routes_et_feux()

    def deplacer_noeud(self, nom, x, y):
        """Déplace un nœud et tout ce qui en dépend : routes, feux, véhicules."""
        self.positions[nom] = (x, y)
        self.placer_noeud(nom)
        for voisin in self.graphe.aretes.get(nom, {}):
            self.dessiner_arete(nom, voisin)
        self.redessiner_feux()
        if self.fenetre is not None:
            self.fenetre.mettre_a_jour_positions_vehicules()
            self.fenetre.mettre_a_jour_feux()

    # ---------------- Dessin ----------------

    def centrer_texte(self, texte, x, y):
        rect = texte.boundingRect()
        texte.setPos(x - rect.width() / 2, y - rect.height() / 2)

    def dessiner_noeud(self, nom, x, y):
        cercle = self.addEllipse(0, 0, 0, 0)
        cercle.setBrush(QBrush(QColor("lightblue")))
        texte = self.addText(nom)
        texte.setDefaultTextColor(COULEUR_TEXTE)
        texte.setAcceptedMouseButtons(Qt.MouseButton.NoButton)  # le clic passe au cercle
        # ZValue = ordre d'empilement : routes 1, nœuds 2, textes 3 et 4.
        cercle.setZValue(2)
        texte.setZValue(3)
        self.cercles[cercle] = nom
        self.cercles[texte] = nom
        self.elements_noeuds[nom] = {"cercle": cercle, "texte": texte}
        self.positions[nom] = (x, y)
        self.placer_noeud(nom)

    def placer_noeud(self, nom):
        """Place le cercle et le texte d'un nœud sur sa position actuelle."""
        x, y = self.positions[nom]
        r = RAYON_NOEUD
        self.elements_noeuds[nom]["cercle"].setRect(x - r, y - r, 2 * r, 2 * r)
        self.centrer_texte(self.elements_noeuds[nom]["texte"], x, y)

    def dessiner_arete(self, depart, arrivee):
        """Dessine (ou déplace, si elle existe déjà) une route : deux voies et son poids."""
        cle = cle_arete(depart, arrivee)
        x1, y1 = self.positions[depart]
        x2, y2 = self.positions[arrivee]
        longueur = math.hypot(x2 - x1, y2 - y1)
        if longueur == 0:
            return

        # Les lignes s'arrêtent au bord des cercles, pas en leur centre.
        bord_x = (x2 - x1) / longueur * RAYON_NOEUD
        bord_y = (y2 - y1) / longueur * RAYON_NOEUD
        dec_x, dec_y = decalage_perpendiculaire(x1, y1, x2, y2)

        # Première fois : on crée les deux lignes et le texte du poids.
        if cle not in self.lignes_aretes:
            self.lignes_aretes[cle] = [self.addLine(0, 0, 0, 0), self.addLine(0, 0, 0, 0)]
            for ligne in self.lignes_aretes[cle]:
                ligne.setZValue(1)
            texte = self.addText("")
            texte.setDefaultTextColor(COULEUR_TEXTE)
            texte.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            texte.setZValue(4)
            self.textes_poids[cle] = texte

        # Une voie de chaque côté de l'axe de la route (sens = +1 puis -1).
        for ligne, sens in zip(self.lignes_aretes[cle], (1, -1)):
            ligne.setLine(x1 + bord_x + sens * dec_x, y1 + bord_y + sens * dec_y,
                          x2 - bord_x + sens * dec_x, y2 - bord_y + sens * dec_y)

        # La distance est écrite en gras sur une petite étiquette blanche, pour rester
        # lisible par-dessus les lignes de la route (mise en forme façon HTML).
        texte = self.textes_poids[cle]
        distance = formater_distance(self.graphe.aretes[depart][arrivee])
        texte.setHtml(f"<span style='background-color: white; font-weight: bold;'>&nbsp;{distance}&nbsp;</span>")
        self.centrer_texte(texte, (x1 + x2) / 2, (y1 + y2) / 2)

    def redessiner_routes_et_feux(self):
        """Efface toutes les routes puis les recrée depuis le modèle (après renommage/suppression)."""
        for cle in self.lignes_aretes:
            for ligne in self.lignes_aretes[cle]:
                self.removeItem(ligne)
            self.removeItem(self.textes_poids[cle])
        self.lignes_aretes = {}
        self.textes_poids = {}
        for depart in self.graphe.aretes:
            for arrivee in self.graphe.aretes[depart]:
                if depart < arrivee:  # chaque route est stockée deux fois : on la dessine une fois
                    self.dessiner_arete(depart, arrivee)
        self.redessiner_feux()

    def redessiner_feux(self):
        for noeud in list(self.feux):
            self.effacer_feu(noeud)
        for noeud in self.graphe.noeuds:
            if self.graphe.a_un_feu(noeud):
                self.dessiner_feu(noeud, self.graphe.noeuds[noeud]["phases"])

    def effacer_feu(self, noeud):
        for feu in self.feux.pop(noeud, {}).values():
            self.removeItem(feu["graphique"])

    def dessiner_feu(self, noeud, groupes):
        """Une pastille par route du carrefour, placée au quart de la route."""
        # Si le carrefour avait déjà un feu, on retire ses anciennes pastilles.
        self.effacer_feu(noeud)
        self.feux[noeud] = {}
        x, y = self.positions[noeud]
        for groupe, voisins in enumerate(groupes):
            for voisin in voisins:
                xv, yv = self.positions[voisin]
                feu_x = x + (xv - x) * 0.25
                feu_y = y + (yv - y) * 0.25
                pastille = self.addEllipse(feu_x - 6, feu_y - 6, 12, 12)
                # Au départ, la phase 0 est verte.
                pastille.setBrush(QBrush(QColor("green" if groupe == 0 else "red")))
                self.feux[noeud][voisin] = {"graphique": pastille, "groupe": groupe}
