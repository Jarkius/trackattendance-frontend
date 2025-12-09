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
    const syncNowBtn = document.getElementById('sync-now-btn');
    const syncPendingCounter = document.getElementById('sync-pending');
    const syncSyncedCounter = document.getElementById('sync-synced');
    const syncFailedCounter = document.getElementById('sync-failed');
    const syncStatusMessage = document.getElementById('sync-status-message');

    if (!barcodeInput || !liveFeedbackName || !totalEmployeesCounter || !totalScannedCounter) {
        console.warn('Attendance UI missing required elements; event wiring skipped.');
        return;
    }

    let api;
    const apiQueue = [];
    let overlayHideTimer = null;
    const overlayIntent = {
        shouldClose: false,
    };

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
        if (overlayHideTimer) {
            window.clearTimeout(overlayHideTimer);
            overlayHideTimer = null;
        }
        exportOverlay.classList.remove('export-overlay--visible', 'export-overlay--error');
        exportOverlay.setAttribute('aria-hidden', 'true');
        if (exportOverlayConfirm) {
            exportOverlayConfirm.classList.add('export-overlay__button--hidden');
        }
    };

    const showExportOverlay = ({ ok, message, destination, autoHideMs = 0, showConfirm = true, title }) => {
        if (!exportOverlay) {
            if (!ok && message) {
                console.warn('Export overlay container missing; message:', message);
            }
            return;
        }
        if (overlayHideTimer) {
            window.clearTimeout(overlayHideTimer);
            overlayHideTimer = null;
        }
        const normalizedMessage = destination ? `${message}
${destination}` : message;
        if (exportOverlayMessage) {
            exportOverlayMessage.textContent = normalizedMessage;
        }
        if (exportOverlayTitle) {
            const heading = typeof title === 'string' && title.trim() ? title : (ok ? 'Export Complete' : 'Export Failed');
            exportOverlayTitle.textContent = heading;
        }
        exportOverlay.classList.add('export-overlay--visible');
        exportOverlay.classList.toggle('export-overlay--error', !ok);
        exportOverlay.setAttribute('aria-hidden', 'false');
        if (exportOverlayConfirm) {
            exportOverlayConfirm.classList.toggle('export-overlay__button--hidden', !showConfirm);
            if (showConfirm) {
                exportOverlayConfirm.focus();
            }
        }
        if (autoHideMs > 0) {
            overlayHideTimer = window.setTimeout(() => {
                overlayHideTimer = null;
                hideExportOverlay();
            }, autoHideMs);
        }
    };

    window.__handleExportShutdown = (payload = {}) => {
        const ok = Boolean(payload.ok);
        const baseMessage = typeof payload.message === 'string' ? payload.message.trim() : '';
        const destination = typeof payload.destination === 'string' ? payload.destination : '';
        const showConfirm = payload.showConfirm !== undefined ? Boolean(payload.showConfirm) : !ok;
        const titleText = typeof payload.title === 'string' ? payload.title : undefined;
        const autoHideMsRaw = typeof payload.autoHideMs === 'number' ? payload.autoHideMs : 0;
        const autoHideMs = Number.isNaN(autoHideMsRaw) ? 0 : Math.max(0, autoHideMsRaw);
        const shouldClose = Boolean(payload.shouldClose);
        overlayIntent.shouldClose = shouldClose;
        const message = baseMessage || (ok ? 'Attendance report exported successfully.' : 'Unable to export attendance report.');
        showExportOverlay({ ok, message, destination, autoHideMs, showConfirm, title: titleText });
        if (shouldClose) {
            const closeDelay = autoHideMs > 0 ? autoHideMs : 1500;
            window.setTimeout(() => {
                queueOrRun((bridge) => {
                    if (bridge.finalize_export_close) {
                        bridge.finalize_export_close();
                        return;
                    }
                    bridge.close_window();
                });
            }, closeDelay);
        }
    };

    window.__handleSyncExportShutdown = (payload = {}) => {
        const stage = payload.stage || 'sync';
        const ok = Boolean(payload.ok);
        const baseMessage = typeof payload.message === 'string' ? payload.message.trim() : '';
        const destination = typeof payload.destination === 'string' ? payload.destination : '';
        const showConfirm = payload.showConfirm !== undefined ? Boolean(payload.showConfirm) : false;
        const autoHideMsRaw = typeof payload.autoHideMs === 'number' ? payload.autoHideMs : 0;
        const autoHideMs = Number.isNaN(autoHideMsRaw) ? 0 : Math.max(0, autoHideMsRaw);
        const shouldClose = Boolean(payload.shouldClose);

        overlayIntent.shouldClose = shouldClose;

        let title = 'Closing Application';
        if (stage === 'sync') {
            title = ok ? 'Syncing Scans...' : 'Sync Warning';
        } else if (stage === 'export') {
            title = ok ? 'Exporting Data...' : 'Export Failed';
        } else if (stage === 'complete') {
            title = ok ? 'Ready to Close' : 'Warning';
        }

        const message = baseMessage || 'Processing...';
        showExportOverlay({ ok, message, destination, autoHideMs, showConfirm, title });

        if (shouldClose) {
            const closeDelay = autoHideMs > 0 ? autoHideMs : 1500;
            window.setTimeout(() => {
                queueOrRun((bridge) => {
                    if (bridge.finalize_export_close) {
                        bridge.finalize_export_close();
                        return;
                    }
                    bridge.close_window();
                });
            }, closeDelay);
        }
    };

    const returnFocusToInput = () => {
        window.setTimeout(() => {
            if (document.body.contains(barcodeInput)) {
                barcodeInput.focus();
            }
        }, 80);
    };

    // Duplicate Badge Alert Handler (Issue #21) - Uses export overlay pattern
    let duplicateOverlayTimeout = null;
    window.__handleDuplicateBadge = (payload = {}) => {
        const duplicateOverlay = document.getElementById('duplicate-overlay');
        const duplicateMessage = document.getElementById('duplicate-overlay-message');
        if (!duplicateOverlay || !duplicateMessage) {
            return;
        }

        // Clear any pending timeout
        if (duplicateOverlayTimeout) {
            window.clearTimeout(duplicateOverlayTimeout);
            duplicateOverlayTimeout = null;
        }

        const badgeId = payload.badgeId || 'Unknown';
        const fullName = payload.fullName || 'Badge scanned';
        const isError = payload.isError || false;  // true for block mode, false for warn mode

        // Build overlay message with user info
        const message = `Badge: ${badgeId}\nName: ${fullName}`;
        duplicateMessage.textContent = message;

        // Update styling based on error state
        duplicateOverlay.classList.toggle('duplicate-overlay--error', isError);

        // Show the overlay and disable barcode input to prevent further scans
        duplicateOverlay.classList.add('duplicate-overlay--visible');
        duplicateOverlay.setAttribute('aria-hidden', 'false');
        barcodeInput.disabled = true;

        // Auto-dismiss after configured duration
        const duration = payload.alertDurationMs || 3000;
        if (duration > 0) {
            duplicateOverlayTimeout = window.setTimeout(() => {
                duplicateOverlayTimeout = null;
                duplicateOverlay.classList.remove('duplicate-overlay--visible');
                duplicateOverlay.setAttribute('aria-hidden', 'true');
                barcodeInput.disabled = false;  // Re-enable input after overlay dismisses
                returnFocusToInput();
            }, duration);
        }
    };

    function adjustFeedbackSizing(content) {
        const message = typeof content === 'string' ? content : '';
        liveFeedbackName.style.fontSize = '';
        liveFeedbackName.classList.remove('feedback-name--compact', 'feedback-name--condensed', 'feedback-name--mini');
        if (message.length > 44) {
            liveFeedbackName.classList.add('feedback-name--mini');
        } else if (message.length > 32) {
            liveFeedbackName.classList.add('feedback-name--condensed');
        } else if (message.length > 22) {
            liveFeedbackName.classList.add('feedback-name--compact');
        }

        const container = liveFeedbackName.parentElement;
        const maxWidth = container ? container.clientWidth : liveFeedbackName.clientWidth;
        if (maxWidth > 0 && liveFeedbackName.scrollWidth > maxWidth) {
            const computed = window.getComputedStyle(liveFeedbackName);
            let currentSize = parseFloat(computed.fontSize) || 22;
            const minSize = 14;
            while (liveFeedbackName.scrollWidth > maxWidth && currentSize > minSize) {
                currentSize -= 1;
                liveFeedbackName.style.fontSize = `${currentSize}px`;
            }
        }
    }

    function setLiveFeedback(message, color = 'var(--deloitte-green)', resetDelayMs = 2000) {
        const normalizedMessage = typeof message === 'string' ? message : String(message ?? '');
        liveFeedbackName.textContent = normalizedMessage;
        adjustFeedbackSizing(normalizedMessage);
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
        scanHistoryList.innerHTML = "";
        entries.forEach((entry) => {
            const listItem = document.createElement('li');
            listItem.className = 'collection-item';
            const isMatched = Boolean(entry.matched);
            if (!isMatched) {
                listItem.classList.add('collection-item--unmatched');
            }

            const headerRow = document.createElement('span');
            headerRow.className = 'history-header';

            const nameText = document.createElement('span');
            nameText.className = 'history-label';
            nameText.textContent = isMatched
                ? (entry.fullName || entry.badgeId || 'Unknown')
                : (entry.badgeId || 'Unknown entry');
            headerRow.appendChild(nameText);

            const timestampText = formatTimestamp(entry.timestamp);
            if (timestampText) {
                const timestampNode = document.createElement('span');
                timestampNode.className = 'history-timestamp';
                timestampNode.textContent = timestampText;
                headerRow.appendChild(timestampNode);
            }

            listItem.appendChild(headerRow);

            const metaParts = [];

            if (isMatched) {
                if (entry.legacyId) {
                    metaParts.push(entry.legacyId);
                }
                if (entry.slL1Desc) {
                    metaParts.push(entry.slL1Desc);
                }
                if (entry.positionDesc) {
                    metaParts.push(entry.positionDesc);
                }
            } else {
                metaParts.push('Not matched - recorded for follow-up');
            }

            if (metaParts.length > 0) {
                const metaLine = document.createElement('span');
                metaLine.className = 'history-meta';
                metaLine.textContent = metaParts.join(' . ');
                listItem.appendChild(metaLine);
            }

            scanHistoryList.appendChild(listItem);
        });

        if (entries.length === 0) {
            const placeholder = document.createElement('li');
            placeholder.className = 'collection-item collection-item--placeholder';

            const placeholderHeader = document.createElement('span');
            placeholderHeader.className = 'history-header';

            const placeholderLabel = document.createElement('span');
            placeholderLabel.className = 'history-label';
            placeholderLabel.textContent = 'Awaiting first scan';
            placeholderHeader.appendChild(placeholderLabel);

            const placeholderTimestamp = document.createElement('span');
            placeholderTimestamp.className = 'history-timestamp';
            placeholderTimestamp.textContent = '--:--:--';
            placeholderHeader.appendChild(placeholderTimestamp);

            placeholder.appendChild(placeholderHeader);

            const placeholderMeta = document.createElement('span');
            placeholderMeta.className = 'history-meta';
            placeholderMeta.textContent = 'Scan a badge to populate recent history.';
            placeholder.appendChild(placeholderMeta);

            scanHistoryList.appendChild(placeholder);
        }
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
                updateSyncStatus();  // Load sync status on startup
                returnFocusToInput();
            });
        });
    };

    const handleScanResponse = (response) => {
        if (!response || response.ok === false) {
            const message = response?.message || 'Scan failed';
            setLiveFeedback(message, 'red', 3000);

            // Show duplicate badge alert if this is a duplicate rejection (block mode)
            if (response?.is_duplicate) {
                window.__handleDuplicateBadge({
                    badgeId: response.badgeId || 'Unknown',
                    fullName: response.fullName || 'Badge blocked',
                    isError: true,  // Red error styling for block mode
                    alertDurationMs: 3000,  // Show for 3 seconds
                });
            }
            return;
        }
        state.totalScansToday = response.totalScansToday ?? state.totalScansToday;
        state.totalScansOverall = response.totalScansOverall ?? state.totalScansOverall;
        state.history = Array.isArray(response.scanHistory) ? response.scanHistory : state.history;
        applyDashboardState();

        // Update sync status counters after new scan
        updateSyncStatus();

        const found = Boolean(response.matched);
        const badgeValue = response.badgeId || '';
        const message = found
            ? (response.fullName || badgeValue || 'Unknown')
            : 'Not matched';
        setLiveFeedback(message, found ? 'var(--deloitte-black)' : 'red');

        // Show duplicate badge alert if this is a duplicate scan (warn mode - accepted but flagged)
        if (response?.is_duplicate) {
            window.__handleDuplicateBadge({
                badgeId: response.badgeId || 'Unknown',
                fullName: response.fullName || 'Unknown',
                isError: false,  // Yellow warning styling for warn mode
                alertDurationMs: 3000,  // Show for 3 seconds
            });
        }
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

            showExportOverlay({
                ok: true,
                message: 'Generating attendance report...',
                title: 'Exporting attendance report...',
                destination: '',
                showConfirm: false,
                autoHideMs: 0,
            });

            bridge.export_scans((result) => {
                exportBtn.disabled = false;
                exportBtn.innerHTML = '<i class="material-icons">file_download</i>Export Data';

                const success = Boolean(result && result.ok);
                const destination = typeof result?.absolutePath === 'string'
                    ? result.absolutePath
                    : (typeof result?.fileName === 'string' ? result.fileName : '');
                const payload = {
                    ok: success,
                    message: success ? (result?.message || '') : (result?.message || 'Unable to export attendance report.'),
                    destination,
                    showConfirm: success ? false : true,
                    autoHideMs: success ? 2500 : 0,
                    shouldClose: false,
                };

                window.__handleExportShutdown(payload);
                returnFocusToInput();
            });
        });
    };

    const updateSyncStatus = () => {
        queueOrRun((bridge) => {
            if (!bridge.get_sync_status) {
                return;
            }
            bridge.get_sync_status((stats) => {
                if (syncPendingCounter) {
                    syncPendingCounter.textContent = Number(stats?.pending ?? 0).toLocaleString();
                }
                if (syncSyncedCounter) {
                    syncSyncedCounter.textContent = Number(stats?.synced ?? 0).toLocaleString();
                }
                if (syncFailedCounter) {
                    syncFailedCounter.textContent = Number(stats?.failed ?? 0).toLocaleString();
                }
            });
        });
    };

    const handleSyncNow = () => {
        queueOrRun((bridge) => {
            if (!bridge.sync_now) {
                if (syncStatusMessage) {
                    syncStatusMessage.textContent = 'Sync service not available';
                    syncStatusMessage.style.color = 'red';
                }
                return;
            }

            syncNowBtn.disabled = true;
            syncNowBtn.innerHTML = '<i class="material-icons sync-spinning">sync</i>';
            syncNowBtn.title = 'Syncing...';
            if (syncStatusMessage) {
                syncStatusMessage.textContent = 'Testing connection...';
                syncStatusMessage.style.color = '#00A3E0';  // Match sync button color
            }

            bridge.sync_now((result) => {
                syncNowBtn.disabled = false;
                syncNowBtn.innerHTML = '<i class="material-icons">sync</i>';
                syncNowBtn.title = 'Sync Now';

                const success = Boolean(result && result.ok);
                if (syncStatusMessage) {
                    syncStatusMessage.textContent = result?.message || (success ? 'Sync complete!' : 'Sync failed');
                    syncStatusMessage.style.color = success ? '#00A3E0' : 'red';  // Blue for success, red for error

                    // Clear message after 5 seconds
                    window.setTimeout(() => {
                        syncStatusMessage.textContent = '';
                    }, 5000);
                }

                // Update sync statistics (with small delay to ensure DB is updated)
                setTimeout(updateSyncStatus, 100);
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
            if (overlayIntent.shouldClose) {
                overlayIntent.shouldClose = false;
                queueOrRun((bridge) => {
                    if (bridge.finalize_export_close) {
                        bridge.finalize_export_close();
                        return;
                    }
                    bridge.close_window();
                });
            }
        });
    }

    if (exportBtn) {
        exportBtn.addEventListener('click', (event) => {
            event.preventDefault();
            handleExport();
        });
    }

    if (syncNowBtn) {
        syncNowBtn.addEventListener('click', (event) => {
            event.preventDefault();
            handleSyncNow();
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
