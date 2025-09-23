import sys
import os
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import QObject, pyqtSlot, QUrl, QPropertyAnimation, QEasingCurve, Qt

class Api(QObject):
    @pyqtSlot()
    def close_window(self):
        app.quit()

def main():
    global app
    app = QApplication(sys.argv)

    window = QMainWindow()
    window.setWindowTitle('Deloitte Staff Attendance')
    
    # Set window attributes for transparency and hide frame for a cleaner look
    window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    window.setWindowFlags(Qt.WindowType.FramelessWindowHint)
    window.setWindowOpacity(0.0) # Start fully transparent

    view = QWebEngineView()
    # Make the web view background transparent to see the window's fade-in
    view.page().setBackgroundColor(Qt.GlobalColor.transparent)

    # --- Animation Setup ---
    animation = QPropertyAnimation(window, b"windowOpacity")
    animation.setDuration(400) # A slightly faster fade
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
    # -----------------------

    # Set up the web channel
    channel = QWebChannel()
    api = Api()
    channel.registerObject('api', api)
    view.page().setWebChannel(channel)

    # --- Wait for page to load before showing window ---
    def on_load_finished(ok):
        if ok:
            window.showFullScreen()
            animation.start()

    view.loadFinished.connect(on_load_finished)
    # ----------------------------------------------------

    # Load the HTML file
    file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "web", "index.html"))
    view.setUrl(QUrl.fromLocalFile(file_path))
    
    window.setCentralWidget(view)

    sys.exit(app.exec())

if __name__ == '__main__':
    main()