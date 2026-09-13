from math import *
import json # On importe json pour simplement tester les graphes, pour avoir un format plus lisible

class Graphes:
    """Classe maitresse, elle permet d'initialiser un graphe"""
    def __init__(self):
        self.noeuds = {}
        self.aretes = {}

    def ajouter_noeud(self, noeud):
        """Ajouter un noeud au graphe"""
        self.noeuds.update({noeud: noeud})

    def ajouter_arete(self, depart, arrivee, poids):
        """Ajouter un lien entre deux noeud existant
        - Si un des noeud donné n'existe pas, il sera demandé de les créer
        - Si ils existent, alors l'opération pourra aboutir
        """
        if depart not in self.noeuds:
            return f"le noeud {depart} n'existe pas, merci de le créer"
        elif arrivee not in self.noeuds:
            return f"le noeud {arrivee} n'existe pas, merci de le créer"
        else:
            if depart not in self.aretes:
                self.aretes[depart] = {}
            if arrivee not in self.aretes:
                self.aretes[arrivee] = {}

            self.aretes[depart].update({arrivee: poids})
            self.aretes[arrivee].update({depart: poids})

test = Graphes()
test.ajouter_noeud('A')
test.ajouter_noeud('B')
test.ajouter_noeud('C')
test.ajouter_arete('A', 'B', 15)
test.ajouter_arete('B', 'C', 7)
test.ajouter_arete('C', 'A', 5)
print(json.dumps(test.noeuds, indent=4))
print(json.dumps(test.aretes, indent=4))