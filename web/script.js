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

    // Debounce utility
    const debounce = (fn, delayMs) => {
        let timeoutId = null;
        return (...args) => {
            if (timeoutId !== null) window.clearTimeout(timeoutId);
            timeoutId = window.setTimeout(() => { timeoutId = null; fn(...args); }, delayMs);
        };
    };

    // Dashboard data cache (10 second TTL)
    let dashboardDataCache = null;
    let dashboardDataCacheTime = 0;
    const DASHBOARD_CACHE_TTL_MS = 10000;

    // Duplicate badge alert configuration
    let duplicateBadgeAlertDurationMs = 3000;  // Default: 3 seconds
    let scanFeedbackDurationMs = 2000;  // Default: 2 seconds

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

    // Voice toggle element
    const voiceToggle = document.getElementById('voice-toggle');

    // Lookup overlay elements
    const lookupOverlay = document.getElementById('lookup-overlay');
    const lookupSearchQuery = document.getElementById('lookup-search-query');
    const lookupResults = document.getElementById('lookup-results');
    const lookupCancel = document.getElementById('lookup-cancel');

    // Camera toggle element
    const cameraToggle = document.getElementById('camera-toggle');

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
    const dashboardFooter = document.getElementById('dashboard-footer');
    const dashboardExportLink = document.getElementById('dashboard-export-link');

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

    const escapeHtml = (str) => {
        if (typeof str !== 'string') return str;
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    };

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
        if (!welcomeHeading) return;

        // Change text to "THANK YOU" and apply green color animation
        welcomeHeading.textContent = 'THANK YOU';
        welcomeHeading.style.color = '#86bc25';
        welcomeHeading.style.transform = 'scale(1)';
        welcomeHeading.style.textShadow = '0 0 0 rgba(134, 188, 37, 0)';

        // Force reflow then animate
        void welcomeHeading.offsetWidth;

        // Phase 1: Quick overshoot (bounce up)
        welcomeHeading.style.transition = 'all 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.5)';
        welcomeHeading.style.transform = 'scale(1.2)';
        welcomeHeading.style.textShadow = '0 0 35px rgba(134, 188, 37, 0.8)';

        // Phase 2: Bounce back down
        setTimeout(() => {
            if (welcomeHeading) {
                welcomeHeading.style.transition = 'all 0.15s ease-out';
                welcomeHeading.style.transform = 'scale(0.95)';
                welcomeHeading.style.textShadow = '0 0 20px rgba(134, 188, 37, 0.5)';
            }
        }, 200);

        // Phase 3: Settle to final state
        setTimeout(() => {
            if (welcomeHeading) {
                welcomeHeading.style.transition = 'all 0.2s ease-out';
                welcomeHeading.style.transform = 'scale(1.08)';
                welcomeHeading.style.textShadow = '0 0 25px rgba(134, 188, 37, 0.6)';
            }
        }, 350);
    };

    const resetWelcomeStyle = () => {
        if (!welcomeHeading) return;
        // Reset to original "WELCOME" text and grey color
        welcomeHeading.textContent = 'WELCOME';
        welcomeHeading.style.transition = 'all 0.3s ease-out';
        welcomeHeading.style.color = '#8c8c8c';
        welcomeHeading.style.transform = 'scale(1)';
        welcomeHeading.style.textShadow = 'none';
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
            let initialDataReceived = false;
            const initialDataTimeout = window.setTimeout(() => {
                if (initialDataReceived) return;
                console.warn('[QWebChannel] Initial data timeout after 10s, using defaults');
                initialDataReceived = true;
                applyDashboardState();
                window.setTimeout(() => {
                    initialDelayCompleted = true;
                    refreshConnectionStatus();
                    startConnectionStatusPolling();
                }, connectionCheckInitialDelayMs);
                returnFocusToInput();
            }, 10000);
            bridge.get_initial_data((payload) => {
                if (initialDataReceived) return;
                initialDataReceived = true;
                window.clearTimeout(initialDataTimeout);
                applyConnectionIntervalFromPayload(payload);
                applyConnectionInitialDelayFromPayload(payload);
                debugMode = Boolean(payload?.debugMode);
                if (debugMode) {
                    console.info('[DEBUG] Debug mode enabled - auto-focus disabled');
                }
                duplicateBadgeAlertDurationMs = Math.max(0, Number(payload?.duplicateBadgeAlertDurationMs) || 3000);
                console.info('[Config] Duplicate badge alert duration:', duplicateBadgeAlertDurationMs, 'ms');
                scanFeedbackDurationMs = Math.max(0, Number(payload?.scanFeedbackDurationMs) || 2000);
                console.info('[Config] Scan feedback duration:', scanFeedbackDurationMs, 'ms');
                // Signal binding already done in QWebChannel setup, don't rebind here
                state.totalEmployees = payload?.totalEmployees ?? 0;
                state.totalScansToday = payload?.totalScansToday ?? 0;
                state.totalScansOverall = payload?.totalScansOverall ?? 0;
                state.stationName = payload?.stationName ?? '--';
                state.history = Array.isArray(payload?.scanHistory) ? payload.scanHistory : [];
                applyDashboardState();
                updateSyncStatus();  // Load sync status on startup
                initCameraToggle();  // Set camera toggle initial state
                initVoiceToggle();  // Set voice toggle initial state
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

    // ── Camera toggle ──────────────────────────────────────────────────

    let cameraToggling = false;

    const setCameraToggleState = (running) => {
        if (!cameraToggle) return;
        cameraToggle.classList.remove('camera-toggle--hidden', 'camera-toggle--on', 'camera-toggle--off');
        cameraToggle.classList.add(running ? 'camera-toggle--on' : 'camera-toggle--off');
        cameraToggle.setAttribute('title', running ? 'Camera Detection: ON' : 'Camera Detection: OFF');
    };

    const initCameraToggle = () => {
        queueOrRun((bridge) => {
            if (!bridge.get_camera_status) return;
            bridge.get_camera_status((status) => {
                if (!status?.enabled) return;  // keep hidden if not configured
                setCameraToggleState(status.running);
            });
        });
    };

    const handleCameraToggle = () => {
        if (cameraToggling) return;  // Prevent rapid clicks
        cameraToggling = true;
        queueOrRun((bridge) => {
            if (!bridge.toggle_camera) { cameraToggling = false; return; }
            bridge.toggle_camera((result) => {
                cameraToggling = false;
                if (result?.ok) {
                    setCameraToggleState(result.running);
                }
                returnFocusToInput();
            });
        });
    };

    // ── Voice toggle ──────────────────────────────────────────────────

    let voiceToggling = false;

    const setVoiceToggleState = (enabled) => {
        if (!voiceToggle) return;
        voiceToggle.classList.remove('voice-toggle--hidden', 'voice-toggle--on', 'voice-toggle--off');
        voiceToggle.classList.add(enabled ? 'voice-toggle--on' : 'voice-toggle--off');
        voiceToggle.setAttribute('title', enabled ? 'Voice: ON' : 'Voice: OFF');
    };

    const initVoiceToggle = () => {
        queueOrRun((bridge) => {
            if (!bridge.get_voice_status) return;
            bridge.get_voice_status((status) => {
                // Always show voice toggle (voice player exists if status returned)
                setVoiceToggleState(status?.enabled ?? false);
            });
        });
    };

    const handleVoiceToggle = () => {
        if (voiceToggling) return;
        voiceToggling = true;
        queueOrRun((bridge) => {
            if (!bridge.toggle_voice) { voiceToggling = false; return; }
            bridge.toggle_voice((result) => {
                voiceToggling = false;
                if (result?.ok) {
                    setVoiceToggleState(result.enabled);
                }
                returnFocusToInput();
            });
        });
    };

    // ── Employee Lookup ───────────────────────────────────────────────

    const showLookupOverlay = (query, results) => {
        if (!lookupOverlay) return;
        if (lookupSearchQuery) lookupSearchQuery.textContent = `Search: "${query}"`;

        if (lookupResults) {
            lookupResults.innerHTML = '';
            if (results.length === 0) {
                lookupResults.innerHTML = '<div class="lookup-overlay__empty">No employees found</div>';
            } else {
                results.forEach((emp) => {
                    const card = document.createElement('div');
                    card.className = 'lookup-overlay__result';
                    card.innerHTML = `
                        <div class="lookup-overlay__result-info">
                            <div class="lookup-overlay__result-name">${escapeHtml(emp.full_name)} (${escapeHtml(emp.legacy_id)})</div>
                            <div class="lookup-overlay__result-meta">${escapeHtml(emp.business_unit)}${emp.email ? ' · ' + escapeHtml(emp.email) : ''}</div>
                        </div>
                        <button class="lookup-overlay__result-btn" data-legacy-id="${escapeHtml(emp.legacy_id)}">Record Scan</button>
                    `;
                    const btn = card.querySelector('.lookup-overlay__result-btn');
                    btn.addEventListener('click', (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        handleManualScan(emp.legacy_id);
                    });
                    lookupResults.appendChild(card);
                });
            }
        }

        lookupOverlay.classList.add('lookup-overlay--visible');
        lookupOverlay.setAttribute('aria-hidden', 'false');

        // Focus Record Scan button only when exactly one result (Enter to confirm)
        if (results.length === 1) {
            const firstBtn = lookupResults?.querySelector('.lookup-overlay__result-btn');
            if (firstBtn) firstBtn.focus();
        }
    };

    const hideLookupOverlay = () => {
        if (!lookupOverlay) return;
        lookupOverlay.classList.remove('lookup-overlay--visible');
        lookupOverlay.setAttribute('aria-hidden', 'true');
        returnFocusToInput();
    };

    const handleManualScan = (legacyId) => {
        hideLookupOverlay();
        queueOrRun((bridge) => {
            if (!bridge.submit_manual_scan) return;
            bridge.submit_manual_scan(legacyId, (response) => {
                handleScanResponse(response);
                barcodeInput.value = '';
                returnFocusToInput();
            });
        });
    };

    // ── Scan handling ────────────────────────────────────────────────────

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
        setLiveFeedback(message, found ? 'var(--deloitte-black)' : 'red', scanFeedbackDurationMs);

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
        // Check if input looks like an email username (contains letters, not a pure number)
        const looksLikeBadge = /^\d+$/.test(badge);

        if (looksLikeBadge) {
            // Normal badge scan flow
            queueOrRun((bridge) => {
                bridge.submit_scan(badge, (response) => {
                    handleScanResponse(response);
                    barcodeInput.value = '';
                    returnFocusToInput();
                });
            });
        } else {
            // Non-numeric input → search employees first (don't record yet)
            queueOrRun((bridge) => {
                if (!bridge.search_employee) {
                    // Fallback: no search support, just do normal scan
                    bridge.submit_scan(badge, (response) => {
                        handleScanResponse(response);
                        barcodeInput.value = '';
                        returnFocusToInput();
                    });
                    return;
                }
                bridge.search_employee(badge, (searchResult) => {
                    barcodeInput.value = '';
                    if (searchResult?.ok && searchResult.results && searchResult.results.length > 0) {
                        showLookupOverlay(badge, searchResult.results);
                    } else {
                        // No lookup results — record as unmatched badge scan
                        bridge.submit_scan(badge, (response) => {
                            handleScanResponse(response);
                            returnFocusToInput();
                        });
                    }
                });
            });
        }
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

    const _updateSyncStatusImmediate = () => {
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
    const updateSyncStatus = debounce(_updateSyncStatusImmediate, 200);

    // Dashboard overlay functions (Issue #27)
    const showDashboardOverlay = () => {
        if (!dashboardOverlay) return;

        // Set flag to skip connection checks while dashboard is open
        dashboardOpen = true;
        console.debug('[Dashboard] Dashboard opened - connection checks paused');

        // Release focus from barcode input so dashboard can scroll freely
        if (barcodeInput) barcodeInput.blur();

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

        // Check admin availability and fetch data
        checkAdminEnabled();
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

        // Hide export footer
        if (dashboardFooter) {
            dashboardFooter.style.display = 'none';
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

    const fetchDashboardData = (forceRefresh = false) => {
        const now = Date.now();
        if (!forceRefresh && dashboardDataCache && (now - dashboardDataCacheTime) < DASHBOARD_CACHE_TTL_MS) {
            console.debug('[Dashboard] Using cached data (age: ' + (now - dashboardDataCacheTime) + 'ms)');
            updateDashboardUI(dashboardDataCache);
            return;
        }

        console.debug('[Dashboard] Fetch data started (cache miss or forced)');
        queueOrRun((bridge) => {
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
            bridge.get_dashboard_data((data) => {
                dashboardDataCache = data;
                dashboardDataCacheTime = Date.now();
                console.debug('[Dashboard] Data received and cached');
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
                dashboardStationsBody.innerHTML = `<div class="dash__empty">${escapeHtml(errorMsg)}</div>`;
            } else {
                dashboardStationsBody.innerHTML = stations.map(station => `
                    <div class="dash__card">
                        <div class="dash__card-name">${escapeHtml(station.name || '--')}</div>
                        <div class="dash__card-row">
                            <div class="dash__card-value">${Number(station.unique || 0).toLocaleString()}</div>
                            <div class="dash__card-sub">${escapeHtml(station.last_scan || '--')}</div>
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
                        <div class="dash__card-name">${escapeHtml(bu.bu_name || '--')}</div>
                        <div class="dash__card-row">
                            <div class="dash__card-value">${Number(bu.scanned || 0).toLocaleString()} <span class="dash__card-total">/ ${Number(bu.registered || 0).toLocaleString()}</span></div>
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

                        // Show footer with file path
                        if (dashboardFooter && dashboardExportLink) {
                            dashboardExportLink.textContent = result.file_path || result.fileName || 'Exported file';
                            dashboardExportLink.setAttribute('data-path', result.file_path || '');
                            dashboardFooter.style.display = '';
                        }
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

    // Export link click - open folder in Explorer
    if (dashboardExportLink) {
        dashboardExportLink.addEventListener('click', (e) => {
            e.preventDefault();
            const filePath = dashboardExportLink.getAttribute('data-path');
            if (filePath) {
                queueOrRun((bridge) => {
                    if (bridge.open_export_folder) {
                        bridge.open_export_folder(filePath);
                    }
                });
            }
        });
    }

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

    // Voice toggle
    if (voiceToggle) {
        voiceToggle.addEventListener('click', (event) => {
            event.preventDefault();
            event.stopPropagation();
            handleVoiceToggle();
        });
    }

    // Camera toggle
    if (cameraToggle) {
        cameraToggle.addEventListener('click', (event) => {
            event.preventDefault();
            event.stopPropagation();
            handleCameraToggle();
        });
    }

    // Employee lookup cancel
    if (lookupCancel) {
        lookupCancel.addEventListener('click', (event) => {
            event.preventDefault();
            hideLookupOverlay();
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
            fetchDashboardData(true);  // Force refresh, bypass cache
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

    // ---- Admin Panel Logic ----
    const adminBtn = document.getElementById('dashboard-admin');
    const adminOverlay = document.getElementById('admin-overlay');
    const adminPinInput = document.getElementById('admin-pin-input');
    const adminPinError = document.getElementById('admin-pin-error');
    const adminCloudCount = document.getElementById('admin-cloud-count');
    const adminLocalCount = document.getElementById('admin-local-count');
    const adminConfirmTitle = document.getElementById('admin-confirm-title');
    const adminConfirmMessage = document.getElementById('admin-confirm-message');
    const adminConfirmCode = document.getElementById('admin-confirm-code');
    const adminConfirmCodeInput = document.getElementById('admin-confirm-code-input');
    const adminResultTitle = document.getElementById('admin-result-title');
    const adminResultMessage = document.getElementById('admin-result-message');

    let adminVerifiedPin = '';
    let adminClearMode = ''; // 'station' or 'all'
    let adminCurrentCode = '';
    let adminStatusPollId = null;

    const checkAdminEnabled = () => {
        queueOrRun((bridge) => {
            if (!bridge.is_admin_enabled) return;
            bridge.is_admin_enabled((result) => {
                if (adminBtn) adminBtn.style.display = result?.enabled ? '' : 'none';
            });
        });
    };

    const ADMIN_VIEWS = ['admin-pin-view', 'admin-actions-view', 'admin-confirm-view', 'admin-result-view', 'admin-status-view'];
    const showAdminView = (viewId) => {
        ADMIN_VIEWS.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.style.display = id === viewId ? '' : 'none';
        });
    };

    const showAdminOverlay = () => {
        if (!adminOverlay) return;
        adminVerifiedPin = '';
        adminClearMode = '';
        showAdminView('admin-pin-view');
        if (adminPinInput) { adminPinInput.value = ''; }
        if (adminPinError) { adminPinError.textContent = ''; }
        adminOverlay.classList.add('admin-overlay--visible');
        adminOverlay.setAttribute('aria-hidden', 'false');
        setTimeout(() => { if (adminPinInput) adminPinInput.focus(); }, 100);
    };

    const hideAdminOverlay = () => {
        if (!adminOverlay) return;
        adminOverlay.classList.remove('admin-overlay--visible');
        adminOverlay.setAttribute('aria-hidden', 'true');
        adminVerifiedPin = '';
        if (adminStatusPollId) { clearInterval(adminStatusPollId); adminStatusPollId = null; }
    };

    const handlePinSubmit = () => {
        const pin = adminPinInput ? adminPinInput.value.trim() : '';
        if (!pin) { if (adminPinError) adminPinError.textContent = 'Please enter a PIN'; return; }
        queueOrRun((bridge) => {
            bridge.verify_admin_pin(pin, (result) => {
                if (result?.ok) {
                    adminVerifiedPin = pin;
                    showAdminView('admin-actions-view');
                    if (adminCloudCount) adminCloudCount.textContent = 'Checking scan count...';
                    bridge.admin_get_cloud_scan_count((countResult) => {
                        if (adminCloudCount) {
                            adminCloudCount.textContent = countResult?.ok
                                ? `Cloud: ${Number(countResult.count).toLocaleString()} scan(s)`
                                : (countResult?.message || 'Could not check count');
                        }
                    });
                    bridge.admin_get_local_scan_count((localResult) => {
                        if (adminLocalCount) {
                            adminLocalCount.textContent = `This station: ${Number(localResult?.count || 0).toLocaleString()} local scan(s)`;
                        }
                    });
                } else {
                    if (adminPinError) adminPinError.textContent = result?.message || 'Incorrect PIN';
                    if (adminPinInput) { adminPinInput.value = ''; adminPinInput.focus(); }
                }
            });
        });
    };

    const showConfirmView = (mode) => {
        adminClearMode = mode;
        adminCurrentCode = String(Math.floor(1000 + Math.random() * 9000));
        if (adminConfirmCode) adminConfirmCode.textContent = adminCurrentCode;
        if (adminConfirmCodeInput) { adminConfirmCodeInput.value = ''; }
        const deleteBtn = document.getElementById('admin-confirm-delete');
        if (deleteBtn) { deleteBtn.disabled = true; deleteBtn.textContent = 'Delete'; }
        if (adminConfirmTitle) {
            adminConfirmTitle.textContent = mode === 'all' ? 'Clear All Stations' : 'Clear This Station';
        }
        if (adminConfirmMessage) {
            adminConfirmMessage.textContent = mode === 'all'
                ? 'This will delete ALL scans + roster from cloud and all stations. A backup will be exported first.'
                : 'This will delete scans from this station only (local + cloud). A backup will be exported first.';
        }
        showAdminView('admin-confirm-view');
        setTimeout(() => { if (adminConfirmCodeInput) adminConfirmCodeInput.focus(); }, 100);
    };

    // Validate confirmation code input
    if (adminConfirmCodeInput) {
        adminConfirmCodeInput.addEventListener('input', () => {
            const deleteBtn = document.getElementById('admin-confirm-delete');
            if (deleteBtn) {
                deleteBtn.disabled = adminConfirmCodeInput.value.trim() !== adminCurrentCode;
            }
        });
    }

    const handleConfirmDelete = () => {
        if (!adminVerifiedPin) { hideAdminOverlay(); return; }
        if (adminConfirmCodeInput && adminConfirmCodeInput.value.trim() !== adminCurrentCode) return;

        const btn = document.getElementById('admin-confirm-delete');
        if (btn) { btn.disabled = true; btn.textContent = 'Deleting...'; }

        const bridgeMethod = adminClearMode === 'all' ? 'admin_clear_cloud_data' : 'admin_clear_station_data';

        queueOrRun((bridge) => {
            bridge[bridgeMethod](adminVerifiedPin, (result) => {
                if (btn) { btn.disabled = false; btn.textContent = 'Delete'; }
                if (result?.ok) {
                    if (adminClearMode === 'all') {
                        // Show live station status view
                        showAdminView('admin-status-view');
                        pollStationStatus();
                        adminStatusPollId = setInterval(pollStationStatus, 5000);
                    } else {
                        // Station-only clear: show result and close
                        showAdminView('admin-result-view');
                        if (adminResultTitle) { adminResultTitle.textContent = 'Station Cleared'; adminResultTitle.style.color = '#86bc25'; }
                        const backupMsg = result.backup_path ? `\nBackup: ${result.backup_path}` : '';
                        if (adminResultMessage) adminResultMessage.textContent = result.message + backupMsg + '\nClosing app in 3 seconds...';
                        dashboardDataCache = null;
                        updateSyncStatus();
                        window.setTimeout(() => { queueOrRun((b) => b.close_window()); }, 3000);
                    }
                } else {
                    showAdminView('admin-result-view');
                    if (adminResultTitle) { adminResultTitle.textContent = 'Error'; adminResultTitle.style.color = '#c62828'; }
                    if (adminResultMessage) adminResultMessage.textContent = result?.message || 'Failed to clear data';
                }
            });
        });
    };

    const pollStationStatus = () => {
        queueOrRun((bridge) => {
            if (!bridge.admin_get_station_status) return;
            bridge.admin_get_station_status((result) => {
                const listEl = document.getElementById('admin-station-list');
                const summaryEl = document.getElementById('admin-station-summary');
                if (!listEl || !result?.stations) return;

                listEl.innerHTML = result.stations.map(s => {
                    const dotClass = 'admin-station-item__dot--' + s.status;
                    const label = s.status === 'ready' ? 'Ready' : s.status === 'pending' ? 'Pending' : 'Offline';
                    const ago = s.seconds_ago < 60 ? `${s.seconds_ago}s ago` : `${Math.floor(s.seconds_ago / 60)}m ago`;
                    const scans = s.status === 'offline' ? '--' : s.local_scan_count;
                    return `<div class="admin-station-item">
                        <span class="admin-station-item__name">${s.station_name}</span>
                        <span class="admin-station-item__status">
                            <span class="admin-station-item__dot ${dotClass}"></span>
                            ${label} &middot; ${scans} scans &middot; ${ago}
                        </span>
                    </div>`;
                }).join('');

                if (summaryEl) {
                    summaryEl.textContent = `${result.ready_count}/${result.total_count} stations cleared`;
                    if (result.ready_count === result.total_count && result.total_count > 0) {
                        summaryEl.style.color = '#4caf50';
                        summaryEl.textContent += ' — All ready!';
                    } else {
                        summaryEl.style.color = '#999';
                    }
                }
            });
        });
    };

    if (adminBtn) adminBtn.addEventListener('click', (e) => { e.preventDefault(); showAdminOverlay(); });
    const adminPinSubmitBtn = document.getElementById('admin-pin-submit');
    if (adminPinSubmitBtn) adminPinSubmitBtn.addEventListener('click', (e) => { e.preventDefault(); handlePinSubmit(); });
    if (adminPinInput) adminPinInput.addEventListener('keyup', (e) => { if (e.key === 'Enter') handlePinSubmit(); });
    const adminCancelBtn = document.getElementById('admin-cancel');
    if (adminCancelBtn) adminCancelBtn.addEventListener('click', (e) => { e.preventDefault(); hideAdminOverlay(); });
    const adminCloseBtn = document.getElementById('admin-close');
    if (adminCloseBtn) adminCloseBtn.addEventListener('click', (e) => { e.preventDefault(); hideAdminOverlay(); });
    const adminClearStationBtn = document.getElementById('admin-clear-station');
    if (adminClearStationBtn) adminClearStationBtn.addEventListener('click', (e) => { e.preventDefault(); showConfirmView('station'); });
    const adminClearCloudBtn = document.getElementById('admin-clear-cloud');
    if (adminClearCloudBtn) adminClearCloudBtn.addEventListener('click', (e) => { e.preventDefault(); showConfirmView('all'); });
    const adminConfirmCancelBtn = document.getElementById('admin-confirm-cancel');
    if (adminConfirmCancelBtn) adminConfirmCancelBtn.addEventListener('click', (e) => { e.preventDefault(); showAdminView('admin-actions-view'); });
    const adminConfirmDeleteBtn = document.getElementById('admin-confirm-delete');
    if (adminConfirmDeleteBtn) adminConfirmDeleteBtn.addEventListener('click', (e) => { e.preventDefault(); handleConfirmDelete(); });
    const adminResultCloseBtn = document.getElementById('admin-result-close');
    if (adminResultCloseBtn) adminResultCloseBtn.addEventListener('click', (e) => { e.preventDefault(); hideAdminOverlay(); });
    const adminStatusCloseBtn = document.getElementById('admin-status-close');
    if (adminStatusCloseBtn) adminStatusCloseBtn.addEventListener('click', (e) => { e.preventDefault(); hideAdminOverlay(); });
    if (adminOverlay) adminOverlay.addEventListener('click', (e) => { if (e.target === adminOverlay) hideAdminOverlay(); });

    document.addEventListener('click', (event) => {
        if (event.target !== barcodeInput) {
            returnFocusToInput();
        }
    });

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
    const debouncedRefreshConnection = debounce(() => {
        if (initialDelayCompleted) refreshConnectionStatus();
    }, 5000);

    window.addEventListener('focus', () => {
        returnFocusToInput();
        debouncedRefreshConnection();
    });
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
            returnFocusToInput();
            debouncedRefreshConnection();
        }
    });
    window.addEventListener('online', () => {
        debouncedRefreshConnection();
    });
    window.addEventListener('offline', () => setConnectionStatus('offline', 'No network connection'));

    applyDashboardState();
    returnFocusToInput();
});
