import argparse
import itertools
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from PyQt6.QtCore import QEventLoop, QTimer

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from main import initialize_app

DEFAULT_EMPLOYEE_BARCODES = [
    '12345',
    '67890',
    '54321',
    '09876',
    '11223',
    '101117',
    '101118',
    '101119',
    '101120',
    '101121',
    '101122',
    '101123',
    '101124',
]

SPECIAL_CASE_BARCODES = [
    '999999',               # intentionally invalid control scan
    '!@#$%',                # punctuation-only input
    '12345-ABC',            # mixed digits and hyphen
    'DROP TABLE;',          # SQL-ish input
    '"quoted"',            # quotes inside payload
    "');--",               # closing quote + comment
]

DEFAULT_BARCODES = DEFAULT_EMPLOYEE_BARCODES + SPECIAL_CASE_BARCODES


def _cycle_barcodes(iterations: int, base: Iterable[str]) -> List[str]:
    base_list = list(base)
    if not base_list:
        return []
    iterator = itertools.cycle(base_list)
    return [next(iterator) for _ in range(iterations)]


def _run_js(view, script: str) -> Any:
    loop = QEventLoop()
    result_container: Dict[str, Any] = {}

    def handle_result(result: Any) -> None:
        result_container['value'] = result
        loop.quit()

    view.page().runJavaScript(script, handle_result)
    loop.exec()
    return result_container.get('value')


def _dispatch_scan(view, barcode: str) -> Dict[str, Any]:
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
            const event = new KeyboardEvent('keyup', {{ key: 'Enter', bubbles: true }});
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
    result = _run_js(view, script)
    if not isinstance(result, dict):
        return {'status': 'no-result', 'barcode': barcode}
    if 'barcode' not in result:
        result['barcode'] = barcode
    return result


def _collect_snapshot(view) -> Dict[str, Any]:
    script = """
        (function() {
            const feedback = document.getElementById('live-feedback-name');
            const totalScanned = document.getElementById('total-scanned');
            const historyList = document.getElementById('scan-history-list');
            const historyName = historyList && historyList.firstElementChild ? historyList.firstElementChild.querySelector('.name') : null;
            return {
                feedbackText: feedback ? feedback.textContent.trim() : null,
                feedbackColor: feedback ? window.getComputedStyle(feedback).color : null,
                totalScanned: totalScanned ? totalScanned.textContent.trim() : null,
                historyTop: historyName ? historyName.textContent.trim() : null
            };
        })();
    """
    snapshot = _run_js(view, script)
    return snapshot if isinstance(snapshot, dict) else {}


def run_stress_test(
    iterations: int,
    barcodes: Sequence[str],
    delay_ms: int,
    show_window: bool,
    show_full_screen: bool,
    enable_fade: bool,
    verbose: bool,
) -> int:
    load_state: Dict[str, Any] = {'ok': None}
    load_loop = QEventLoop()

    def on_load_finished(ok: bool) -> None:
        load_state['ok'] = ok
        if load_loop.isRunning():
            load_loop.quit()

    app, window, view, _ = initialize_app(
        argv=sys.argv,
        show_window=show_window,
        show_full_screen=show_full_screen,
        enable_fade=enable_fade,
        on_load_finished=on_load_finished,
    )

    if load_state['ok'] is None:
        load_loop.exec()
    if not load_state['ok']:
        return 3

    sequence = _cycle_barcodes(iterations, barcodes)
    failures: List[Dict[str, Any]] = []
    successful = 0
    invalid = 0
    start = time.perf_counter()

    for index, barcode in enumerate(sequence, start=1):
        result = _dispatch_scan(view, barcode)
        status = result.get('status', 'unknown')
        feedback = (result.get('feedbackText') or '').strip()
        total_scanned = result.get('totalScanned')
        history_top = result.get('historyTop')

        if status != 'ok':
            failures.append(result)
        else:
            if feedback.lower().startswith('not found'):
                invalid += 1
            else:
                successful += 1

        if verbose:
            print(f"[{index:03d}] status={status} barcode={barcode} feedback='{feedback}' total={total_scanned} history='{history_top}'")
        elif index % 25 == 0 or index == 1 or index == iterations:
            print(f"[{index:03d}/{iterations}] status={status} feedback='{feedback}' total={total_scanned}")

        if delay_ms > 0:
            settle_loop = QEventLoop()
            QTimer.singleShot(delay_ms, settle_loop.quit)
            settle_loop.exec()

    duration = time.perf_counter() - start
    snapshot = _collect_snapshot(view)

    window.close()
    for _ in range(3):
        app.processEvents()

    print("\n--- Stress Test Summary ---")
    print(f'Scans attempted : {iterations}')
    print(f'Successful scans: {successful}')
    print(f'Invalid scans   : {invalid}')
    print(f'Failures        : {len(failures)}')
    print(f'Total runtime   : {duration:.2f}s')

    if failures:
        print("\nFirst failure:")
        print(json.dumps(failures[0], indent=2))
        return 2

    expected_total = str(successful)
    final_total = snapshot.get('totalScanned') if snapshot else None
    if final_total and final_total != expected_total:
        print(f"Warning: total_scanned reported as {final_total}, expected {expected_total}.")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='Drive the full PyQt window and simulate barcode scans.')
    parser.add_argument('barcodes', nargs='*', help='Base barcode values to cycle through; defaults to known samples.')
    parser.add_argument('--iterations', type=int, default=200, help='Number of barcode submissions to perform.')
    parser.add_argument('--delay-ms', type=int, default=75, help='Delay between scans to mimic hardware pacing.')
    parser.add_argument('--no-show-window', action='store_true', help='Keep the window hidden during the run.')
    parser.add_argument('--windowed', action='store_true', help='Show the window but avoid fullscreen mode.')
    parser.add_argument('--disable-fade', action='store_true', help='Skip the window fade animation to save a few frames.')
    parser.add_argument('--verbose', action='store_true', help='Log every scan instead of periodic checkpoints.')
    args = parser.parse_args()

    base_barcodes = args.barcodes or DEFAULT_BARCODES
    if not base_barcodes:
        print('No barcodes provided for the stress test.', file=sys.stderr)
        return 1

    status = run_stress_test(
        iterations=args.iterations,
        barcodes=base_barcodes,
        delay_ms=max(args.delay_ms, 0),
        show_window=not args.no_show_window,
        show_full_screen=not args.windowed,
        enable_fade=not args.disable_fade,
        verbose=args.verbose,
    )
    return status


if __name__ == '__main__':
    sys.exit(main())
