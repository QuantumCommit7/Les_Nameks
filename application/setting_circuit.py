from graphes import Graphes
from vehicule import Vehicule

circuit = Graphes()
circuit.ajouter_noeud('A')
circuit.ajouter_noeud('B')
circuit.ajouter_noeud('C')
circuit.ajouter_noeud('D')
circuit.ajouter_noeud('E')
circuit.ajouter_arete('A', 'B', 5)
circuit.ajouter_arete('A', 'C', 7)
circuit.ajouter_arete('C', 'D', 14)
circuit.ajouter_arete('A', 'E', 18)
circuit.ajouter_arete('C', 'E', 3)
circuit.ajouter_arete('D', 'B', 5)

circuit.definir_feu('A', [['B'], ['C', 'E']])
circuit.definir_feu('B', [['A'], ['D']])
circuit.definir_feu('D', [['C'], ['B']])

voiture1 = Vehicule(circuit, 'A', 0.1, 'D')
voiture2 = Vehicule(circuit, 'D', 0.1, 'E', est_urgent=True)
voiture3 = Vehicule(circuit, 'C', 0.1, 'A')

vehicules = [voiture1, voiture2, voiture3]