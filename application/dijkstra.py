from graphes import *
from math import inf

def dijkstra(graph, start, stop):
    if start not in graph.noeuds or stop not in graph.noeuds:
        return f"les noeuds n'existent pas dans le graphe, créer les avant de débuter"
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

    if detail[stop]["distance"] == inf:
        return f"aucun lien existant, connexion impossible"

    chemin = []
    actuel = stop
    while actuel != start:
        chemin.append(actuel)
        actuel = detail[actuel]["precedent"]
    chemin.append(actuel)
    chemin.reverse()
    return chemin

if __name__ == "__main__":
    resultat = dijkstra(test, "A", "C")
    print(resultat)
    resultat = dijkstra(test, "A", "D")
    print(resultat)