"""Recherche d'itinéraire dans le graphe routier du simulateur."""

from graphes import *
from math import inf # inportation de l'infini pour définir dans dijkstra la distance a l'initialisaton du nœud

def dijkstra(graph, start, stop):
    """
    Recherche un chemin de poids minimal entre deux nœuds.

    Args:
        graph: Graphe contenant les nœuds et les routes pondérées.
        start: Nom du nœud de départ.
        stop: Nom du nœud d'arrivée.

    Returns:
        La liste des nœuds du départ à l'arrivée, ou ``None`` si un
        nœud n'existe pas ou si aucun chemin n'est disponible.

    L'algorithme suppose que les poids des routes sont non négatifs.
    """
    if start not in graph.noeuds or stop not in graph.noeuds:
        return None

    if start == stop:
        return [start]

    # Pour chaque nœud, mémoriser le meilleur coût connu et son précédent.
    detail = {}
    plus_proche = None
    for elt in graph.noeuds:
        if elt == start:
            detail[elt] = {"distance" : 0, "precedent" : None, "traité" : False}
        else:
            detail[elt] = {"distance" : inf, "precedent" : None, "traité" : False}
    while True:
        plus_proche = None
        # Choisir le nœud non traité dont la distance provisoire est la plus petite.
        for elt in detail:
            if detail[elt]["traité"] == True:
                pass
            else:
                if plus_proche == None:
                    plus_proche = elt
                if detail[elt]["distance"] <= detail[plus_proche]["distance"]:
                    plus_proche = elt
        if plus_proche is None:
            break

        if detail[plus_proche]["distance"] == inf:
            break

        detail[plus_proche]["traité"] = True

        if plus_proche == stop:
            break

        # Vérifier si passer par le nœud choisi améliore le coût de ses voisins.
        for voisin in graph.aretes.get(plus_proche, {}):
            distance = detail[plus_proche]["distance"] + graph.aretes[plus_proche][voisin]
            if distance < detail[voisin]["distance"]:
                detail[voisin]["distance"] = distance
                detail[voisin]["precedent"] = plus_proche

    if detail[stop]["distance"] == inf:
        return None

    # Reconstituer le trajet en remontant les précédents depuis l'arrivée.
    chemin = []
    actuel = stop
    while actuel != start:
        chemin.append(actuel)
        actuel = detail[actuel]["precedent"]
    chemin.append(actuel)
    chemin.reverse()
    return chemin
