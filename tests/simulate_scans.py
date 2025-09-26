import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, List, Dict, Any

from PyQt6.QtCore import QEventLoop, QTimer, QUrl
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView


def simulate_scans(barcodes: Iterable[str], html_path: Path) -> List[Dict[str, Any]]:
    """Load the attendance UI and simulate Enter key submissions for each barcode."""
    app = QApplication(sys.argv)
    view = QWebEngineView()

    load_state: Dict[str, Any] = {"ok": None}
    load_loop = QEventLoop()

    def on_load_finished(ok: bool) -> None:
        load_state["ok"] = ok
        load_loop.quit()

    view.loadFinished.connect(on_load_finished)
    view.setUrl(QUrl.fromLocalFile(str(html_path)))
    load_loop.exec()

    if not load_state.get("ok"):
        raise RuntimeError(f"Failed to load UI from {html_path}")

    # Ensure the underlying page has time to finish any startup script before we drive it.
    startup_loop = QEventLoop()
    QTimer.singleShot(100, startup_loop.quit)
    startup_loop.exec()

    results: List[Dict[str, Any]] = []

    for barcode in barcodes:
        loop = QEventLoop()
        payload = json.dumps(barcode)
        script = f"""
            (function(barcode) {{
                const barcodeInput = document.getElementById('barcode-input');
                const feedback = document.getElementById('live-feedback-name');
                const totalScanned = document.getElementById('total-scanned');
                const historyList = document.getElementById('scan-history-list');
                if (!barcodeInput) {{
                    return {{ status: 'missing-input', barcode }};
                }}
                barcodeInput.value = barcode;
                const event = new KeyboardEvent('keyup', {{ key: 'Enter' }});
                barcodeInput.dispatchEvent(event);
                const firstHistory = historyList && historyList.firstElementChild;
                const historyName = firstHistory ? firstHistory.querySelector('.name') : null;
                return {{
                    status: 'ok',
                    barcode,
                    feedbackText: feedback ? feedback.textContent.trim() : null,
                    feedbackColor: feedback ? window.getComputedStyle(feedback).color : null,
                    totalScanned: totalScanned ? totalScanned.textContent.trim() : null,
                    historyTop: historyName ? historyName.textContent.trim() : null
                }};
            }})({payload});
        """

        def handle_result(result: Any, current_barcode: str = barcode) -> None:
            outcome = result or {"status": "no-result", "barcode": current_barcode}
            if "barcode" not in outcome:
                outcome["barcode"] = current_barcode
            results.append(outcome)
            loop.quit()

        view.page().runJavaScript(script, handle_result)
        loop.exec()

        # Allow the UI to settle (e.g., feedback countdown) before the next scan.
        settle_loop = QEventLoop()
        QTimer.singleShot(150, settle_loop.quit)
        settle_loop.exec()

    QTimer.singleShot(0, app.quit)
    app.exec()
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Simulate barcode scans against the Track Attendance UI."
    )
    parser.add_argument(
        "barcodes",
        nargs="*",
        help="Barcode values to submit; defaults use sample employees and an invalid entry."
    )
    parser.add_argument(
        "--html",
        dest="html",
        default=str(Path(__file__).resolve().parents[1] / "web" / "index.html"),
        help="Path to the index.html file to load."
    )
    args = parser.parse_args()

    html_path = Path(args.html).resolve()
    if not html_path.exists():
        print(f"HTML asset not found: {html_path}", file=sys.stderr)
        return 2

    barcodes = args.barcodes or [
        "12345",
        "101117",
        "67890",
        "101124",
        "999999"  # Intentionally invalid to exercise the not-found branch.
    ]

    try:
        results = simulate_scans(barcodes, html_path)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 3

    all_ok = True
    for entry in results:
        status = entry.get("status", "unknown")
        barcode = entry.get("barcode", "<missing>")
        if status != "ok":
            all_ok = False
            print(f"[{status}] barcode={barcode}")
            continue
        feedback = entry.get("feedbackText") or "<no feedback>"
        total = entry.get("totalScanned") or "?"
        history_name = entry.get("historyTop") or "<no history>"
        print(f"[ok] barcode={barcode} feedback='{feedback}' total_scanned={total} history_top='{history_name}'")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
