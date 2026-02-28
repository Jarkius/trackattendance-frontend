/**
 * TrackAttendance Dashboard
 *
 * Uses Server-Sent Events (SSE) for real-time updates.
 * Falls back to polling if SSE is unavailable.
 */

class Dashboard {
    constructor(config) {
        this.apiUrl = config.API_URL;
        this.apiKey = config.API_KEY || '';
        this.pollInterval = config.POLL_INTERVAL || 15000;
        this.showToast = config.SHOW_TOAST !== false;

        this.eventSource = null;
        this.pollTimer = null;
        this.lastStats = null;
        this.reconnectDelay = 1000;
        this.maxReconnectDelay = 30000;
    }

    /**
     * Initialize the dashboard connection
     */
    init() {
        this.setupOfflineDetection();
        this.connect();
    }

    /**
     * Connect via SSE for real-time updates
     */
    connect() {
        // Check if SSE is supported
        if (typeof EventSource === 'undefined') {
            console.log('SSE not supported, using polling');
            this.startPolling();
            return;
        }

        try {
            this.setStatus('connecting');
            const sseUrl = `${this.apiUrl}/v1/dashboard/events`;
            console.log('Connecting to SSE:', sseUrl);
            this.eventSource = new EventSource(sseUrl);

            // Initial data event
            this.eventSource.addEventListener('init', (e) => {
                const data = JSON.parse(e.data);
                this.updateUI(data);
                this.setStatus('connected');
                this.reconnectDelay = 1000;
            });

            // Update event (new scans)
            this.eventSource.addEventListener('update', (e) => {
                const data = JSON.parse(e.data);
                this.updateUI(data);
                this.flashUpdate();

                if (this.showToast) {
                    this.showUpdateToast('New scan received!');
                }
            });

            // Connection opened
            this.eventSource.onopen = () => {
                console.log('SSE connected');
                this.setStatus('connected');
                this.reconnectDelay = 1000;
            };

            // Handle messages without event type
            this.eventSource.onmessage = (e) => {
                try {
                    const data = JSON.parse(e.data);
                    this.updateUI(data);
                    this.setStatus('connected');
                } catch (err) {
                    console.error('Failed to parse SSE message:', err);
                }
            };

            // Error handling with reconnect
            this.eventSource.onerror = (e) => {
                console.error('SSE error, reconnecting...', e);
                this.eventSource.close();
                this.setStatus('reconnecting');

                // Exponential backoff
                setTimeout(() => this.connect(), this.reconnectDelay);
                this.reconnectDelay = Math.min(
                    this.reconnectDelay * 2,
                    this.maxReconnectDelay
                );
            };

        } catch (e) {
            console.error('SSE connection failed:', e);
            this.startPolling();
        }
    }

    /**
     * Start polling for dashboard stats
     */
    startPolling() {
        console.log(`Polling every ${this.pollInterval / 1000}s`);

        const poll = async () => {
            try {
                this.setStatus('connecting');

                const headers = {};
                if (this.apiKey) {
                    headers['Authorization'] = `Bearer ${this.apiKey}`;
                }

                const res = await fetch(`${this.apiUrl}/v1/dashboard/stats`, { headers });

                if (res.ok) {
                    const data = await res.json();
                    const hadChanges = this.hasChanges(data);
                    this.updateUI(data);
                    this.setStatus('connected');

                    if (hadChanges && this.showToast) {
                        this.showUpdateToast('Data updated');
                    }
                } else {
                    console.error('API error:', res.status);
                    this.setStatus('error');
                }
            } catch (e) {
                console.error('Polling error:', e);
                this.setStatus('error');
            }
        };

        // Initial fetch
        poll();

        // Start interval
        this.pollTimer = setInterval(poll, this.pollInterval);
    }

    /**
     * Check if stats have changed
     */
    hasChanges(newData) {
        if (!this.lastStats) return false;
        return newData.total_scans !== this.lastStats.total_scans ||
               newData.unique_badges !== this.lastStats.unique_badges;
    }

    /**
     * Update all UI elements with new data
     */
    updateUI(data) {
        // Store for comparison
        const prevStats = this.lastStats;
        this.lastStats = data;

        // Main stats
        this.animateNumber('total-scanned', data.unique_badges || 0);
        this.animateNumber('total-scans', data.total_scans || 0);

        const rate = data.attendance_rate || 0;
        document.getElementById('attendance-rate').textContent = rate + '%';

        // Progress bar
        const progressBar = document.getElementById('attendance-progress');
        if (progressBar) {
            progressBar.style.width = Math.min(rate, 100) + '%';
        }

        // Registered count
        const regEl = document.getElementById('registered-count');
        if (regEl && data.registered !== undefined) {
            regEl.textContent = data.registered.toLocaleString();
        }

        // Last updated
        document.getElementById('last-updated').textContent =
            new Date().toLocaleTimeString();

        // Stations
        this.updateStations(data.stations || []);

        // Business Units
        if (data.business_units) {
            this.updateBusinessUnits(data.business_units);
        }
    }

    /**
     * Animate number changes
     */
    animateNumber(elementId, newValue) {
        const el = document.getElementById(elementId);
        if (!el) return;

        const currentValue = parseInt(el.textContent.replace(/,/g, '')) || 0;

        if (currentValue === newValue) {
            el.textContent = newValue.toLocaleString();
            return;
        }

        // Quick animation
        const duration = 300;
        const steps = 10;
        const increment = (newValue - currentValue) / steps;
        let current = currentValue;
        let step = 0;

        const animate = () => {
            step++;
            current += increment;

            if (step >= steps) {
                el.textContent = newValue.toLocaleString();
            } else {
                el.textContent = Math.round(current).toLocaleString();
                setTimeout(animate, duration / steps);
            }
        };

        animate();
    }

    /**
     * Update stations list
     */
    updateStations(stations) {
        const container = document.getElementById('stations-list');
        if (!container) return;

        if (stations.length === 0) {
            container.innerHTML = `
                <div class="col s12 no-data">
                    <i class="material-icons">router</i>
                    <p>No stations connected yet</p>
                </div>
            `;
            return;
        }

        container.innerHTML = stations.map(s => `
            <div class="col s12 m6 l4">
                <div class="card-panel station-card">
                    <div class="station-info">
                        <div class="station-name">${this.escapeHtml(s.name)}</div>
                        <div class="station-time">
                            <i class="material-icons tiny">access_time</i>
                            ${this.formatTime(s.last_scan)}
                        </div>
                    </div>
                    <div class="station-stats">
                        <div class="station-count">${s.unique || 0}</div>
                        <div class="station-count-label">unique</div>
                    </div>
                </div>
            </div>
        `).join('');
    }

    /**
     * Update business units list
     */
    updateBusinessUnits(units) {
        const container = document.getElementById('bu-list');
        if (!container) return;

        if (units.length === 0) {
            container.innerHTML = `
                <div class="col s12 no-data">
                    <i class="material-icons">business</i>
                    <p>No data available</p>
                </div>
            `;
            return;
        }

        // Sort by attendance rate descending
        const sorted = [...units].sort((a, b) =>
            (b.attendance_rate || 0) - (a.attendance_rate || 0)
        );

        container.innerHTML = sorted.map(bu => {
            const rate = bu.attendance_rate || 0;
            const rateClass = rate >= 80 ? 'rate-high' :
                              rate >= 50 ? 'rate-medium' : 'rate-low';

            return `
                <div class="col s12 m6">
                    <div class="card-panel bu-card">
                        <div class="bu-name">${this.escapeHtml(bu.bu_name)}</div>
                        <div class="bu-stats">
                            <div class="bu-rate ${rateClass}">${rate}%</div>
                            <div class="bu-count">${bu.scanned || 0} / ${bu.registered || 0}</div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    /**
     * Flash the page on update
     */
    flashUpdate() {
        document.body.classList.add('flash');
        setTimeout(() => document.body.classList.remove('flash'), 300);
    }

    /**
     * Show update toast notification
     */
    showUpdateToast(message) {
        const toast = document.getElementById('update-toast');
        const msgEl = document.getElementById('update-message');

        if (toast && msgEl) {
            msgEl.textContent = message;
            toast.classList.remove('hide');

            setTimeout(() => {
                toast.classList.add('hide');
            }, 3000);
        }
    }

    /**
     * Set connection status indicator
     */
    setStatus(status) {
        const el = document.getElementById('connection-status');
        if (!el) return;

        el.className = `right status-${status}`;

        const icons = {
            connected: 'cloud_done',
            connecting: 'sync',
            reconnecting: 'sync_problem',
            error: 'cloud_off'
        };

        const labels = {
            connected: 'Live',
            connecting: 'Connecting...',
            reconnecting: 'Reconnecting...',
            error: 'Offline'
        };

        el.innerHTML = `
            <i class="material-icons tiny">${icons[status] || 'cloud'}</i>
            ${labels[status] || status}
        `;
    }

    /**
     * Format ISO timestamp to local time
     */
    formatTime(isoString) {
        if (!isoString) return '--';

        try {
            const date = new Date(isoString);
            return date.toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch (e) {
            return '--';
        }
    }

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Setup offline/online detection
     */
    setupOfflineDetection() {
        const offlineIndicator = document.getElementById('offline-indicator');

        window.addEventListener('online', () => {
            if (offlineIndicator) offlineIndicator.classList.add('hide');
            this.connect();
        });

        window.addEventListener('offline', () => {
            if (offlineIndicator) offlineIndicator.classList.remove('hide');
            this.setStatus('error');
        });

        // Initial check
        if (!navigator.onLine && offlineIndicator) {
            offlineIndicator.classList.remove('hide');
        }
    }

    /**
     * Clean up resources
     */
    destroy() {
        if (this.eventSource) {
            this.eventSource.close();
        }
        if (this.pollTimer) {
            clearInterval(this.pollTimer);
        }
    }
}

// Initialize dashboard when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const dashboard = new Dashboard(window.CONFIG);
    dashboard.init();

    // Expose for debugging
    window.dashboard = dashboard;
});

// Register service worker for PWA
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('sw.js').catch(() => {
        // Service worker registration failed, continue without it
    });
}
