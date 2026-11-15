"""Modèle d'un véhicule et progression le long de son itinéraire.

Un véhicule ne s'occupe pas de l'affichage : il retient seulement sa position
« logique » (sur quelle route il roule et quelle proportion de cette route il a
parcourue). C'est interface.py qui transforme cette position en coordonnées
à l'écran.
"""

from dijkstra import *


class Vehicule:
    """Véhicule associé à un chemin calculé dans le graphe courant."""

    def __init__(self, graphe,  depart, vitesse, destination, avancement=0, est_urgent=False):
        self.graphe = graphe
        # depart et arrivee désignent la route sur laquelle le véhicule roule
        # en ce moment (de depart vers arrivee), et non le trajet complet.
        self.depart = depart
        # Proportion de la route actuelle déjà parcourue : 0 = début, 1 = bout.
        self.avancement = avancement
        self.destination = destination
        self.est_urgent = est_urgent
        self.vitesse = vitesse
        # Le chemin complet est calculé une seule fois, à la création.
        # Exemple : ['A', 'B', 'G', 'H'] pour aller de A à H.
        self.chemin = dijkstra(graphe, depart, destination)

        # On refuse de créer un véhicule qui ne pourrait pas rouler :
        # l'interface attrape cette erreur et affiche un message.
        if self.chemin is None:
            raise ValueError("Aucun chemin ne relie le départ à la destination.")

        if len(self.chemin) < 2:
            raise ValueError("Le départ et la destination doivent être différents.")

        # index_chemin est la position de self.depart dans self.chemin.
        self.index_chemin = 0
        self.arrivee = self.chemin[self.index_chemin + 1]

    def est_sur_derniere_route(self):
        """Vrai si la route actuelle mène directement à la destination.

        Sur cette dernière route, le feu du nœud d'arrivée ne concerne pas le
        véhicule : il termine son trajet en atteignant le nœud, il ne traverse
        pas le carrefour. Dijkstra ne renvoie jamais deux fois le même nœud,
        donc ``arrivee == destination`` n'arrive que sur la dernière route.
        """
        return self.arrivee == self.destination

    def avancer(self, graphe):
        """Fait progresser le véhicule et renvoie son état au tick courant.

        ``avancement`` est une proportion de l'arête : 0 correspond au départ
        et 1 à la ligne d'arrêt. Le résultat indique si le véhicule continue,
        attend le feu ou a terminé son trajet.
        """
        # Le facteur convertit la vitesse choisie en progression par tick (20 ms).
        # Exemple : vitesse 0.1 -> 0.1 * 20/300 ≈ 0.0067 par tick, soit environ
        # 150 ticks (3 secondes) pour parcourir une route. Toutes les routes se
        # parcourent donc dans le même temps, quelle que soit leur longueur.
        self.avancement += self.vitesse  * (20 / 300)

        # Règle du véhicule prioritaire : à 70 % de la route, s'il voit un feu
        # rouge devant lui, il fait passer le carrefour dans la phase qui lui
        # donne le vert. Sur la dernière route, il n'y a pas de carrefour à
        # traverser, donc rien à demander.
        if self.est_urgent and self.avancement >= 0.7 and not self.est_sur_derniere_route():
            if graphe.est_vert(self.arrivee, self.depart) == False:
                # Le véhicule prioritaire demande la phase qui autorise sa voie.
                phases = graphe.noeuds[self.arrivee]["phases"]
                index_trouve = None
                i = 0
                # On cherche dans quelle phase se trouve la route d'où il vient.
                for sous_liste in phases:
                    if self.depart in sous_liste:
                        index_trouve = i
                    i = i + 1
                if index_trouve is not None:
                    graphe.changer_phase(self.arrivee, index_trouve)

        # Le véhicule a atteint le bout de sa route.
        if self.avancement >= 1:
            # Il peut passer si c'est la fin de son trajet (le feu ne le concerne
            # pas) ou si le feu est vert pour la route d'où il vient.
            derniere_route = self.est_sur_derniere_route()
            if derniere_route or graphe.est_vert(self.arrivee, self.depart):
                # On garde le surplus d'avancement pour ne pas perdre de distance,
                # puis on passe à la route suivante du chemin.
                self.avancement -= 1
                self.depart = self.arrivee
                self.index_chemin += 1
                if self.index_chemin + 1 >= len(self.chemin):
                    return "arrive"
                self.arrivee = self.chemin[self.index_chemin + 1]
                return "en cours"
            else:
                # Feu rouge : on bloque le véhicule exactement au bout de la route.
                self.avancement =  1
                return "attends feu"
        return "en cours"
