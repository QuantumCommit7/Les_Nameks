"""Recherche du chemin le moins coûteux entre deux nœuds (algorithme de Dijkstra)."""

from math import inf  # l'infini : distance d'un nœud qu'on ne sait pas encore atteindre


def dijkstra(graphe, depart, arrivee):
    """Calcule le chemin le plus court (en mètres) entre deux nœuds.

    Exemple : dijkstra(graphe, "A", "H") -> ["A", "B", "G", "H"].

    Args:
        graphe (Graphes): réseau routier ; les poids des routes doivent être positifs.
        depart (str): nœud de départ.
        arrivee (str): nœud d'arrivée.

    Returns:
        list[str] | None: les nœuds du chemin, du départ à l'arrivée ; [depart] si les
        deux nœuds sont identiques ; None si un nœud n'existe pas ou si aucun chemin n'existe.
    """
    if depart not in graphe.noeuds or arrivee not in graphe.noeuds:
        return None
    if depart == arrivee:
        return [depart]

    # distance[n] : meilleur coût connu pour aller du départ à n.
    # precedent[n] : nœud par lequel on arrive en n sur ce meilleur chemin.
    distance = {noeud: inf for noeud in graphe.noeuds}
    distance[depart] = 0
    precedent = {}
    a_traiter = list(graphe.noeuds)

    while a_traiter:
        # On prend le nœud non traité le plus proche du départ.
        noeud = min(a_traiter, key=lambda n: distance[n])
        if distance[noeud] == inf or noeud == arrivee:
            break  # les nœuds restants sont inaccessibles, ou on est arrivé
        a_traiter.remove(noeud)

        # Passer par ce nœud améliore-t-il le coût de ses voisins ?
        for voisin, poids in graphe.aretes.get(noeud, {}).items():
            if distance[noeud] + poids < distance[voisin]:
                distance[voisin] = distance[noeud] + poids
                precedent[voisin] = noeud

    if distance[arrivee] == inf:
        return None

    # On remonte les précédents depuis l'arrivée (H -> G -> B -> A),
    # puis on inverse la liste pour obtenir A, B, G, H.
    chemin = [arrivee]
    while chemin[-1] != depart:
        chemin.append(precedent[chemin[-1]])
    chemin.reverse()
    return chemin
