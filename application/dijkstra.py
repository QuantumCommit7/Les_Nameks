from graphes import *
from math import inf

def dijkstra(graph, start, stop):
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
        detail[plus_proche]["traité"] = True

        if plus_proche == stop:
            break

        for voisin in graph.aretes[plus_proche]:
            distance = detail[plus_proche]["distance"] + graph.aretes[plus_proche][voisin]
            if distance < detail[voisin]["distance"]:
                detail[voisin]["distance"] = distance
                detail[voisin]["precedent"] = plus_proche
    chemin = []
    actuel = stop
    while actuel != start:
        chemin.append(actuel)
        actuel = detail[actuel]["precedent"]
    chemin.append(actuel)
    chemin.reverse()
    return chemin

resultat = dijkstra(test, "A", "C")
print(resultat)