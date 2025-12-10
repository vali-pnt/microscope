import sys
import requests
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QSplitter,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPixmapItem,
    QMenu,
    QFileDialog,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QUrl, QThread, pyqtSignal
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtGui import QPixmap, QAction, QPainter

URL = "http://microscope.local:8080"


class NetworkWorker(QThread):
    def __init__(self, method, url, data=None):
        super().__init__()
        self.method = method
        self.url = url
        self.data = data

    def run(self):
        try:
            if self.method == "POST":
                requests.post(self.url, json=self.data)
                print(f"POST sent to {self.url} with {self.data}")
            elif self.method == "GET_IMAGE":
                # logic handled in main for image to keep this simple
                pass
        except Exception as e:
            print(f"Network Error: {e}")


class ZoomableImageViewer(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)

        # Enable Panning
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setBackgroundBrush(Qt.GlobalColor.darkGray)

        # Context Menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def set_image(self, pixmap):
        self.pixmap_item.setPixmap(pixmap)
        self.scene.setSceneRect(self.pixmap_item.boundingRect())
        self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event):
        # Zoom Factor
        zoom_in_factor = 1.15
        zoom_out_factor = 1 / zoom_in_factor

        # Save the scene pos
        old_pos = self.mapToScene(event.position().toPoint())

        # Zoom
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor

        self.scale(zoom_factor, zoom_factor)

        # Get the new position
        new_pos = self.mapToScene(event.position().toPoint())

        # Move scene to old position
        delta = new_pos - old_pos
        self.translate(delta.x(), delta.y())

    def show_context_menu(self, position):
        if self.pixmap_item.pixmap().isNull():
            return

        menu = QMenu()
        save_action = QAction("Save Image As...", self)
        save_action.triggered.connect(self.save_image)
        menu.addAction(save_action)
        menu.exec(self.mapToGlobal(position))

    def save_image(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Image", "saved_image.png", "Images (*.png *.jpg *.bmp)"
        )
        if file_path:
            self.pixmap_item.pixmap().save(file_path)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Microscope")
        self.resize(1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        splitter1 = QSplitter(Qt.Orientation.Horizontal)
        splitter2 = QSplitter(Qt.Orientation.Vertical)

        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl(URL))
        splitter2.addWidget(self.browser)

        self.image_viewer = ZoomableImageViewer()
        splitter2.addWidget(self.image_viewer)

        splitter1.addWidget(splitter2)

        # 3. Side Panel (Controls)
        side_panel = QWidget()
        side_layout = QVBoxLayout(side_panel)
        side_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        btn_left = QPushButton("Left")
        btn_left.clicked.connect(lambda: self.send_move(-100, 0, 0))
        btn_right = QPushButton("Right")
        btn_right.clicked.connect(lambda: self.send_move(100, 0, 0))
        btn_up = QPushButton("Up")
        btn_up.clicked.connect(lambda: self.send_move(0, 100, 0))
        btn_down = QPushButton("Down")
        btn_down.clicked.connect(lambda: self.send_move(0, -100, 0))

        side_layout.addWidget(btn_left)
        side_layout.addWidget(btn_right)
        side_layout.addWidget(btn_up)
        side_layout.addWidget(btn_down)

        splitter1.addWidget(side_panel)
        main_layout.addWidget(splitter1)

    def keyPressEvent(self, event):
        key = event.key()

        if key == Qt.Key.Key_Up:
            self.send_move(0, 100, 0)
        elif key == Qt.Key.Key_Down:
            self.send_move(0, -100, 0)
        elif key == Qt.Key.Key_Left:
            self.send_move(-100, 0, 0)
        elif key == Qt.Key.Key_Right:
            self.send_move(100, 0, 0)
        else:
            super().keyPressEvent(event)

    def send_move(self, x, y, z):
        self.worker = NetworkWorker("POST", f"{URL}/step?x={x}&y={y}&z={z}")
        self.worker.start()

    def fetch_image(self):
        try:
            response = requests.get(IMAGE_URL)
            response.raise_for_status()

            pixmap = QPixmap()
            pixmap.loadFromData(response.content)

            self.image_viewer.set_image(pixmap)
            print("Image loaded successfully.")

        except Exception as e:
            print(f"Failed to load image: {e}")
            QMessageBox.warning(self, "Error", f"Could not load image: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
