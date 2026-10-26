# Cartographie expérimentale

La cartographie est temporairement déconnectée de l'interface afin que le simulateur démarre sur son graphe classique, sans requête de géocodage ni téléchargement de tuiles.

Le code cartographique est conservé dans `application/fond_carte.py`. Il contient le chargement et le cache des tuiles OpenStreetMap, la recherche de villes et de lieux, ainsi que les conversions entre coordonnées de scène et coordonnées GPS. Les tuiles déjà présentes restent dans `application/cache_tuiles/`.

Le zoom à la molette et le déplacement de la vue sont indépendants de la carte. Ils restent disponibles dans `application/vue_graphe.py`.

## Réactivation ultérieure

1. Reconnecter `FondCarte` à `SceneGraphe` dans `application/scene_graphe.py` : créer l'objet, dessiner son fond et rafraîchir la scène lorsqu'une tuile arrive.
2. Reconnecter la recherche de lieu dans `application/interface.py` : bouton, signaux de résultat et appels à `chercher_lieu()` et `definir_centre()`.
3. L'ancien code de l'interface faisait référence à `PanneauCarte` dans `carte.py`, mais ce fichier est absent du dépôt. Pour retrouver un onglet de carte dédié, il faudra retrouver ce module ou rétablir son intégration; il n'a pas été recréé ici.
4. Les conversions GPS et les constantes de carte restent dans `application/fond_carte.py`.

La cartographie n'a pas été déplacée ni réécrite. Ce fichier indique où la reconnecter plus tard.
