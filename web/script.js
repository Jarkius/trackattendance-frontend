document.addEventListener('DOMContentLoaded', () => {
    const state = {
        totalEmployees: 0,
        totalScansToday: 0,
        totalScansOverall: 0,
        history: [],
        stationName: '--',
    };

    const barcodeInput = document.getElementById('barcode-input');
    const liveFeedbackName = document.getElementById('live-feedback-name');
    const stationNameLabel = document.getElementById('station-name');
    const totalEmployeesCounter = document.getElementById('total-employees');
    const totalScannedCounter = document.getElementById('total-scanned');
    const scanHistoryList = document.getElementById('scan-history-list');
    const closeBtn = document.getElementById('close-btn');
    const exportBtn = document.getElementById('export-data-btn');
    const exportOverlay = document.getElementById('export-overlay');
    const exportOverlayTitle = document.getElementById('export-overlay-title');
    const exportOverlayMessage = document.getElementById('export-overlay-message');
    const exportOverlayConfirm = document.getElementById('export-overlay-confirm');

    if (!barcodeInput || !liveFeedbackName || !totalEmployeesCounter || !totalScannedCounter) {
        console.warn('Attendance UI missing required elements; event wiring skipped.');
        return;
    }

    let api;
    const apiQueue = [];

    const flushApiQueue = () => {
        if (!api) {
            return;
        }
        apiQueue.splice(0).forEach((callback) => callback(api));
    };

    if (window.qt && window.qt.webChannelTransport) {
        new QWebChannel(window.qt.webChannelTransport, (channel) => {
            api = channel.objects.api;
            flushApiQueue();
            loadInitialData();
        });
    } else {
        console.warn('Qt WebChannel transport not available; desktop integration disabled.');
        setLiveFeedback('Desktop bridge unavailable', 'red');
    }

    const queueOrRun = (callback) => {
        if (api) {
            callback(api);
            return;
        }
        apiQueue.push(callback);
    };

    const hideExportOverlay = () => {
        if (!exportOverlay) {
            return;
        }
        exportOverlay.classList.remove('export-overlay--visible', 'export-overlay--error');
        exportOverlay.setAttribute('aria-hidden', 'true');
    };

    const showExportOverlay = ({ ok, message, destination }) => {
        if (!exportOverlay) {
            if (!ok && message) {
                console.warn('Export overlay container missing; message:', message);
            }
            return;
        }
        const normalizedMessage = destination ? `${message}
${destination}` : message;
        exportOverlayMessage.textContent = normalizedMessage;
        if (exportOverlayTitle) {
            exportOverlayTitle.textContent = ok ? 'Export Complete' : 'Export Failed';
        }
        exportOverlay.classList.toggle('export-overlay--error', !ok);
        exportOverlay.classList.add('export-overlay--visible');
        exportOverlay.setAttribute('aria-hidden', 'false');
        if (exportOverlayConfirm) {
            exportOverlayConfirm.focus();
        }
    };

    window.__handleExportShutdown = (payload) => {
        const data = payload || {};
        const ok = Boolean(data.ok);
        const baseMessage = typeof data.message === 'string' ? data.message.trim() : '';
        const destination = typeof data.destination === 'string' ? data.destination : '';
        const message = baseMessage || (ok ? 'Attendance report exported successfully.' : 'Unable to export attendance report.');
        showExportOverlay({ ok, message, destination });
    };

    const returnFocusToInput = () => {
        window.setTimeout(() => {
            if (document.body.contains(barcodeInput)) {
                barcodeInput.focus();
            }
        }, 80);
    };

    function adjustFeedbackSizing(content) {
        const message = typeof content === 'string' ? content : '';
        liveFeedbackName.classList.remove('feedback-name--compact', 'feedback-name--condensed');
        if (message.length > 32) {
            liveFeedbackName.classList.add('feedback-name--condensed');
        } else if (message.length > 22) {
            liveFeedbackName.classList.add('feedback-name--compact');
        }
    }

    function setLiveFeedback(message, color = 'var(--deloitte-green)', resetDelayMs = 2000) {
        adjustFeedbackSizing(message);
        liveFeedbackName.textContent = message;
        liveFeedbackName.style.color = color;
        if (resetDelayMs > 0) {
            window.setTimeout(() => {
                const defaultMessage = 'Ready to scan...';
                liveFeedbackName.textContent = defaultMessage;
                adjustFeedbackSizing(defaultMessage);
                liveFeedbackName.style.color = 'var(--deloitte-green)';
            }, resetDelayMs);
        }
    }

    const formatTimestamp = (isoValue) => {
        if (!isoValue) {
            return '';
        }
        const parsed = new Date(isoValue);
        if (Number.isNaN(parsed.getTime())) {
            return isoValue;
        }
        return parsed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    };

    const renderHistory = (entries) => {
        if (!scanHistoryList) {
            return;
        }
        scanHistoryList.innerHTML = '';
        entries.forEach((entry) => {
            const listItem = document.createElement('li');
            listItem.className = 'collection-item';
            listItem.innerHTML = `<span class="name">${entry.fullName}</span><span class="timestamp">${formatTimestamp(entry.timestamp)}</span>`;
            scanHistoryList.appendChild(listItem);
        });
    };

    const applyDashboardState = () => {
        if (stationNameLabel) {
            stationNameLabel.textContent = state.stationName || '--';
        }
        totalEmployeesCounter.textContent = Number(state.totalEmployees).toLocaleString();
        totalScannedCounter.textContent = Number(state.totalScansToday).toLocaleString();
        renderHistory(state.history);
    };

    const loadInitialData = () => {
        queueOrRun((bridge) => {
            bridge.get_initial_data((payload) => {
                state.totalEmployees = payload?.totalEmployees ?? 0;
                state.totalScansToday = payload?.totalScansToday ?? 0;
                state.totalScansOverall = payload?.totalScansOverall ?? 0;
                state.stationName = payload?.stationName ?? '--';
                state.history = Array.isArray(payload?.scanHistory) ? payload.scanHistory : [];
                applyDashboardState();
                returnFocusToInput();
            });
        });
    };

    const handleScanResponse = (response) => {
        if (!response || response.ok === false) {
            const message = response?.message || 'Scan failed';
            setLiveFeedback(message, 'red', 3000);
            return;
        }
        state.totalScansToday = response.totalScansToday ?? state.totalScansToday;
        state.totalScansOverall = response.totalScansOverall ?? state.totalScansOverall;
        state.history = Array.isArray(response.scanHistory) ? response.scanHistory : state.history;
        applyDashboardState();

        const found = Boolean(response.matched);
        const nameToShow = response.fullName || 'Unknown';
        setLiveFeedback(nameToShow, found ? 'var(--deloitte-black)' : 'red');
    };

    const submitScan = (badgeValue) => {
        const badge = badgeValue.trim();
        if (!badge) {
            return;
        }
        queueOrRun((bridge) => {
            bridge.submit_scan(badge, (response) => {
                handleScanResponse(response);
                barcodeInput.value = '';
                returnFocusToInput();
            });
        });
    };

    const handleExport = () => {
        queueOrRun((bridge) => {
            exportBtn.disabled = true;
            exportBtn.innerHTML = '<i class="material-icons">hourglass_empty</i>Exporting...';
            bridge.export_scans((result) => {
                exportBtn.disabled = false;
                exportBtn.innerHTML = '<i class="material-icons">file_download</i>Export Data';
                if (!result || result.ok === false) {
                    const message = result?.message || 'Export failed';
                    setLiveFeedback(message, 'red', 3000);
                } else {
                    const successMessage = `Exported ${result.fileName || 'Checkins.xlsx'}`;
                    setLiveFeedback(successMessage, 'var(--deloitte-green)', 4000);
                }
                returnFocusToInput();
            });
        });
    };

    barcodeInput.addEventListener('keyup', (event) => {
        if (event.key === 'Enter') {
            submitScan(barcodeInput.value);
        }
    });

    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            queueOrRun((bridge) => bridge.close_window());
        });
    }

    if (exportOverlayConfirm) {
        exportOverlayConfirm.addEventListener('click', (event) => {
            event.preventDefault();
            hideExportOverlay();
            queueOrRun((bridge) => {
                if (bridge.finalize_export_close) {
                    bridge.finalize_export_close();
                    return;
                }
                bridge.close_window();
            });
        });
    }

    if (exportBtn) {
        exportBtn.addEventListener('click', (event) => {
            event.preventDefault();
            handleExport();
        });
    }

    document.addEventListener('click', (event) => {
        if (event.target !== barcodeInput) {
            returnFocusToInput();
        }
    });
    document.addEventListener('scroll', returnFocusToInput, true);
    if (scanHistoryList) {
        scanHistoryList.addEventListener('scroll', returnFocusToInput);
    }
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            queueOrRun((bridge) => bridge.close_window());
            return;
        }
        if (event.target !== barcodeInput && event.key.length === 1) {
            returnFocusToInput();
        }
    });
    window.addEventListener('focus', returnFocusToInput);
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
            returnFocusToInput();
        }
    });
    document.addEventListener('mouseup', returnFocusToInput);
    document.addEventListener('touchend', returnFocusToInput);

    applyDashboardState();
    returnFocusToInput();
});
