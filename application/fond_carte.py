"""
Fond de carte pour l'onglet « Schéma ».

- FondCarte : télécharge / met en cache les tuiles et les dessine derrière la scène.
- VueGraphe : QGraphicsView avec zoom à la molette et déplacement de la carte.

Les coordonnées de la scène (celles des nœuds) sont des pixels de carte au zoom ZREF :
Le point (REF_X, REF_Y) de la scène correspond à (CENTRE_LAT, CENTRE_LON). Les nœuds gardent donc leurs positions actuelles,
et on peut convertir scène <-> GPS avec scene_vers_latlon / latlon_vers_scene.
"""
import json
import math
import time
from pathlib import Path


from PyQt6.QtCore import QObject, QRectF, QUrl, QUrlQuery, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import QGraphicsScene
#https://doc.qt.io/qt/qgraphicsview.html
# ----------------------------- Réglages ------------------------------------
CENTRE_LAT = 48.0794      # Colmar
CENTRE_LON = 7.3585
REF_X, REF_Y = 200, 200   
ZREF = 16                 
ZMIN, ZMAX = 10, 19       
TAILLE_TUILE = 256
URL_TUILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
USER_AGENT = b"SimulateurTrafic/1.0 (projet etudiant IUT Colmar R&T)"  # exigé par OSM
DOSSIER_CACHE = Path(__file__).resolve().parent / "cache_tuiles"
MAX_TUILES_MEMOIRE = 600
DELAI_NOUVEL_ESSAI = 30   
MAX_TUILES_PAR_IMAGE = 150
# -------------------------- Merci de ne par supprimer ceci -Sichard Lomme-----------------------------
#ça utilise QGraphicsScene grace a QGraphicsView https://doc.qt.io/qt/qgraphicsview.html
#https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames
#https://operations.osmfoundation.org/policies/tiles/

def latlon_vers_pixel(lat, lon, z):
    n = TAILLE_TUILE * 2 ** z
    x = (lon + 180) / 360 * n
    sin_lat = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + sin_lat) / (1 - sin_lat)) / (4 * math.pi)) * n
    return x, y


def pixel_vers_latlon(x, y, z):
    n = TAILLE_TUILE * 2 ** z
    lon = x / n * 360 - 180
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lat, lon


class FondCarte(QObject):
    tuile_prete = pyqtSignal(QRectF)   # zone de la scène à redessiner
    lieux_trouves = pyqtSignal(list)   # liste de (nom, lat, lon)
    erreur_recherche = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        cx, cy = latlon_vers_pixel(CENTRE_LAT, CENTRE_LON, ZREF)
        self.origine_x = cx - REF_X    # pixel monde (zoom ZREF) de l'abscisse de scène 0
        self.origine_y = cy - REF_Y
        self.cache = {}                # (z, x, y) -> QPixmap
        self.en_cours = set()
        self.echecs = {}               # (z, x, y) -> instant de l'échec
        self.reseau = QNetworkAccessManager(self)

    # ---------------- conversions scène <-> GPS ----------------
    def scene_vers_latlon(self, x, y):
        return pixel_vers_latlon(self.origine_x + x, self.origine_y + y, ZREF)

    def latlon_vers_scene(self, lat, lon):
        px, py = latlon_vers_pixel(lat, lon, ZREF)
        return px - self.origine_x, py - self.origine_y

    def definir_centre(self, lat, lon, scene_x, scene_y):
        """Place (lat, lon) sur le point (scene_x, scene_y) de la scène : les nœuds ne bougent pas, la carte change."""
        cx, cy = latlon_vers_pixel(lat, lon, ZREF)
        self.origine_x = cx - scene_x
        self.origine_y = cy - scene_y
        self.echecs.clear()

    # ---------------- recherche d'un lieu (Nominatim, puis Photon en secours) ----------------
    def chercher_lieu(self, texte):
        self.lancer_recherche(texte, "nominatim")

    def lancer_recherche(self, texte, service):
        requete_url = QUrlQuery()
        requete_url.addQueryItem("q", texte)
        requete_url.addQueryItem("limit", "6")
        if service == "nominatim":
            url = QUrl("https://nominatim.openstreetmap.org/search")
            requete_url.addQueryItem("format", "json")
            requete_url.addQueryItem("accept-language", "fr")
        else:
            url = QUrl("https://photon.komoot.io/api/")
            requete_url.addQueryItem("lang", "fr")
        url.setQuery(requete_url)

        requete = QNetworkRequest(url)
        requete.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, USER_AGENT)
        requete.setRawHeader(b"Accept", b"application/json")
        requete.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                             QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        reponse = self.reseau.get(requete)
        reponse.finished.connect(lambda r=reponse: self.recherche_recue(r, texte, service))

    def recherche_recue(self, reponse, texte, service):
        try:
            if reponse.error() != QNetworkReply.NetworkError.NoError:
                code = reponse.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
                detail = f"{service} : HTTP {code} - {reponse.errorString()}"
                print(f"Recherche de lieu échouée ({detail})")
                if service == "nominatim":
                    self.lancer_recherche(texte, "photon")   # on tente le service de secours
                else:
                    self.erreur_recherche.emit(detail)
                return

            donnees = json.loads(bytes(reponse.readAll()).decode("utf-8"))
            if service == "nominatim":
                lieux = [(d["display_name"], float(d["lat"]), float(d["lon"])) for d in donnees]
            else:
                lieux = []
                for f in donnees["features"]:
                    p = f["properties"]
                    lon, lat = f["geometry"]["coordinates"]
                    rue = " ".join(m for m in (p.get("housenumber"), p.get("street")) if m)
                    morceaux = []
                    for m in (p.get("name"), rue, p.get("postcode"), p.get("city"), p.get("country")):
                        if m and str(m) not in morceaux:
                            morceaux.append(str(m))
                    lieux.append((", ".join(morceaux), float(lat), float(lon)))
            self.lieux_trouves.emit(lieux)
        except (ValueError, KeyError, TypeError) as erreur:
            self.erreur_recherche.emit(f"Réponse illisible ({service}) : {erreur}")
        finally:
            reponse.deleteLater()

    #  tuiles 
    def chemin_tuile(self, z, x, y):
        return DOSSIER_CACHE / str(z) / str(x) / f"{y}.png"

    def rect_tuile(self, z, tx, ty):
        taille = TAILLE_TUILE / 2 ** (z - ZREF)
        return QRectF(tx * taille - self.origine_x, ty * taille - self.origine_y, taille, taille)

    def ranger(self, cle, pixmap):
        if len(self.cache) >= MAX_TUILES_MEMOIRE:
            del self.cache[next(iter(self.cache))]   # supprime l'ancienne
        self.cache[cle] = pixmap

    def obtenir_tuile(self, z, tx, ty):
        cle = (z, tx, ty)
        if cle in self.cache:
            return self.cache[cle]

        chemin = self.chemin_tuile(*cle)
        if chemin.exists():
            pixmap = QPixmap(str(chemin))
            if not pixmap.isNull():
                self.ranger(cle, pixmap)
                return pixmap

        self.demander(cle)
        return None

    def demander(self, cle):
        if cle in self.en_cours:
            return
        instant_echec = self.echecs.get(cle)
        if instant_echec is not None and time.monotonic() - instant_echec < DELAI_NOUVEL_ESSAI:
            return

        z, x, y = cle
        requete = QNetworkRequest(QUrl(URL_TUILES.format(z=z, x=x, y=y)))
        requete.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, USER_AGENT.decode())
        requete.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                             QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        reponse = self.reseau.get(requete)
        self.en_cours.add(cle)
        reponse.finished.connect(lambda r=reponse, c=cle: self.tuile_recue(r, c))

    def tuile_recue(self, reponse, cle):
        self.en_cours.discard(cle)
        reussi = False

        if reponse.error() == QNetworkReply.NetworkError.NoError:
            donnees = reponse.readAll()
            pixmap = QPixmap()
            if pixmap.loadFromData(donnees):
                try:
                    chemin = self.chemin_tuile(*cle)
                    chemin.parent.mkdir(parents=True, exist_ok=True)
                    chemin.write_bytes(bytes(donnees))
                except OSError as erreur:
                    print(f"Cache de tuile impossible : {erreur}")
                self.ranger(cle, pixmap)
                self.tuile_prete.emit(self.rect_tuile(*cle))
                reussi = True

        if not reussi:
            self.echecs[cle] = time.monotonic()
            print(f"Tuile {cle} indisponible")
        reponse.deleteLater()

    # ---------------- dessin ----------------
    def dessiner(self, painter, rect):
        painter.fillRect(rect, QColor("#e9e5dc"))

        echelle = painter.worldTransform().m11()
        if echelle <= 0:
            return

        z = ZREF + round(math.log2(echelle))
        z = max(ZMIN, min(ZMAX, z))
        facteur = 2 ** (z - ZREF)              # pixels de tuile
        taille_scene = TAILLE_TUILE / facteur  # taille d'une tuile
        n = 2 ** z

        x0 = math.floor((self.origine_x + rect.left()) * facteur / TAILLE_TUILE)
        x1 = math.floor((self.origine_x + rect.right()) * facteur / TAILLE_TUILE)
        y0 = math.floor((self.origine_y + rect.top()) * facteur / TAILLE_TUILE)
        y1 = math.floor((self.origine_y + rect.bottom()) * facteur / TAILLE_TUILE)

        if (x1 - x0 + 1) * (y1 - y0 + 1) > MAX_TUILES_PAR_IMAGE:
            return

        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        marge = 0.5 / echelle   

        for tx in range(max(0, x0), min(n - 1, x1) + 1):
            for ty in range(max(0, y0), min(n - 1, y1) + 1):
                cible = QRectF(tx * taille_scene - self.origine_x,
                               ty * taille_scene - self.origine_y,
                               taille_scene + marge, taille_scene + marge)
                pixmap = self.obtenir_tuile(z, tx, ty)
                if pixmap is not None:
                    painter.drawPixmap(cible, pixmap, QRectF(pixmap.rect()))
                else:
                    self.dessiner_parent(painter, z, tx, ty, cible)

    def dessiner_parent(self, painter, z, tx, ty, cible):
        """En attendant la tuile, on affiche (floue) la tuile du zoom inférieur si on l'a déjà."""
        for niveau in (1, 2, 3):
            if z - niveau < 0:
                return
            parent = self.cache.get((z - niveau, tx >> niveau, ty >> niveau))
            if parent is not None:
                part = TAILLE_TUILE / 2 ** niveau
                sx = (tx - ((tx >> niveau) << niveau)) * part
                sy = (ty - ((ty >> niveau) << niveau)) * part
                painter.drawPixmap(cible, parent, QRectF(sx, sy, part, part))
                return



