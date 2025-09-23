
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
        { barcode: '101124', fullName: 'Sasithorn Srisuk' },
    ];

    const MOCKED_HISTORY = [];
    const TOTAL_EMPLOYEES = 1500;
    let TOTAL_SCANNED_COUNT = 0;

    // --- DOM Elements --- //
    const barcodeInput = document.getElementById('barcode-input');
    const liveFeedbackName = document.getElementById('live-feedback-name');
    const totalEmployeesCounter = document.getElementById('total-employees');
    const totalScannedCounter = document.getElementById('total-scanned');
    
    const scanHistoryList = document.getElementById('scan-history-list');
    const closeBtn = document.getElementById('close-btn');

    // --- PyQt6 WebChannel --- //
    let api;
    new QWebChannel(qt.webChannelTransport, function (channel) {
        api = channel.objects.api;
    });

    // --- Initialization --- //
    function initializeApp() {
        totalEmployeesCounter.textContent = TOTAL_EMPLOYEES.toLocaleString();
        totalScannedCounter.textContent = TOTAL_SCANNED_COUNT;
        barcodeInput.focus();
    }

    // --- UI Update Functions --- //
    function updateLiveFeedback(name) {
        liveFeedbackName.textContent = name;
        // Revert after 2 seconds
        setTimeout(() => {
            liveFeedbackName.textContent = 'Ready to scan...';
            liveFeedbackName.style.color = 'var(--deloitte-green)'; // Reset color to green
        }, 2000);
    }

    function updateScanHistory(employeeName) {
        const timestamp = new Date().toLocaleTimeString();
        MOCKED_HISTORY.unshift({ name: employeeName, time: timestamp });

        // Create new list item
        const listItem = document.createElement('li');
        listItem.className = 'collection-item';
        listItem.innerHTML = `<span class="name">${employeeName}</span><span class="timestamp">${timestamp}</span>`;

        // Add to top of the list
        scanHistoryList.prepend(listItem);
    }

    function updateDashboard() {
        TOTAL_SCANNED_COUNT++;
        totalScannedCounter.textContent = TOTAL_SCANNED_COUNT;
    }

    // --- Event Listeners --- //
    barcodeInput.addEventListener('keyup', (event) => {
        if (event.key === 'Enter') {
            const barcode = barcodeInput.value.trim();
            if (!barcode) return;

            const employee = MOCKED_EMPLOYEES.find(emp => emp.barcode === barcode);

            if (employee) {
                updateLiveFeedback(employee.fullName);
                liveFeedbackName.style.color = 'var(--deloitte-black)'; // Set color for success
                updateScanHistory(employee.fullName);
                updateDashboard();
            } else {
                updateLiveFeedback('Not Found !');
                liveFeedbackName.style.color = 'red'; // Set color to red for error
            }

            // Clear and refocus for the next scan
            barcodeInput.value = '';
            barcodeInput.focus();
        }
    });

    // Add listener for the Escape key to close the application
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            if (api) {
                api.close_window();
            }
        }
    });

    // Add listener for the close button
    closeBtn.addEventListener('click', () => {
        if (api) {
            api.close_window();
        }
    });

    // --- Start the app --- //
    initializeApp();
});
