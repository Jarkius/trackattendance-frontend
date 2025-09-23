import sys
import os
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import QObject, pyqtSlot, QUrl, QPropertyAnimation, QEasingCurve, Qt
FALLBACK_ERROR_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Interface Load Error</title>
    <style>
        body {
            margin: 0;
            font-family: "Segoe UI", Arial, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
            background-color: #f5f5f5;
            color: #333333;
        }
        .container {
            max-width: 560px;
            padding: 32px;
            text-align: center;
            border: 1px solid #e0e0e0;
            border-radius: 12px;
            background-color: #ffffff;
            box-shadow: 0 12px 32px rgba(0, 0, 0, 0.08);
        }
        h1 {
            margin-bottom: 12px;
            font-size: 1.6rem;
            color: #000000;
        }
        p {
            margin: 0;
            line-height: 1.5;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Interface Load Error</h1>
        <p>The attendance experience could not be loaded. Please verify that the local assets under <code>web/</code> are available, then restart the application.</p>
        <p>Press <strong>Alt+F4</strong> (or close the window from the taskbar) to exit.</p>
    </div>
</body>
</html>"""


class Api(QObject):
    @pyqtSlot()
    def close_window(self):
        """Shut down the QApplication when the web UI requests a close via QWebChannel."""
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
            return

        view.loadFinished.disconnect(on_load_finished)
        print('Failed to load web interface from:', file=sys.stderr)
        print(file_path, file=sys.stderr)
        window.setWindowOpacity(1.0)
        window.showFullScreen()
        view.setHtml(FALLBACK_ERROR_HTML)
        QMessageBox.critical(
            window,
            'Load Error',
            'Unable to load the attendance interface. Please check the local assets and try again.'
        )

    view.loadFinished.connect(on_load_finished)
    # ----------------------------------------------------

    # Load the HTML file
    file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "web", "index.html"))
    view.setUrl(QUrl.fromLocalFile(file_path))
    
    window.setCentralWidget(view)

    sys.exit(app.exec())

if __name__ == '__main__':
    main()
