import json # On importe json pour simplement tester les graphes, pour avoir un format plus lisible

class Graphes:
    """Classe maitresse, elle permet d'initialiser un graphe"""
    def __init__(self):
        """
        Ce constructeur va créer deux dictionnaires vides
        le premier self.noeuds va serveur à ajouter les noeuds
        le second self.aretes va servir à créer les liens entre les noeuds
        """
        self.noeuds = {}
        self.aretes = {}

    def ajouter_noeud(self, noeud : str):
        """
        Cette methode va servir à créer un noeud dans notre instance de Graphes
        l'argument noeud doit être de type string, si le type est différent une erreur sera renvoyée
        Une seconde vérification aura lieu, elle vérifiera que le noeud donné n'existe pas déjà.
        Une fois toutes les vérifications passées, on update le dictionnaire pour ajouter une nouvelle entrée,
        qui aura comme valeur l'argument noeud.
        """
        if not isinstance(noeud, str):
            raise TypeError("Votre noeud n'est pas un string")
        if noeud in self.noeuds:
            raise ValueError("Ce noeud existe déjà")
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
        return None

    def definir_feu(self, noeud, phases):
        if noeud not in self.noeuds:
            raise ValueError("le noeud n'existe pas")
        self.noeuds[noeud] = {"phases": phases, "phase_active": 0}

    def est_vert(self, noeud, venant_de):
        if noeud not in self.noeuds:
            raise ValueError("le noeud n'existe pas")
        if not isinstance(self.noeuds[noeud], dict):
            return True
        phase_active = self.noeuds[noeud]["phase_active"]
        directions_autorises = self.noeuds[noeud]["phases"][phase_active]
        return venant_de in directions_autorises

    def changer_phase(self, noeud, nouvelle_phase):
        if noeud not in self.noeuds:
            raise ValueError("le noeud n'existe pas")
        if not isinstance(self.noeuds[noeud], dict):
            raise TypeError(f"le noeud {noeud} n'a pas de feu configuré")
        if nouvelle_phase < 0 or nouvelle_phase > len(self.noeuds[noeud]["phases"]):
            raise ValueError("le nouvelle_phase n'est pas 0 ou 1")
        self.noeuds[noeud]["phase_active"] = nouvelle_phase
if __name__ == "__main__":
    test = Graphes() # on crée une instance de Graphes affectée à une variable test
    test.ajouter_noeud('A') # ajout de 'A'
    test.ajouter_noeud('B') # ajout de 'B'
    test.ajouter_noeud('C') # ajout de 'C'
    test.ajouter_arete('A', 'B', 15) # on crée un lien entre A et B avec un poid de 15
    test.ajouter_arete('B', 'C', 7) # on crée un lien entre B et C avec un poid de 7
    test.ajouter_arete('C', 'A', 5) # on crée un lien entre C et A avec un poid de 5
    test.definir_feu('A', [['B'], ['C']])
    print(test.est_vert('A', 'B'))
    print(test.est_vert('A', 'C'))
    test.changer_phase('A', 1)
    print(test.noeuds['A'])
    print(json.dumps(test.noeuds, indent=4)) # librairie json afin de lire avec plus de facilité le gros dictionnaire de dictionnaires
    print(json.dumps(test.aretes, indent=4))
