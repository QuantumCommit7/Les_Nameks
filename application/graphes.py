"""Modèle du réseau routier : nœuds, routes pondérées (distances en mètres) et feux."""


class Graphes:
    """Le réseau routier : nœuds, routes et feux. Cette classe ne dessine rien.

    Exemple :
        noeuds = {"A": "A", "B": {"phases": [["A", "C"], ["D", "E"]], "phase_active": 0}}
        aretes = {"A": {"B": 500}, "B": {"A": 500}}
    A est un nœud simple. B est un carrefour avec feu : en phase 0, les voitures
    venant de A ou C ont le vert, celles venant de D ou E ont le rouge.
    Chaque route est enregistrée dans les deux sens, avec son poids.

    Attributes:
        noeuds (dict): nom du nœud -> son nom (nœud simple) ou un dictionnaire
            {"phases": ..., "phase_active": ...} (carrefour avec feu).
        aretes (dict): nom du nœud -> {voisin: distance en mètres}.
    """

    def __init__(self):
        """Crée un réseau vide, sans nœud ni route."""
        self.noeuds = {}
        self.aretes = {}

    def a_un_feu(self, noeud):
        """Indique si un nœud est équipé d'un feu.

        Args:
            noeud (str): nom du nœud.

        Returns:
            bool: True si le nœud a un feu.
        """
        # Un nœud avec feu a pour valeur un dictionnaire (voir definir_feu).
        return isinstance(self.noeuds[noeud], dict)

    def ajouter_noeud(self, noeud):
        """Ajoute un nœud (carrefour ou point de passage) au réseau.

        Args:
            noeud (str): nom du nouveau nœud.

        Raises:
            TypeError: si le nom n'est pas une chaîne de caractères.
            ValueError: si un nœud porte déjà ce nom.
        """
        if not isinstance(noeud, str):
            raise TypeError("Votre noeud n'est pas un string")
        if noeud in self.noeuds:
            raise ValueError("Ce noeud existe déjà")
        self.noeuds[noeud] = noeud

    def ajouter_arete(self, depart, arrivee, poids):
        """Ajoute une route à double sens entre deux nœuds existants.

        Args:
            depart (str): premier nœud.
            arrivee (str): second nœud.
            poids (float): longueur de la route en mètres (utilisée par Dijkstra).

        Raises:
            ValueError: si l'un des deux nœuds n'existe pas.
        """
        if depart not in self.noeuds or arrivee not in self.noeuds:
            raise ValueError("les deux nœuds doivent exister")
        # setdefault crée le dictionnaire des voisins s'il n'existe pas encore.
        self.aretes.setdefault(depart, {})[arrivee] = poids
        self.aretes.setdefault(arrivee, {})[depart] = poids

    def renommer_noeud(self, ancien, nouveau):
        """Renomme un nœud partout : nœuds, routes et phases des feux.

        Args:
            ancien (str): nom actuel du nœud.
            nouveau (str): nouveau nom.

        Raises:
            ValueError: si l'ancien nœud n'existe pas ou si le nouveau nom est déjà pris.
        """
        if ancien not in self.noeuds:
            raise ValueError("le noeud n'existe pas")
        if nouveau in self.noeuds:
            raise ValueError("Ce noeud existe déjà")

        # pop retire l'ancienne clé et renvoie sa valeur (le feu éventuel est conservé).
        self.noeuds[nouveau] = self.noeuds.pop(ancien)
        if not self.a_un_feu(nouveau):
            self.noeuds[nouveau] = nouveau
        if ancien in self.aretes:
            self.aretes[nouveau] = self.aretes.pop(ancien)
        for voisins in self.aretes.values():
            if ancien in voisins:
                voisins[nouveau] = voisins.pop(ancien)
        for phase in self.toutes_les_phases():
            for i, voisin in enumerate(phase):
                if voisin == ancien:
                    phase[i] = nouveau

    def supprimer_noeud(self, nom):
        """Supprime un nœud, ses routes, et le retire des phases des feux.

        Args:
            nom (str): nœud à supprimer.

        Raises:
            ValueError: si le nœud n'existe pas.
        """
        if nom not in self.noeuds:
            raise ValueError("le noeud n'existe pas")
        del self.noeuds[nom]
        self.aretes.pop(nom, None)
        # list(...) : on copie les clés pour pouvoir supprimer pendant le parcours.
        for noeud in list(self.aretes):
            self.aretes[noeud].pop(nom, None)
            if not self.aretes[noeud]:
                del self.aretes[noeud]
        for phase in self.toutes_les_phases():
            while nom in phase:
                phase.remove(nom)

    def toutes_les_phases(self):
        """Rassemble les phases de tous les feux du réseau.

        Returns:
            list[list[str]]: chaque phase est la liste des voisins qui ont le vert.
        """
        phases = []
        for noeud in self.noeuds:
            if self.a_un_feu(noeud):
                phases.extend(self.noeuds[noeud]["phases"])
        return phases

    def definir_feu(self, noeud, phases):
        """Installe un feu sur un carrefour ; la phase 0 est active au départ.

        Args:
            noeud (str): carrefour à équiper.
            phases (list[list[str]]): [[voisins verts en phase 0], [voisins verts en phase 1]].

        Raises:
            ValueError: si le nœud n'existe pas.
        """
        if noeud not in self.noeuds:
            raise ValueError("le noeud n'existe pas")
        self.noeuds[noeud] = {"phases": phases, "phase_active": 0}

    def est_vert(self, noeud, venant_de):
        """Indique si une voiture venant de `venant_de` peut traverser `noeud`.

        Args:
            noeud (str): carrefour à traverser.
            venant_de (str): nœud d'où arrive la voiture.

        Returns:
            bool: True si le feu est vert pour elle (toujours True sans feu).
        """
        if not self.a_un_feu(noeud):
            return True  # pas de feu : on passe toujours
        feu = self.noeuds[noeud]
        return venant_de in feu["phases"][feu["phase_active"]]

    def changer_phase(self, noeud, nouvelle_phase):
        """Change la phase active du feu d'un carrefour.

        Args:
            noeud (str): carrefour équipé d'un feu.
            nouvelle_phase (int): numéro de la phase à activer (0 ou 1).

        Raises:
            TypeError: si le nœud n'a pas de feu.
        """
        if not self.a_un_feu(noeud):
            raise TypeError(f"le noeud {noeud} n'a pas de feu configuré")
        self.noeuds[noeud]["phase_active"] = nouvelle_phase


# Petit test manuel : ce bloc ne s'exécute que si on lance graphes.py directement.
if __name__ == "__main__":
    test = Graphes()
    for nom in "ABC":
        test.ajouter_noeud(nom)
    test.ajouter_arete("A", "B", 15)
    test.ajouter_arete("B", "C", 7)
    test.ajouter_arete("C", "A", 5)
    test.definir_feu("A", [["B"], ["C"]])
    print(test.est_vert("A", "B"), test.est_vert("A", "C"))  # True False
    test.changer_phase("A", 1)
    print(test.noeuds)
    print(test.aretes)
