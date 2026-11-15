"""Un véhicule et sa progression le long de son chemin.

Le véhicule ne s'occupe pas de l'affichage : il retient seulement sur quelle
route il roule et quelle proportion de cette route il a parcourue.
C'est interface.py qui transforme cela en position à l'écran.
"""

from dijkstra import dijkstra

DUREE_TICK = 0.02  # secondes entre deux ticks (minuterie de 20 ms dans interface.py)


class Vehicule:

    def __init__(self, graphe, depart, vitesse, destination, est_urgent=False):
        self.destination = destination
        self.vitesse = vitesse  # en pixels par seconde
        self.est_urgent = est_urgent
        # Le chemin complet est calculé une seule fois, à la création.
        self.chemin = dijkstra(graphe, depart, destination)
        if self.chemin is None:
            raise ValueError("Aucun chemin ne relie le départ à la destination.")
        if len(self.chemin) < 2:
            raise ValueError("Le départ et la destination doivent être différents.")

        # Route actuelle : de self.depart vers self.arrivee.
        self.index_chemin = 0
        self.depart = self.chemin[0]
        self.arrivee = self.chemin[1]
        # Proportion de la route parcourue : 0 = début, 1 = bout.
        self.avancement = 0

    def est_sur_derniere_route(self):
        """Vrai si la route actuelle mène directement à la destination.

        Sur cette route, le feu du dernier nœud ne concerne pas le véhicule :
        il s'arrête à destination, il ne traverse pas le carrefour.
        """
        return self.arrivee == self.destination

    def avancer(self, graphe, longueur_route):
        """Fait avancer le véhicule d'un tick (20 ms).

        longueur_route : longueur en pixels de la route actuelle.
        Renvoie "en cours", "attends feu" ou "arrive".
        """
        # Distance parcourue pendant un tick, convertie en proportion de la route.
        # Exemple : 60 px/s pendant 0,02 s = 1,2 px ; sur une route de 120 px, +0.01.
        # Une route deux fois plus longue prend donc deux fois plus de temps.
        self.avancement += self.vitesse * DUREE_TICK / max(longueur_route, 1)
        derniere_route = self.est_sur_derniere_route()

        # Un véhicule prioritaire, à 70 % de la route, fait passer au vert
        # le feu qui est devant lui.
        if self.est_urgent and self.avancement >= 0.7 and not derniere_route:
            if not graphe.est_vert(self.arrivee, self.depart):
                phases = graphe.noeuds[self.arrivee]["phases"]
                for index, phase in enumerate(phases):
                    if self.depart in phase:
                        graphe.changer_phase(self.arrivee, index)

        if self.avancement < 1:
            return "en cours"

        # Bout de la route atteint : feu rouge -> on attend.
        if not derniere_route and not graphe.est_vert(self.arrivee, self.depart):
            self.avancement = 1
            return "attends feu"

        # On passe à la route suivante (en gardant le surplus d'avancement).
        if derniere_route:
            return "arrive"
        self.avancement -= 1
        self.index_chemin += 1
        self.depart = self.arrivee
        self.arrivee = self.chemin[self.index_chemin + 1]
        return "en cours"
