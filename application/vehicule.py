from dijkstra import *

class Vehicule:
    def __init__(self, graphe,  depart, vitesse, destination, avancement=0, est_urgent=False):
        self.graphe = graphe
        self.depart = depart
        self.avancement = avancement
        self.destination = destination
        self.est_urgent = est_urgent
        self.vitesse = vitesse
        self.chemin = dijkstra(graphe, depart, destination)
        self.index_chemin = 0
        self.arrivee = self.chemin[self.index_chemin + 1]

    def avancer(self):
        self.avancement += self.vitesse
        if self.avancement >= 1:
            self.avancement -= 1
            self.depart = self.arrivee
            self.index_chemin += 1
            if self.index_chemin + 1 >= len(self.chemin):
                return "arrive"
            self.arrivee = self.chemin[self.index_chemin + 1]
        return "en cours"