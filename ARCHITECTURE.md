# Architecture Document: Deloitte Staff Attendance

## 1. Overview

The Deloitte Staff Attendance application is a desktop application built using Python and PyQt6, leveraging web technologies (HTML, CSS, JavaScript) for its user interface. This hybrid approach allows for rich UI development with web standards while maintaining desktop application capabilities and system integration through Python.

## 2. Components

The application is primarily composed of the following architectural components:

### 2.1. Frontend (Web UI)
*   **Technologies:** HTML5, CSS3 (Materialize CSS framework, custom `style.css`), JavaScript.
*   **Purpose:** Renders the user interface, handles user interactions (e.g., barcode input), displays feedback, and presents attendance data (dashboard, history).
*   **Files:** `web/index.html`, `web/css/*.css`, `web/js/script.js`.

### 2.2. Backend (Python/PyQt6 Application)
*   **Technologies:** Python, PyQt6, PyQt6-WebEngine.
*   **Purpose:** Manages the desktop application window, embeds the web UI, handles communication between the web UI and the Python backend, and performs core application logic (e.g., processing barcode scans, interacting with a database or external systems for attendance records).
*   **Files:** `main.py`.

### 2.3. Communication Layer (QWebChannel)
*   **Technology:** PyQt6's QWebChannel.
*   **Purpose:** Facilitates seamless, asynchronous communication between the JavaScript frontend and the Python backend. This allows JavaScript to call Python methods and Python to emit signals that JavaScript can listen to.
*   **Implementation:** An `Api` QObject in Python registers methods (`close_window` in this case) that are exposed to the JavaScript context via the `QWebChannel`.

## 3. Data Flow

1.  **Application Startup:**
    *   `main.py` initializes the PyQt6 application and `QMainWindow`.
    *   A `QWebEngineView` is created and configured to load `web/index.html`.
    *   A `QWebChannel` is set up, and a Python `Api` object is registered, making its methods available to the JavaScript frontend.
    *   The window fades in upon successful page load.

2.  **User Interaction (e.g., Barcode Scan):**
    *   User inputs a barcode into the `<input id="barcode-input">` element in the HTML UI.
    *   JavaScript (`script.js`) captures this input.
    *   JavaScript uses the `QWebChannel` to call a corresponding Python method (e.g., `api.processBarcode(barcode_value)` - *hypothetical, not yet implemented*).

3.  **Backend Processing:**
    *   The Python backend receives the barcode value.
    *   It processes the barcode (e.g., validates, records attendance, fetches employee details).
    *   Python prepares feedback data (e.g., employee name, status).

4.  **Feedback to UI:**
    *   Python emits a signal or calls a JavaScript function via `QWebChannel` to update the UI.
    *   JavaScript (`script.js`) receives this update and displays the feedback (e.g., updates `#live-feedback-name`, `#total-scanned`, `#scan-history-list`).

## 4. Key Technologies

*   **Python:** Core application logic and desktop integration.
*   **PyQt6:** Python bindings for the Qt application framework, providing GUI widgets and web engine integration.
*   **PyQt6-WebEngine:** Enables embedding a Chromium-based web engine (`QWebEngineView`) for rendering the web UI.
*   **QWebChannel:** Facilitates communication between the Python backend and the JavaScript frontend.
*   **HTML/CSS/JavaScript:** Standard web technologies for building the interactive user interface.
*   **Materialize CSS:** A modern responsive front-end framework for faster and easier web development.
