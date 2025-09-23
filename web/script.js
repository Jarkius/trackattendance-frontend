document.addEventListener('DOMContentLoaded', () => {
    // --- Mock Data --- //
    const MOCKED_EMPLOYEES = [
        { barcode: '12345', fullName: 'John Smith' },
        { barcode: '67890', fullName: 'Jane Doe' },
        { barcode: '54321', fullName: 'Peter Jones' },
        { barcode: '09876', fullName: 'Mary Williams' },
        { barcode: '11223', fullName: 'David Brown' },
        { barcode: '101117', fullName: 'Juckrit Sanitareephon' },
        { barcode: '101118', fullName: 'Pawaputanon Na Mahasarakham' },
        { barcode: '101119', fullName: 'Natthanichaphat Saosungkhongcharoen' },
        { barcode: '101120', fullName: 'Thanawatphattarakun, Naphattrarath' },
        { barcode: '101121', fullName: 'Sasithorn Srisuk' },
        { barcode: '101122', fullName: 'Kittipong Charoensuk' },
        { barcode: '101123', fullName: 'Anusorn Charoensuk' },
        { barcode: '101124', fullName: 'Nassaya Sitthichokvarodom' }
    ];
    const MOCKED_HISTORY = [];
    const TOTAL_EMPLOYEES = 1500;
    let totalScannedCount = 0;
    // --- DOM Elements --- //
    const barcodeInput = document.getElementById('barcode-input');
    const liveFeedbackName = document.getElementById('live-feedback-name');
    const totalEmployeesCounter = document.getElementById('total-employees');
    const totalScannedCounter = document.getElementById('total-scanned');
    const scanHistoryList = document.getElementById('scan-history-list');
    const closeBtn = document.getElementById('close-btn');
    const exportBtn = document.getElementById('export-data-btn');
    if (!barcodeInput || !liveFeedbackName || !totalEmployeesCounter || !totalScannedCounter) {
        console.warn('Attendance UI missing required elements; event wiring skipped.');
        return;
    }
    // --- PyQt6 WebChannel --- //
    let api;
    if (window.qt && window.qt.webChannelTransport) {
        new QWebChannel(window.qt.webChannelTransport, (channel) => {
            api = channel.objects.api;
        });
    } else {
        console.warn('Qt WebChannel transport not available; desktop integration disabled.');
    }
    // --- Helper Functions --- //
    const returnFocusToInput = () => {
        window.setTimeout(() => {
            if (document.body.contains(barcodeInput)) {
                barcodeInput.focus();
            }
        }, 100);
    };

    const adjustFeedbackSizing = (content) => {
        const message = typeof content === 'string' ? content : '';
        liveFeedbackName.classList.remove('feedback-name--compact', 'feedback-name--condensed');
        if (message.length > 32) {
            liveFeedbackName.classList.add('feedback-name--condensed');
        } else if (message.length > 22) {
            liveFeedbackName.classList.add('feedback-name--compact');
        }
    };
    function updateLiveFeedback(name) {
        adjustFeedbackSizing(name);
        liveFeedbackName.textContent = name;
        window.setTimeout(() => {
            const defaultMessage = 'Ready to scan...';
            liveFeedbackName.textContent = defaultMessage;
            adjustFeedbackSizing(defaultMessage);
            liveFeedbackName.style.color = 'var(--deloitte-green)';
        }, 2000);
    }
    function updateScanHistory(employeeName) {
        const timestamp = new Date().toLocaleTimeString();
        MOCKED_HISTORY.unshift({ name: employeeName, time: timestamp });
        if (!scanHistoryList) {
            return;
        }
        const listItem = document.createElement('li');
        listItem.className = 'collection-item';
        listItem.innerHTML = `<span class="name">${employeeName}</span><span class="timestamp">${timestamp}</span>`;
        scanHistoryList.prepend(listItem);
    }
    function updateDashboard() {
        totalScannedCount += 1;
        totalScannedCounter.textContent = totalScannedCount;
    }
    function initializeApp() {
        totalEmployeesCounter.textContent = TOTAL_EMPLOYEES.toLocaleString();
        totalScannedCounter.textContent = totalScannedCount;
        adjustFeedbackSizing(liveFeedbackName.textContent);
        returnFocusToInput();
    }
    function handleExportSuccess(originalText, originalColor) {
        const successMessage = 'Data exported successfully!';
        liveFeedbackName.textContent = successMessage;
        liveFeedbackName.style.color = 'var(--deloitte-green)';
        adjustFeedbackSizing(successMessage);
        window.setTimeout(() => {
            const fallbackMessage = originalText || 'Ready to scan...';
            liveFeedbackName.textContent = fallbackMessage;
            adjustFeedbackSizing(fallbackMessage);
            liveFeedbackName.style.color = originalColor || 'var(--deloitte-green)';
        }, 3000);
    }
    // --- Event Listeners --- //
    barcodeInput.addEventListener('keyup', (event) => {
        if (event.key === 'Enter') {
            const barcode = barcodeInput.value.trim();
            if (!barcode) {
                return;
            }
            const employee = MOCKED_EMPLOYEES.find((emp) => emp.barcode === barcode);
            if (employee) {
                updateLiveFeedback(employee.fullName);
                liveFeedbackName.style.color = 'var(--deloitte-black)';
                updateScanHistory(employee.fullName);
                updateDashboard();
            } else {
                updateLiveFeedback('Not Found !');
                liveFeedbackName.style.color = 'red';
            }
            barcodeInput.value = '';
            returnFocusToInput();
        }
    });
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            if (api) {
                api.close_window();
            }
        });
    }
    if (exportBtn) {
        exportBtn.addEventListener('click', (event) => {
            event.preventDefault();
            exportBtn.disabled = true;
            exportBtn.innerHTML = '<i class="material-icons">hourglass_empty</i>Exporting...';
            window.setTimeout(() => {
                exportBtn.disabled = false;
                exportBtn.innerHTML = '<i class="material-icons">file_download</i>Export Data';
                handleExportSuccess(liveFeedbackName.textContent, liveFeedbackName.style.color);
                returnFocusToInput();
            }, 1500);
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
            if (api) {
                api.close_window();
            }
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
    // --- Start the app --- //
    initializeApp();
});
