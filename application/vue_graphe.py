"""La « caméra » qui regarde la scène : zoom à la molette et déplacement à la souris.

Zoomer ou se déplacer ne change que la vue : les objets de la scène ne bougent pas.
"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QGraphicsView


class VueGraphe(QGraphicsView):
    """Vue de la scène, avec zoom à la molette et déplacement par glisser-déposer.

    Attributes:
        dernier_point (QPoint | None): position de la souris pendant un déplacement
            de la vue, None quand on ne déplace pas.
    """

    def __init__(self, scene):
        """Configure la vue (lissage, zoom sous la souris, scène « infinie »).

        Args:
            scene (SceneGraphe): scène à afficher.
        """
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)  # bords lissés
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)  # zoom autour de la souris
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)  # garde le centre si on redimensionne
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSceneRect(-200000, -200000, 400000, 400000)  # scène « infinie » pour se déplacer
        self.dernier_point = None  # position de la souris pendant un déplacement
        # Centrer la vue dès que la fenêtre a sa taille définitive.
        QTimer.singleShot(0, lambda: self.centerOn(450, 300))

    def ajuster_au_graphe(self):
        """Zoome pour faire tenir tout le graphe dans la vue, avec une petite marge."""
        rectangle = self.scene().itemsBoundingRect()
        if rectangle.isNull():
            return
        marge = max(rectangle.width(), rectangle.height()) * 0.04
        rectangle.adjust(-marge, -marge, marge, marge)
        self.fitInView(rectangle, Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event):
        """Molette de la souris : zoom avant ou arrière, entre x0,25 et x8.

        Args:
            event (QWheelEvent): informations sur le mouvement de la molette.
        """
        # Chaque cran de molette multiplie l'échelle par 1,25 (ou la divise).
        facteur = 1.25 ** (event.angleDelta().y() / 120)
        if 0.25 <= self.transform().m11() * facteur <= 8:  # m11() = échelle actuelle
            self.scale(facteur, facteur)

    def mousePressEvent(self, event):
        """Clic du milieu, ou clic droit dans le vide : on commence à déplacer la vue.

        Les autres clics sont transmis à la scène.

        Args:
            event (QMouseEvent): informations sur le clic (bouton, position).
        """
        bouton = event.button()
        sur_un_noeud = self.itemAt(event.position().toPoint()) in self.scene().cercles
        if bouton == Qt.MouseButton.MiddleButton or (bouton == Qt.MouseButton.RightButton and not sur_un_noeud):
            self.dernier_point = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        else:
            super().mousePressEvent(event)  # sinon, le clic est transmis à la scène

    def mouseMoveEvent(self, event):
        """Pendant un déplacement de la vue, la fait glisser avec la souris.

        Args:
            event (QMouseEvent): informations sur le mouvement (position).
        """
        if self.dernier_point is None:
            super().mouseMoveEvent(event)
            return
        point = event.position().toPoint()
        delta = point - self.dernier_point  # déplacement de la souris
        self.dernier_point = point
        self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
        self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())

    def mouseReleaseEvent(self, event):
        """Fin du déplacement de la vue : le curseur redevient normal.

        Args:
            event (QMouseEvent): informations sur le relâchement du bouton.
        """
        if self.dernier_point is None:
            super().mouseReleaseEvent(event)
            return
        self.dernier_point = None
        self.unsetCursor()
