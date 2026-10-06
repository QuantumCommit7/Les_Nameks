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

    def avancer(self, graphe):
        self.avancement += self.vitesse  * (20 / 300)
        if self.est_urgent and self.avancement >= 0.7:
            if graphe.est_vert(self.arrivee, self.depart) == False:
                phases = graphe.noeuds[self.arrivee]["phases"]
                index_trouve = None
                i = 0
                for sous_liste in phases:
                    if self.depart in sous_liste:
                        index_trouve = i
                    i = i + 1
                if index_trouve is not None:
                    graphe.changer_phase(self.arrivee, index_trouve)

        if self.avancement >= 1:
            situation = graphe.est_vert(self.arrivee, self.depart)
            if situation:
                self.avancement -= 1
                self.depart = self.arrivee
                self.index_chemin += 1
                if self.index_chemin + 1 >= len(self.chemin):
                    return "arrive"
                self.arrivee = self.chemin[self.index_chemin + 1]
                return "en cours"
            else:
                self.avancement =  1
                return "attends feu"
        return "en cours"

