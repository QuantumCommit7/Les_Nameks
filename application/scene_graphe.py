import math

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import QGraphicsScene, QInputDialog, QMessageBox, QMenu

from graphes import Graphes

class SceneGraphe(QGraphicsScene):
    """Gère les éléments graphiques et les interactions avec le graphe.

    Le modèle (``self.graphe``) contient les données ; la scène contient les
    objets dessinés. Les dictionnaires ci-dessous font le lien entre les deux.
    """

    def __init__(self, graphe: Graphes):
        super().__init__()
        self.graphe = graphe
        # Objet graphique (cercle ou texte) -> nom du nœud : sert à savoir
        # sur quel nœud l'utilisateur a cliqué.
        self.cercles = {}
        # Nom du nœud -> {"cercle": ..., "texte": ...}
        self.elements_noeuds = {}
        # Nom du nœud -> (x, y) dans la scène.
        self.positions = {}
        # ("A", "B") trié -> [ligne voie 1, ligne voie 2]
        self.lignes_aretes = {}
        # ("A", "B") trié -> texte affichant le poids
        self.textes_poids = {}
        # Écart en pixels entre l'axe de la route et chaque voie.
        self.decalage_voies = 8
        # Premier nœud cliqué quand on crée une route en deux clics.
        self.noeud_en_attente = None
        # Carrefour -> {voisin: {"graphique": pastille, "groupe": 0 ou 1}}
        self.feux = {}
        self.mode_ajout_noeud = False
        self.noeud_a_deplacer = None
        self.deplacement_en_cours = False
        # Référence vers FenetrePrincipale, renseignée par interface.py.
        self.fenetre = None
        self.setBackgroundBrush(QBrush(QColor("#eef3f1")))

    # ------------------------------------------------------------------
    # Événements souris (appelés automatiquement par Qt)
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        """Dirige le clic vers le menu, la sélection ou le déplacement d'un objet."""
        position = event.scenePos()
        x = position.x()
        y = position.y()

        # Objet situé sous la souris (None si on clique dans le vide).
        item_clique = self.itemAt(position, self.views()[0].transform())

        # Clic droit sur un nœud : menu « Modifier le nom / Supprimer ».
        if event.button() == Qt.MouseButton.RightButton:
            if item_clique in self.cercles:
                nom_clique = self.cercles[item_clique]
                self.afficher_menu_noeud(nom_clique, event.screenPos())
                return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        # Clic gauche sur un véhicule (ou sur son gyrophare) : on le sélectionne.
        if self.fenetre is not None:
            for vehicule in self.fenetre.vehicules:
                if item_clique is not None and (
                    item_clique == vehicule.graphique
                    or vehicule.graphique.isAncestorOf(item_clique)
                ):
                    self.fenetre.selectionner_vehicule(vehicule)
                    return

        # Clic gauche sur un nœud : il peut s'agir d'un déplacement ou d'un
        # simple clic. On ne le saura qu'au relâchement (mouseReleaseEvent).
        if item_clique in self.cercles:
            nom_clique = self.cercles[item_clique]
            self.noeud_a_deplacer = nom_clique
            self.deplacement_en_cours = False
            return

        # Clic dans le vide après « Ajouter un nœud ».
        if self.mode_ajout_noeud:
            self.creer_noeud(x, y)
            self.mode_ajout_noeud = False


    def mouseMoveEvent(self, event):
        """Déplace le nœud sélectionné et recalcule ses routes."""
        if self.noeud_a_deplacer is None:
            return

        position = event.scenePos()
        # La souris a bougé : ce n'est plus un simple clic.
        self.deplacement_en_cours = True

        self.deplacer_noeud(
            self.noeud_a_deplacer,
            position.x(),
            position.y()
        )

    def mouseReleaseEvent(self, event):
        """Interprète un clic simple sans le confondre avec un glissement."""
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
        """Utilise deux clics simples sur des nœuds pour créer une route."""
        # Premier clic : on mémorise le nœud de départ.
        if self.noeud_en_attente is None:
            self.noeud_en_attente = nom
            print(f"{nom} sélectionné comme départ, cliquez sur le nœud d'arrivée")
            if self.fenetre is not None:
                self.fenetre.statusBar().showMessage("Sélectionnez le second nœud", 3000)
            return

        # Second clic : on crée la route entre les deux nœuds.
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

        # Dijkstra ne fonctionne qu'avec des poids positifs.
        if poids <= 0:
            print("Impossible d'avoir une ponderation negative")
            return

        self.graphe.ajouter_arete(depart, arrivee, poids)
        self.dessiner_arete(depart, arrivee)
        if self.fenetre is not None:
            self.fenetre.statusBar().showMessage("Route créée", 3000)
        print(self.graphe.aretes)

    # ------------------------------------------------------------------
    # Outils de calcul
    # ------------------------------------------------------------------

    def cle_arete(self, depart, arrivee):
        """Clé unique d'une route : A-B et B-A donnent toutes deux ("A", "B")."""
        return tuple(sorted([depart, arrivee]))

    def calculer_decalage_perpendiculaire(self, x1, y1, x2, y2):
        """Calcule le décalage latéral qui sépare les deux voies d'une route.

        Le vecteur perpendiculaire est normalisé pour que l'écart reste
        constant quelle que soit la longueur de la route.
        """
        dx = x2 - x1
        dy = y2 - y1

        longueur = math.sqrt(dx * dx + dy * dy)

        if longueur == 0:
            return 0, 0

        # (-dy, dx) est perpendiculaire à (dx, dy) ; diviser par la longueur
        # donne un vecteur de longueur 1.
        decalage_x = -dy / longueur
        decalage_y = dx / longueur

        return (
            decalage_x * self.decalage_voies,
            decalage_y * self.decalage_voies
        )

    # ------------------------------------------------------------------
    # Édition des nœuds
    # ------------------------------------------------------------------

    def activer_ajout_noeud(self):
        """Le prochain clic dans le vide créera un nœud."""
        self.mode_ajout_noeud = True
        self.noeud_en_attente = None
        print("Cliquez dans le vide pour placer le nouveau noeud")
        if self.fenetre is not None:
            self.fenetre.statusBar().showMessage("Cliquez dans le graphe pour placer un nœud", 3000)

    def afficher_menu_noeud(self, nom, position):
        """Affiche le menu contextuel d'un nœud et exécute l'action choisie."""
        menu = QMenu()
        action_modifier = menu.addAction("Modifier le nom")
        action_supprimer = menu.addAction("Supprimer")

        # exec() bloque jusqu'au choix de l'utilisateur et renvoie l'action.
        action = menu.exec(position)

        if action == action_modifier:
            self.modifier_nom_noeud(nom)
        elif action == action_supprimer:
            self.supprimer_noeud(nom)

    def modifier_nom_noeud(self, ancien_nom):
        """Renomme un nœud dans le modèle puis dans la scène."""
        # Protection : les véhicules gardent des noms de nœuds dans leur chemin.
        # Renommer pendant qu'ils roulent rendrait ces chemins invalides.
        if self.fenetre is not None and self.fenetre.vehicules:
            QMessageBox.warning(
                self.fenetre,
                "Modification impossible",
                "Retirez d'abord tous les véhicules avant de renommer un nœud."
            )
            return

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

        # Mettre à jour les dictionnaires de la scène avec le nouveau nom.
        self.positions[nouveau_nom] = self.positions.pop(ancien_nom)
        self.elements_noeuds[nouveau_nom] = self.elements_noeuds.pop(ancien_nom)

        cercle = self.elements_noeuds[nouveau_nom]["cercle"]
        texte = self.elements_noeuds[nouveau_nom]["texte"]

        x, y = self.positions[nouveau_nom]

        self.cercles[cercle] = nouveau_nom
        self.cercles[texte] = nouveau_nom
        texte.setPlainText(nouveau_nom)
        self.mettre_a_jour_position_noeud(nouveau_nom, x, y)

        # Les clés des routes contiennent les noms : on redessine tout.
        self.noeud_en_attente = None
        self.redessiner_toutes_aretes()
        self.mettre_a_jour_feux_graphique()

    def supprimer_noeud(self, nom):
        """Supprime un nœud du modèle puis ses éléments graphiques."""
        # Même protection que pour le renommage.
        if self.fenetre is not None and self.fenetre.vehicules:
            QMessageBox.warning(
                self.fenetre,
                "Modification impossible",
                "Retirez d'abord tous les véhicules avant de supprimer un nœud."
            )
            return

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
        """Déplace un nœud et tout ce qui en dépend (routes, feux, véhicules)."""
        self.positions[nom] = (x, y)
        self.mettre_a_jour_position_noeud(nom, x, y)
        self.repositionner_aretes(nom)
        self.mettre_a_jour_feux_graphique()

        if self.fenetre is not None:
            self.fenetre.mettre_a_jour_positions_vehicules()
            self.fenetre.mettre_a_jour_feux()


    def mettre_a_jour_position_noeud(self, nom, x, y):
        """Replace le cercle et le texte d'un nœud, centrés sur (x, y)."""
        elements = self.elements_noeuds[nom]
        cercle = elements["cercle"]
        texte = elements["texte"]

        # Cercle de rayon 15 : le rectangle englobant commence à (x-15, y-15).
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

    # ------------------------------------------------------------------
    # Dessin des routes et des feux
    # ------------------------------------------------------------------

    def repositionner_aretes(self, nom):
        """Redessine les routes qui touchent un nœud déplacé."""
        if nom not in self.graphe.aretes:
            return

        for voisin in self.graphe.aretes[nom]:
            self.dessiner_arete(nom, voisin)

    def redessiner_toutes_aretes(self):
        """Efface toutes les routes dessinées puis les recrée depuis le modèle."""

        for cle in self.lignes_aretes:
            for ligne in self.lignes_aretes[cle]:
                self.removeItem(ligne)

        for cle in self.textes_poids:
            self.removeItem(self.textes_poids[cle])

        self.lignes_aretes = {}
        self.textes_poids = {}

        for depart in self.graphe.aretes:
            for arrivee in self.graphe.aretes[depart]:
                # Chaque route est stockée dans les deux sens : on ne la
                # dessine qu'une fois.
                if depart < arrivee:
                    self.dessiner_arete(depart, arrivee)

    def mettre_a_jour_feux_graphique(self):
        """Efface toutes les pastilles de feux puis les redessine."""
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
        """Demande un nom puis ajoute le nœud au modèle et à la scène."""
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
        if self.fenetre is not None:
            self.fenetre.statusBar().showMessage("Nœud créé", 3000)

    def dessiner_noeud(self, nom, x, y):
        """Crée le cercle et le texte d'un nœud."""
        cercle = self.addEllipse(
            x - 15,
            y - 15,
            30,
            30)
        cercle.setBrush(QBrush(QColor("lightblue")))
        # ZValue = ordre d'empilement : plus il est grand, plus l'objet est devant.
        # Routes = 1, nœuds = 2, textes = 3 et 4.
        cercle.setZValue(2)
        self.cercles[cercle] = nom

        self.positions[nom] = (x, y)

        texte = self.addText(nom)
        # Le texte laisse passer les clics vers le cercle situé dessous.
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
        """Dessine les deux voies et le poids de la route entre deux nœuds.

        Si la route est déjà dessinée, on déplace simplement ses lignes
        au lieu d'en créer de nouvelles.
        """
        cle = self.cle_arete(depart, arrivee)
        x1, y1 = self.positions[depart]
        x2, y2 = self.positions[arrivee]

        # Arrêter les lignes au bord des cercles des nœuds, pas en leur centre.
        rayon = 15

        dx = x2 - x1
        dy = y2 - y1

        distance = (dx ** 2 + dy ** 2) ** 0.5

        if distance == 0:
            return

        # Vecteur unitaire (longueur 1) dans la direction de la route.
        dx_norm = dx / distance
        dy_norm = dy / distance

        x1_bord = x1 + dx_norm * rayon
        y1_bord = y1 + dy_norm * rayon

        x2_bord = x2 - dx_norm * rayon
        y2_bord = y2 - dy_norm * rayon

        # Décaler les deux segments de part et d'autre de l'axe de la route.
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

        # Le poids est affiché au milieu de la route.
        poids = self.graphe.aretes[depart][arrivee]
        milieu_x = (x1 + x2) / 2
        milieu_y = (y1 + y2) / 2

        if cle in self.textes_poids:
            texte_poids = self.textes_poids[cle]
            texte_poids.setPlainText(str(poids))
        else:
            texte_poids = self.addText(str(poids))
            texte_poids.setDefaultTextColor(QColor("black"))
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
        """Dessine un indicateur coloré pour chaque direction des phases du feu."""
        x, y = self.positions[noeud]

        # Si ce carrefour avait déjà un feu (feu ajouté deux fois), on retire
        # d'abord ses anciennes pastilles. Sinon elles resteraient affichées
        # sans plus jamais changer de couleur.
        if noeud in self.feux:
            for ancien_feu in self.feux[noeud].values():
                self.removeItem(ancien_feu["graphique"])

        self.feux[noeud] = {}

        for groupe in range(2):

            for voisin in groupes[groupe]:

                xv, yv = self.positions[voisin]

                dx = xv - x
                dy = yv - y

                # La pastille est placée au quart de la route, côté carrefour.
                facteur = 0.25

                feu_x = x + dx * facteur
                feu_y = y + dy * facteur

                feu = self.addEllipse(
                    feu_x - 6,
                    feu_y - 6,
                    12,
                    12
                )
                # Couleur initiale : la phase 0 est active au départ.
                if groupe == 0:
                    feu.setBrush(QBrush(QColor("green")))
                else:
                    feu.setBrush(QBrush(QColor("red")))

                self.feux[noeud][voisin] = {
                    "graphique": feu,
                    "groupe": groupe
                }
