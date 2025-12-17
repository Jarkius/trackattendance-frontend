// Debug Console Setup (temporary debugging)
const debugConsole = {
    element: null,
    output: null,
    messages: [],

    init() {
        this.element = document.getElementById('debug-console');
        this.output = document.getElementById('debug-output');

        // Override console.log, console.info, console.warn, console.error
        const originalLog = console.log;
        const originalInfo = console.info;
        const originalWarn = console.warn;
        const originalError = console.error;
        const originalDebug = console.debug;

        const self = this;
        console.log = (...args) => {
            originalLog(...args);
            self.addMessage('LOG', args);
        };
        console.info = (...args) => {
            originalInfo(...args);
            self.addMessage('INFO', args);
        };
        console.warn = (...args) => {
            originalWarn(...args);
            self.addMessage('WARN', args);
        };
        console.error = (...args) => {
            originalError(...args);
            self.addMessage('ERROR', args);
        };
        console.debug = (...args) => {
            originalDebug(...args);
            self.addMessage('DEBUG', args);
        };

        // Keyboard shortcut: Ctrl+Shift+D to toggle debug console
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.shiftKey && e.key === 'D') {
                e.preventDefault();
                self.toggle();
            }
        });
    },

    addMessage(level, args) {
        const msg = args.map(arg => {
            if (typeof arg === 'object') {
                try {
                    return JSON.stringify(arg);
                } catch {
                    return String(arg);
                }
            }
            return String(arg);
        }).join(' ');

        const timestamp = new Date().toLocaleTimeString();
        const line = `[${timestamp}] ${level}: ${msg}`;
        this.messages.push(line);

        if (this.output) {
            const p = document.createElement('div');
            p.textContent = line;
            p.style.color = level === 'ERROR' ? '#f00' : level === 'WARN' ? '#ff0' : '#0f0';
            this.output.appendChild(p);
            this.output.scrollTop = this.output.scrollHeight;

            // Keep last 50 messages
            while (this.messages.length > 50) {
                this.messages.shift();
                if (this.output.firstChild) {
                    this.output.removeChild(this.output.firstChild);
                }
            }
        }
    },

    toggle() {
        if (this.element) {
            this.element.style.display = this.element.style.display === 'none' ? 'block' : 'none';
        }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    debugConsole.init();
    console.info('Debug console initialized - Press Ctrl+Shift+D to toggle');

    const state = {
        totalEmployees: 0,
        totalScansToday: 0,
        totalScansOverall: 0,
        history: [],
        stationName: '--',
    };

    // Debug mode flag - disable auto-focus when debugging
    let debugMode = false;

    // Duplicate badge alert configuration
    let duplicateBadgeAlertDurationMs = 3000;  // Default: 3 seconds

    // Connection status polling with hysteresis to prevent flicker and reduce API calls
    const DEFAULT_CONNECTION_CHECK_INTERVAL_MS = 60000;  // 60 seconds (not 10!) to reduce API cost
    const DEFAULT_CONNECTION_CHECK_INITIAL_DELAY_MS = 15000;  // 15 seconds - wait for UI to render
    const CONNECTION_CHECK_FALLBACK_MS = 15000;  // Timeout if no signal after 15s
    const CONNECTION_HYSTERESIS_THRESHOLD = 2;  // Require 2 consecutive failures before showing red
    let connectionCheckIntervalMs = DEFAULT_CONNECTION_CHECK_INTERVAL_MS;
    let connectionCheckInitialDelayMs = DEFAULT_CONNECTION_CHECK_INITIAL_DELAY_MS;
    let consecutiveFailures = 0;  // Track failures for hysteresis
    let connectionState = 'unknown';  // 'unknown' | 'online' | 'offline'
    let initialDelayCompleted = false;  // Track if initial delay has passed
    const barcodeInput = document.getElementById('barcode-input');
    const liveFeedbackName = document.getElementById('live-feedback-name');
    const welcomeHeading = document.getElementById('welcome-heading');
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
    const connectionStatusDot = document.getElementById('connection-status');

    // Dashboard overlay elements (Issue #27)
    const dashboardIcon = document.getElementById('dashboard-icon');
    const dashboardOverlay = document.getElementById('dashboard-overlay');
    const dashboardClose = document.getElementById('dashboard-close');
    const dashboardRegistered = document.getElementById('dashboard-registered');
    const dashboardScanned = document.getElementById('dashboard-scanned');
    const dashboardRate = document.getElementById('dashboard-rate');
    const dashboardStationsBody = document.getElementById('dashboard-stations-body');
    const dashboardBuBody = document.getElementById('dashboard-bu-body');
    const dashboardUpdated = document.getElementById('dashboard-updated');
    const dashboardExportBtn = document.getElementById('dashboard-export');
    const dashboardRefreshBtn = document.getElementById('dashboard-refresh');

    if (!barcodeInput || !liveFeedbackName || !totalEmployeesCounter || !totalScannedCounter) {
        console.warn('Attendance UI missing required elements; event wiring skipped.');
        return;
    }

    let api;
    let webChannelReady = false;
    let connectionStatusIntervalId = null;
    let connectionCheckInFlight = false;
    let connectionCheckTimeoutId = null;
    let dashboardOpen = false;  // Flag to skip connection checks while dashboard is open
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

    const queueOrRun = (callback) => {
        if (api) {
            callback(api);
            return;
        }
        apiQueue.push(callback);
    };

    const setConnectionStatus = (status = 'unknown', message = '') => {
        console.debug('[ConnectionSignal] setConnectionStatus called', { status, message, hasDot: !!connectionStatusDot });
        if (!connectionStatusDot) {
            console.warn('[ConnectionSignal] Connection status dot not found!');
            return;
        }
        connectionStatusDot.classList.remove('connection-status--unknown', 'connection-status--online', 'connection-status--offline', 'connection-status--checking');
        const normalizedStatus = status === 'online'
            ? 'connection-status--online'
            : status === 'checking'
                ? 'connection-status--checking'
                : status === 'offline'
                    ? 'connection-status--offline'
                    : 'connection-status--unknown';  // Default to unknown/black for all other states
        connectionStatusDot.classList.add(normalizedStatus);
        console.debug('[ConnectionSignal] Applied class:', normalizedStatus, 'Current classes:', connectionStatusDot.className);

        const fallbackLabel = status === 'online' ? 'API connected' : 'API offline';
        const label = message && typeof message === 'string' ? message : fallbackLabel;
        connectionStatusDot.setAttribute('aria-label', label);
        connectionStatusDot.setAttribute('title', label);
    };

    const clearConnectionGuard = () => {
        if (connectionCheckTimeoutId !== null) {
            console.debug('[ConnectionSignal] Clearing timeout guard');
            window.clearTimeout(connectionCheckTimeoutId);
            connectionCheckTimeoutId = null;
        }
    };

    const handleConnectionStatusPayload = (payload) => {
        clearConnectionGuard();
        console.info('[ConnectionSignal] Handling payload:', payload);
        const isOk = Boolean(payload && payload.ok);
        const message = payload?.message || (isOk ? 'Connected to API' : 'Cannot reach API');

        // Hysteresis logic: prevent flicker from transient failures
        if (isOk) {
            // If connection is OK, reset failure counter and show green immediately
            consecutiveFailures = 0;
            if (connectionState !== 'online') {
                connectionState = 'online';
                console.info('[ConnectionSignal] Connection restored (hysteresis: failures reset)');
            }
            // Always update visual to online when connection succeeds
            // (even if already online, to override the 'checking' state set earlier)
            setConnectionStatus('online', message);
        } else {
            // If connection failed, increment failure counter
            consecutiveFailures++;
            console.info(`[ConnectionSignal] Connection check failed (${consecutiveFailures}/${CONNECTION_HYSTERESIS_THRESHOLD})`);

            // Only show offline after N consecutive failures (prevents flicker from transient issues)
            if (consecutiveFailures >= CONNECTION_HYSTERESIS_THRESHOLD && connectionState !== 'offline') {
                connectionState = 'offline';
                console.warn('[ConnectionSignal] Connection lost (hysteresis threshold reached)');
                setConnectionStatus('offline', message);
            }
        }

        connectionCheckInFlight = false;
        localStorage.setItem('connectionDebug_state', JSON.stringify({
            state: connectionState,
            consecutiveFailures,
            hysteresisThreshold: CONNECTION_HYSTERESIS_THRESHOLD,
            lastMessage: message
        }));
    };

    const refreshConnectionStatus = () => {
        if (dashboardOpen) {
            console.debug('[ConnectionSignal] Dashboard open, skipping connection check');
            return;
        }
        if (!connectionStatusDot) {
            return;
        }
        if (connectionCheckIntervalMs === 0) {
            return;
        }
        if (!webChannelReady) {
            setConnectionStatus('offline', 'Desktop bridge unavailable');
            return;
        }
        if (connectionCheckInFlight) {
            console.debug('[ConnectionSignal] Check already in flight, skipping');
            return;
        }
        console.info('[ConnectionSignal] Starting connection check');
        connectionCheckInFlight = true;
        clearConnectionGuard();
        connectionCheckTimeoutId = window.setTimeout(() => {
            connectionCheckTimeoutId = null;
            if (!connectionCheckInFlight) {
                console.debug('[ConnectionSignal] Timeout fired but check already completed');
                return;
            }
            console.warn('[ConnectionSignal] Connection check timed out after', CONNECTION_CHECK_FALLBACK_MS, 'ms');
            handleConnectionStatusPayload({ ok: false, message: 'Connection check timed out' });
        }, CONNECTION_CHECK_FALLBACK_MS);
        // Note: Don't show 'checking' state - keep current state (green/grey) during checks with hysteresis
        queueOrRun((bridge) => {
            if (!bridge.test_cloud_connection) {
                setConnectionStatus('offline', 'Connection check unavailable');
                connectionCheckInFlight = false;
                return;
            }
            // Non-blocking: result delivered via connection_status_changed signal
            try {
                bridge.test_cloud_connection();
            } catch (err) {
                setConnectionStatus('offline', 'Connection check error');
                connectionCheckInFlight = false;
                clearConnectionGuard();
            }
        });
    };

    const startConnectionStatusPolling = () => {
        if (!connectionStatusDot || connectionCheckIntervalMs <= 0) {
            console.warn('[ConnectionSignal] Polling disabled or dot not found');
            return;
        }
        if (connectionStatusIntervalId !== null) {
            window.clearInterval(connectionStatusIntervalId);
            connectionStatusIntervalId = null;
        }
        console.info('[ConnectionSignal] Starting polling every', connectionCheckIntervalMs, 'ms');
        connectionStatusIntervalId = window.setInterval(() => {
            refreshConnectionStatus();
        }, connectionCheckIntervalMs);
    };

    const stopConnectionStatusPolling = () => {
        if (connectionStatusIntervalId !== null) {
            window.clearInterval(connectionStatusIntervalId);
            connectionStatusIntervalId = null;
        }
    };

    const applyConnectionIntervalFromPayload = (payload) => {
        const configuredInterval = Number(payload?.connectionCheckIntervalMs);
        if (Number.isFinite(configuredInterval) && configuredInterval >= 0) {
            connectionCheckIntervalMs = configuredInterval;
            // Don't start polling here - it will be started after the initial delay
            console.info('[Config] Connection check interval:', connectionCheckIntervalMs, 'ms (polling deferred)');
            return;
        }
        connectionCheckIntervalMs = DEFAULT_CONNECTION_CHECK_INTERVAL_MS;
    };

    const applyConnectionInitialDelayFromPayload = (payload) => {
        const configuredDelay = Number(payload?.connectionCheckInitialDelayMs);
        if (Number.isFinite(configuredDelay) && configuredDelay >= 0) {
            connectionCheckInitialDelayMs = configuredDelay;
            console.info('[Config] Connection check initial delay:', connectionCheckInitialDelayMs, 'ms');
            return;
        }
        connectionCheckInitialDelayMs = DEFAULT_CONNECTION_CHECK_INITIAL_DELAY_MS;
    };

    const bindConnectionSignal = () => {
        const debug = {
            hasApi: !!api,
            hasSignal: !!(api && api.connection_status_changed),
            hasConnect: !!(api && api.connection_status_changed && api.connection_status_changed.connect),
        };
        console.debug('[ConnectionSignal] bindConnectionSignal called', debug);
        localStorage.setItem('connectionDebug_bindCalled', JSON.stringify(debug));

        if (!api || !api.connection_status_changed || !api.connection_status_changed.connect) {
            console.warn('[ConnectionSignal] Signal connection failed - missing component');
            localStorage.setItem('connectionDebug_bindFailed', 'missing component');
            return;
        }
        try {
            api.connection_status_changed.connect((payload) => {
                console.debug('[ConnectionSignal] Signal fired', payload);
                localStorage.setItem('connectionDebug_signalFired', JSON.stringify(payload));
                handleConnectionStatusPayload(payload);
            });
            console.info('[ConnectionSignal] Successfully connected to connection_status_changed signal');
            localStorage.setItem('connectionDebug_bindSuccess', 'true');
        } catch (err) {
            console.error('[ConnectionSignal] Failed to connect signal:', err);
            localStorage.setItem('connectionDebug_bindError', String(err));
        }
    };

    if (window.qt && window.qt.webChannelTransport) {
        new QWebChannel(window.qt.webChannelTransport, (channel) => {
            console.info('[QWebChannel] Connected, got api object');
            webChannelReady = true;
            api = channel.objects.api;
            console.info('[QWebChannel] API object assigned, attempting signal binding');
            console.debug('[QWebChannel] api properties:', {
                hasConnectionStatusChanged: !!api.connection_status_changed,
                connectionStatusChangedType: typeof api.connection_status_changed,
                hasConnect: !!(api.connection_status_changed && typeof api.connection_status_changed.connect === 'function'),
            });
            bindConnectionSignal();
            flushApiQueue();
            loadInitialData();
            // Don't refresh connection status here - loadInitialData() handles the 15s delay
        });
    } else {
        console.warn('Qt WebChannel transport not available; desktop integration disabled.');
        setLiveFeedback('Desktop bridge unavailable', 'red');
        setConnectionStatus('offline', 'Desktop bridge unavailable');
    }



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
        // Skip auto-focus when in debug mode (allows copying debug console text)
        if (debugMode) {
            return;
        }
        // Skip auto-focus while dashboard is open
        if (dashboardOpen) {
            return;
        }
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
        const duplicateTitle = document.getElementById('duplicate-overlay-title');
        const duplicateBadge = document.getElementById('duplicate-overlay-badge');
        const duplicateName = document.getElementById('duplicate-overlay-name');
        const duplicateMessage = document.getElementById('duplicate-overlay-message');
        if (!duplicateOverlay || !duplicateTitle || !duplicateBadge || !duplicateName || !duplicateMessage) {
            return;
        }

        // Clear any pending timeout
        if (duplicateOverlayTimeout) {
            window.clearTimeout(duplicateOverlayTimeout);
            duplicateOverlayTimeout = null;
        }

        const badgeId = payload.badgeId || 'Unknown';
        const fullName = payload.fullName || 'Unknown';
        const message = payload.message || '';
        const isError = payload.isError || false;  // true for block mode, false for warn mode

        // Set title - always "DUPLICATED" for professional tone
        duplicateTitle.textContent = 'DUPLICATED';

        // Populate badge ID, full name, and message in separate elements
        duplicateBadge.textContent = badgeId;
        duplicateName.textContent = fullName;
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

    // Welcome heading animation helpers - using inline styles for PyQt compatibility
    const animateWelcomeSuccess = () => {
        console.log('[Welcome Animation] animateWelcomeSuccess called');
        if (!welcomeHeading) {
            console.warn('[Welcome Animation] welcomeHeading element not found!');
            return;
        }
        // Apply green color and pulse animation via inline styles
        welcomeHeading.style.color = '#86bc25';
        welcomeHeading.style.transform = 'scale(1)';
        welcomeHeading.style.textShadow = '0 0 0 rgba(134, 188, 37, 0)';

        // Force reflow then animate
        void welcomeHeading.offsetWidth;

        // Animate to scaled state with glow
        welcomeHeading.style.transition = 'all 0.3s ease-out';
        welcomeHeading.style.transform = 'scale(1.08)';
        welcomeHeading.style.textShadow = '0 0 25px rgba(134, 188, 37, 0.6)';

        // Settle to final state after pulse
        setTimeout(() => {
            if (welcomeHeading) {
                welcomeHeading.style.transform = 'scale(1.05)';
                welcomeHeading.style.textShadow = '0 0 15px rgba(134, 188, 37, 0.4)';
            }
        }, 300);

        console.log('[Welcome Animation] Applied green color and pulse animation');
    };

    const resetWelcomeStyle = () => {
        if (!welcomeHeading) return;
        // Reset to original grey color
        welcomeHeading.style.transition = 'all 0.3s ease-out';
        welcomeHeading.style.color = '#8c8c8c';
        welcomeHeading.style.transform = 'scale(1)';
        welcomeHeading.style.textShadow = 'none';
        console.log('[Welcome Animation] Reset to grey');
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
                // Reset welcome heading animation when feedback resets
                resetWelcomeStyle();
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
                applyConnectionIntervalFromPayload(payload);
                applyConnectionInitialDelayFromPayload(payload);
                debugMode = Boolean(payload?.debugMode);
                if (debugMode) {
                    console.info('[DEBUG] Debug mode enabled - auto-focus disabled');
                }
                duplicateBadgeAlertDurationMs = Math.max(0, Number(payload?.duplicateBadgeAlertDurationMs) || 3000);
                console.info('[Config] Duplicate badge alert duration:', duplicateBadgeAlertDurationMs, 'ms');
                // Signal binding already done in QWebChannel setup, don't rebind here
                state.totalEmployees = payload?.totalEmployees ?? 0;
                state.totalScansToday = payload?.totalScansToday ?? 0;
                state.totalScansOverall = payload?.totalScansOverall ?? 0;
                state.stationName = payload?.stationName ?? '--';
                state.history = Array.isArray(payload?.scanHistory) ? payload.scanHistory : [];
                applyDashboardState();
                updateSyncStatus();  // Load sync status on startup
                // Delay connection check to reduce initial load time
                // Indicator starts black (invisible), so no rush to show status
                // Uses configurable delay from CONNECTION_CHECK_INITIAL_DELAY_SECONDS
                window.setTimeout(() => {
                    console.info('[ConnectionSignal] Initial delay expired, starting connection checks');
                    initialDelayCompleted = true;  // Allow event listeners to trigger checks now
                    refreshConnectionStatus();  // Check API connectivity after UI renders
                    startConnectionStatusPolling();  // Start periodic polling after first check
                }, connectionCheckInitialDelayMs);
                returnFocusToInput();
            });
        });
    };

    const handleScanResponse = (response) => {
        if (!response || response.ok === false) {
            const message = response?.message || 'Scan failed';

            // Show duplicate badge alert if this is a duplicate rejection (block mode)
            if (response?.is_duplicate) {
                window.__handleDuplicateBadge({
                    badgeId: response.badgeId || 'Unknown',
                    fullName: response.fullName || 'Badge blocked',
                    message: message,  // Pass the error message
                    isError: true,  // Red error styling for block mode
                    alertDurationMs: duplicateBadgeAlertDurationMs,
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

        // Animate welcome heading on successful matched scan
        if (found) {
            animateWelcomeSuccess();
        }

        // Show duplicate badge alert if this is a duplicate scan (warn mode - accepted but flagged)
        if (response?.is_duplicate) {
            window.__handleDuplicateBadge({
                badgeId: response.badgeId || 'Unknown',
                fullName: response.fullName || 'Unknown',
                message: 'Scanned within 5 minutes',  // Inform user about time window
                isError: false,  // Yellow warning styling for warn mode
                alertDurationMs: duplicateBadgeAlertDurationMs,
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

            bridge.export_scans((result) => {
                exportBtn.disabled = false;
                exportBtn.innerHTML = '<i class="material-icons">file_download</i>Export Data';

                // No data - just show feedback, no modal
                if (result?.noData) {
                    setLiveFeedback('No scan data to export', 'var(--deloitte-grey-medium)', 2000);
                    returnFocusToInput();
                    return;
                }

                // Show result in modal
                const success = Boolean(result && result.ok);
                const destination = typeof result?.absolutePath === 'string'
                    ? result.absolutePath
                    : (typeof result?.fileName === 'string' ? result.fileName : '');

                showExportOverlay({
                    ok: success,
                    message: success ? 'Attendance report exported successfully.' : (result?.message || 'Unable to export attendance report.'),
                    destination,
                    showConfirm: !success,
                    autoHideMs: success ? 2500 : 0,
                });
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

    // Dashboard overlay functions (Issue #27)
    const showDashboardOverlay = () => {
        if (!dashboardOverlay) return;

        // Set flag to skip connection checks while dashboard is open
        dashboardOpen = true;
        console.debug('[Dashboard] Dashboard opened - connection checks paused');

        // Prevent scrolling on background page
        document.body.classList.add('dashboard-open');
        console.debug('[Dashboard] Prevented background scrolling');

        dashboardOverlay.classList.add('dashboard-overlay--visible');
        dashboardOverlay.setAttribute('aria-hidden', 'false');

        // Pause connection polling while dashboard is open to prevent conflicts
        if (connectionStatusIntervalId !== null) {
            window.clearInterval(connectionStatusIntervalId);
            connectionStatusIntervalId = null;
            console.debug('[Dashboard] Paused connection polling interval');
        }

        // Disable barcode input to prevent accidental scans while viewing dashboard
        if (barcodeInput) {
            barcodeInput.disabled = true;
            console.debug('[Dashboard] Disabled barcode input');
        }

        // Hide sync status message to prevent layout shift
        if (syncStatusMessage) {
            syncStatusMessage.style.display = 'none';
            console.debug('[Dashboard] Hidden sync status message');
        }

        // Initialize with loading state
        if (dashboardRegistered) dashboardRegistered.textContent = '--';
        if (dashboardScanned) dashboardScanned.textContent = '--';
        if (dashboardRate) dashboardRate.textContent = '--';
        if (dashboardStationsBody) {
            dashboardStationsBody.innerHTML = '<div class="dash__empty">Loading...</div>';
        }
        if (dashboardBuBody) {
            dashboardBuBody.innerHTML = '<div class="dash__empty">Loading...</div>';
        }
        // Show spinning icon in message area
        if (dashboardUpdated) {
            dashboardUpdated.innerHTML = '<i class="material-icons sync-spinning" style="font-size: 14px; vertical-align: middle;">sync</i> Loading...';
        }

        // Fetch data from Python bridge
        fetchDashboardData();
    };

    const hideDashboardOverlay = () => {
        if (!dashboardOverlay) return;

        // Clear flag to resume connection checks
        dashboardOpen = false;

        // Hide immediately (no animation to prevent flickering on app close)
        dashboardOverlay.classList.remove('dashboard-overlay--visible');
        dashboardOverlay.setAttribute('aria-hidden', 'true');

        // Restore background scrolling
        document.body.classList.remove('dashboard-open');
        console.debug('[Dashboard] Dashboard closed');

        // Resume connection polling
        if (connectionStatusIntervalId === null && connectionCheckIntervalMs > 0) {
            startConnectionStatusPolling();
        }

        // Re-enable barcode input
        if (barcodeInput) {
            barcodeInput.disabled = false;
        }

        // Restore sync status message
        if (syncStatusMessage) {
            syncStatusMessage.style.display = '';
        }

        returnFocusToInput();
    };

    const fetchDashboardData = () => {
        console.debug('[Dashboard] Fetch data started');
        queueOrRun((bridge) => {
            console.debug('[Dashboard] Bridge callback executing');
            if (!bridge.get_dashboard_data) {
                console.warn('[Dashboard] get_dashboard_data not available');
                updateDashboardUI({
                    registered: 0,
                    scanned: 0,
                    attendance_rate: 0,
                    stations: [],
                    last_updated: '',
                    error: 'Dashboard service not available',
                });
                return;
            }
            console.debug('[Dashboard] Calling bridge.get_dashboard_data');
            bridge.get_dashboard_data((data) => {
                console.debug('[Dashboard] Data received from bridge:', data);
                updateDashboardUI(data);
            });
        });
    };

    const updateDashboardUI = (data) => {
        console.debug('[Dashboard] updateDashboardUI called with:', data);

        // Update metric cards
        if (dashboardRegistered) {
            dashboardRegistered.textContent = Number(data?.registered ?? 0).toLocaleString();
        }
        if (dashboardScanned) {
            dashboardScanned.textContent = Number(data?.scanned ?? 0).toLocaleString();
        }
        if (dashboardRate) {
            const rate = data?.attendance_rate ?? 0;
            dashboardRate.textContent = `${rate.toFixed(1)}%`;
        }
        if (dashboardUpdated) {
            dashboardUpdated.textContent = data?.last_updated || '--';
        }

        // Update station cards
        if (dashboardStationsBody) {
            const stations = data?.stations || [];
            if (stations.length === 0) {
                const errorMsg = data?.error || 'No scan data available';
                dashboardStationsBody.innerHTML = `<div class="dash__empty">${errorMsg}</div>`;
            } else {
                dashboardStationsBody.innerHTML = stations.map(station => `
                    <div class="dash__card">
                        <div class="dash__card-name">${station.name || '--'}</div>
                        <div class="dash__card-row">
                            <div class="dash__card-value">${Number(station.unique || 0).toLocaleString()}</div>
                            <div class="dash__card-sub">${station.last_scan || '--'}</div>
                        </div>
                    </div>
                `).join('');
            }
        }

        // Update BU breakdown cards (Issue #28)
        if (dashboardBuBody) {
            const businessUnits = data?.business_units || [];
            if (businessUnits.length === 0) {
                dashboardBuBody.innerHTML = `<div class="dash__empty">No BU data available</div>`;
            } else {
                dashboardBuBody.innerHTML = businessUnits.map(bu => `
                    <div class="dash__card">
                        <div class="dash__card-name">${bu.bu_name || '--'}</div>
                        <div class="dash__card-row">
                            <div class="dash__card-value">${Number(bu.scanned || 0).toLocaleString()}</div>
                            <div class="dash__card-pct">${(bu.attendance_rate || 0).toFixed(1)}%</div>
                        </div>
                    </div>
                `).join('');
            }
        }

        console.debug('[Dashboard] UI update complete');
    };

    const handleDashboardExport = () => {
        queueOrRun((bridge) => {
            if (!bridge.export_dashboard_excel) {
                if (dashboardUpdated) {
                    dashboardUpdated.textContent = 'Export service not available';
                    dashboardUpdated.style.color = 'red';
                }
                return;
            }

            // Disable button during export (icon-only button)
            if (dashboardExportBtn) {
                dashboardExportBtn.disabled = true;
                dashboardExportBtn.innerHTML = '<i class="material-icons">hourglass_empty</i>';
                dashboardExportBtn.title = 'Exporting...';
            }

            bridge.export_dashboard_excel((result) => {
                // Re-enable button (restore icon-only state)
                if (dashboardExportBtn) {
                    dashboardExportBtn.disabled = false;
                    dashboardExportBtn.innerHTML = '<i class="material-icons">download</i>';
                    dashboardExportBtn.title = 'Export';
                }

                // Show feedback in dashboard header
                if (dashboardUpdated) {
                    const originalText = dashboardUpdated.textContent;
                    const success = Boolean(result?.ok);

                    if (result?.noData) {
                        dashboardUpdated.textContent = 'No scan data to export';
                        dashboardUpdated.style.color = 'var(--deloitte-grey-medium)';
                    } else if (success) {
                        dashboardUpdated.textContent = 'Export complete';
                        dashboardUpdated.style.color = 'var(--deloitte-green)';
                    } else {
                        dashboardUpdated.textContent = result?.message || 'Export failed';
                        dashboardUpdated.style.color = 'red';
                    }

                    setTimeout(() => {
                        dashboardUpdated.textContent = originalText;
                        dashboardUpdated.style.color = '';
                    }, 2500);
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
                refreshConnectionStatus();
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

    // Dashboard overlay event listeners (Issue #27)
    if (dashboardIcon) {
        dashboardIcon.addEventListener('click', (event) => {
            event.preventDefault();
            event.stopPropagation();
            showDashboardOverlay();
        });
    }

    if (dashboardClose) {
        dashboardClose.addEventListener('click', (event) => {
            event.preventDefault();
            hideDashboardOverlay();
        });
    }

    if (dashboardRefreshBtn) {
        dashboardRefreshBtn.addEventListener('click', (event) => {
            event.preventDefault();
            // Show spinning in message area
            if (dashboardUpdated) {
                dashboardUpdated.innerHTML = '<i class="material-icons sync-spinning" style="font-size: 14px; vertical-align: middle;">sync</i> Loading...';
            }
            fetchDashboardData();
        });
    }

    if (dashboardExportBtn) {
        dashboardExportBtn.addEventListener('click', (event) => {
            event.preventDefault();
            handleDashboardExport();
        });
    }

    // Close dashboard overlay when clicking outside the dialog
    if (dashboardOverlay) {
        dashboardOverlay.addEventListener('click', (event) => {
            if (event.target === dashboardOverlay) {
                hideDashboardOverlay();
            }
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
            // First check if dashboard overlay is open
            if (dashboardOverlay && dashboardOverlay.classList.contains('dashboard-overlay--visible')) {
                hideDashboardOverlay();
                return;
            }
            queueOrRun((bridge) => bridge.close_window());
            return;
        }
        if (event.target !== barcodeInput && event.key.length === 1) {
            returnFocusToInput();
        }
    });
    window.addEventListener('focus', () => {
        returnFocusToInput();
        // Only check connection after initial delay has completed
        if (initialDelayCompleted) {
            refreshConnectionStatus();
        }
    });
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
            returnFocusToInput();
            // Only check connection after initial delay has completed
            if (initialDelayCompleted) {
                refreshConnectionStatus();
            }
        }
    });
    document.addEventListener('mouseup', returnFocusToInput);
    document.addEventListener('touchend', returnFocusToInput);
    window.addEventListener('online', () => {
        // Only check connection after initial delay has completed
        if (initialDelayCompleted) {
            refreshConnectionStatus();
        }
    });
    window.addEventListener('offline', () => setConnectionStatus('offline', 'No network connection'));

    applyDashboardState();
    returnFocusToInput();
});
