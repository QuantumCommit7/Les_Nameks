from graphes import *
from math import inf # inportation de l'infini pour définir dans dijkstra la distance a l'initialisaton du nœud

def dijkstra(graph, start, stop):
    """
    Fonction basée sur l'algorithme de dijkstra. Il va permettre de
    trouver le chemin le plus court dans un graphe pondéré d'un point A
    à un point B.

    Args:
            graph: Objet de la class Graph.
            start: noeud correspondant au point A
            stop: noeud correspondant au point B

    Returns:
        renvoie la liste du parcours pour rejoindre le point A au point B le plus rapidement
        ou None si un des noeuds n'existe pas ou si aucun chemin n'est disponible
    """
    if start not in graph.noeuds or stop not in graph.noeuds:
        return None

    if start == stop:
        return [start]

    detail = {}
    plus_proche = None
    for elt in graph.noeuds:
        if elt == start:
            detail[elt] = {"distance" : 0, "precedent" : None, "traité" : False}
        else:
            detail[elt] = {"distance" : inf, "precedent" : None, "traité" : False}
    while True:
        plus_proche = None
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

        for voisin in graph.aretes.get(plus_proche, {}):
            distance = detail[plus_proche]["distance"] + graph.aretes[plus_proche][voisin]
            if distance < detail[voisin]["distance"]:
                detail[voisin]["distance"] = distance
                detail[voisin]["precedent"] = plus_proche

    if detail[stop]["distance"] == inf:
        return None

    chemin = []
    actuel = stop
    while actuel != start:
        chemin.append(actuel)
        actuel = detail[actuel]["precedent"]
    chemin.append(actuel)
    chemin.reverse()
    return chemin
