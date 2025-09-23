# Staff Attendance

## Project Overview

This application is designed to facilitate efficient staff attendance tracking using QR code scanning. It provides a user-friendly interface for scanning badges, displaying real-time feedback, and maintaining a historical log of scans. The application also features a dashboard to summarize attendance data.

## Features

*   **QR Code Scanning:** Quickly scan staff badges to record attendance.
*   **Real-time Feedback:** Instant visual feedback on successful scans or errors.
*   **Attendance Dashboard:** Displays key metrics such as total employees and scanned count.
*   **Scan History:** A chronological list of recent attendance records.
*   **Modern UI/UX:** Clean and intuitive interface built with Materialize CSS and custom styling.

## Setup Instructions

To set up and run this project, follow these steps:

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd QR
    ```

2.  **Create a Python Virtual Environment (recommended):**
    ```bash
    python -m venv .venv
    ```

3.  **Activate the Virtual Environment:**
    *   **Windows:**
        ```bash
        .venv\Scripts\activate
        ```
    *   **macOS/Linux:**
        ```bash
        source .venv/bin/activate
        ```

4.  **Install Dependencies:**
    ```bash
    pip install PyQt6 PyQt6-WebEngine
    ```
    *(Note: Other dependencies like `bottle`, `eel`, etc., might be present in the environment but `PyQt6` and `PyQt6-WebEngine` are crucial for the application's core functionality.)*

## How to Run

After setting up the environment and installing dependencies, you can run the application:

```bash
python main.py
```

## UI/UX Notes

 
 
