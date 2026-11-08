from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QGraphicsView

class VueGraphe(QGraphicsView):
    """Vue de la scène avec zoom à la molette et déplacement à la souris."""

    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSceneRect(-200000, -200000, 400000, 400000)   # scène « infinie » pour pouvoir se déplacer
        self.deplacement_en_cours = False
        self.dernier_point = None
        self.deja_centree = False

    def showEvent(self, event):
        super().showEvent(event)
        if not self.deja_centree:
            self.deja_centree = True
            QTimer.singleShot(0, lambda: self.centerOn(450, 300))

    def ajuster_au_graphe(self):
        """Centre et ajuste la vue pour faire tenir les éléments du graphe."""
        rectangle = self.scene().itemsBoundingRect()
        if rectangle.isNull():
            return

        marge = max(rectangle.width(), rectangle.height()) * 0.04
        rectangle.adjust(-marge, -marge, marge, marge)
        self.fitInView(rectangle, Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event):
        """Zoome autour du curseur, en gardant une échelle lisible."""
        delta = event.angleDelta().y()
        if delta == 0:
            return
        # Chaque cran de molette multiplie l'échelle par 1,25 (ou son inverse).
        facteur = 1.25 ** (delta / 120)
        nouvelle_echelle = self.transform().m11() * facteur
        if 0.25 <= nouvelle_echelle <= 8:
            self.scale(facteur, facteur)

    def mousePressEvent(self, event):
        """Démarre un déplacement avec le bouton du milieu ou le clic droit dans le vide."""
        bouton = event.button()
        deplacer = bouton == Qt.MouseButton.MiddleButton

        if bouton == Qt.MouseButton.RightButton:
            item = self.itemAt(event.position().toPoint())
            deplacer = item is None or item not in self.scene().cercles   # sur un nœud : menu normal

        if deplacer:
            self.deplacement_en_cours = True
            self.dernier_point = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Déplace les barres de défilement pendant un glisser-déplacer."""
        if self.deplacement_en_cours:
            point = event.position().toPoint()
            delta = point - self.dernier_point
            self.dernier_point = point
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Termine le déplacement de la vue et restaure le curseur normal."""
        if self.deplacement_en_cours and event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton):
            self.deplacement_en_cours = False
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

