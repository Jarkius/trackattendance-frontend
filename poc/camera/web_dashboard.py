"""
Web Dashboard for Attendance System
Flask-based web interface for monitoring and managing attendance
"""

import os
import json
from datetime import datetime
from flask import Flask, render_template, jsonify, request, Response
from flask_cors import CORS
import threading
import time

# Import our modules
from database import db, Employee, Event, AttendanceRecord
from main_system import AttendanceSystem, SystemConfig

# Create Flask app
template_dir = os.path.join(os.path.dirname(__file__), 'templates')
static_dir = os.path.join(os.path.dirname(__file__), 'static')

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
CORS(app)

# Global system instance
attendance_system: AttendanceSystem = None
system_thread: threading.Thread = None


def get_system() -> AttendanceSystem:
    """Get or create global attendance system"""
    global attendance_system
    if attendance_system is None:
        config = SystemConfig(
            enable_usb_scanner=True,
            enable_camera_scanner=True,
            enable_proximity_detection=True,
            enable_voice=True
        )
        attendance_system = AttendanceSystem(config)
    return attendance_system


# ==================== Web Routes ====================

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('dashboard.html')


@app.route('/api/status')
def api_status():
    """Get system status"""
    system = get_system()
    return jsonify({
        'running': system.is_running if system else False,
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/start', methods=['POST'])
def api_start():
    """Start the attendance system"""
    global system_thread
    
    system = get_system()
    if system.is_running:
        return jsonify({'success': False, 'error': 'Already running'})
    
    def run_system():
        system.start()
        while system.is_running:
            time.sleep(0.1)
    
    system_thread = threading.Thread(target=run_system, daemon=True)
    system_thread.start()
    
    return jsonify({'success': True})


@app.route('/api/stop', methods=['POST'])
def api_stop():
    """Stop the attendance system"""
    system = get_system()
    if system and system.is_running:
        system.stop()
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Not running'})


@app.route('/api/stats')
def api_stats():
    """Get system statistics"""
    system = get_system()
    if system:
        stats = system.get_stats()
        return jsonify(stats)
    return jsonify({})


@app.route('/api/employees')
def api_employees():
    """Get all employees"""
    employees = db.get_all_employees()
    return jsonify([{
        'id': e.id,
        'badge_id': e.badge_id,
        'name': e.name,
        'department': e.department,
        'email': e.email
    } for e in employees])


@app.route('/api/employees', methods=['POST'])
def api_add_employee():
    """Add a new employee"""
    data = request.json
    try:
        employee = db.add_employee(
            badge_id=data['badge_id'],
            name=data['name'],
            department=data.get('department', ''),
            email=data.get('email')
        )
        return jsonify({
            'success': True,
            'employee': {
                'id': employee.id,
                'badge_id': employee.badge_id,
                'name': employee.name,
                'department': employee.department,
                'email': employee.email
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/events')
def api_events():
    """Get all events"""
    events = db.get_all_events()
    return jsonify([{
        'id': e.id,
        'name': e.name,
        'description': e.description,
        'start_time': e.start_time,
        'end_time': e.end_time,
        'location': e.location
    } for e in events])


@app.route('/api/events/active')
def api_active_events():
    """Get active events"""
    events = db.get_active_events()
    return jsonify([{
        'id': e.id,
        'name': e.name,
        'description': e.description,
        'start_time': e.start_time,
        'end_time': e.end_time,
        'location': e.location
    } for e in events])


@app.route('/api/events', methods=['POST'])
def api_create_event():
    """Create a new event"""
    data = request.json
    try:
        event = db.create_event(
            name=data['name'],
            start_time=data['start_time'],
            end_time=data['end_time'],
            description=data.get('description'),
            location=data.get('location')
        )
        return jsonify({
            'success': True,
            'event': {
                'id': event.id,
                'name': event.name,
                'description': event.description,
                'start_time': event.start_time,
                'end_time': event.end_time,
                'location': event.location
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/attendance/<int:event_id>')
def api_event_attendance(event_id):
    """Get attendance for an event"""
    records = db.get_event_attendance(event_id)
    return jsonify(records)


@app.route('/api/attendance/stats/<int:event_id>')
def api_attendance_stats(event_id):
    """Get attendance statistics for an event"""
    stats = db.get_attendance_stats(event_id)
    return jsonify(stats)


@app.route('/api/simulate-scan', methods=['POST'])
def api_simulate_scan():
    """Simulate a badge scan"""
    data = request.json
    badge_id = data.get('badge_id')
    
    system = get_system()
    if system and system.is_running:
        system.simulate_scan(badge_id)
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'System not running'})


@app.route('/api/events/set-current', methods=['POST'])
def api_set_current_event():
    """Set the current event"""
    data = request.json
    event_id = data.get('event_id')
    
    system = get_system()
    if system:
        system.set_event(event_id)
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'System not initialized'})


# ==================== SSE for real-time updates ====================

@app.route('/api/stream')
def api_stream():
    """Server-sent events for real-time updates"""
    def event_stream():
        last_stats = None
        while True:
            system = get_system()
            if system:
                stats = system.get_stats()
                if stats != last_stats:
                    last_stats = stats
                    yield f"data: {json.dumps({'type': 'stats', 'data': stats})}\n\n"
            time.sleep(1)
    
    return Response(event_stream(), mimetype='text/event-stream')


# ==================== Create HTML Templates ====================

def create_templates():
    """Create HTML template files"""
    os.makedirs(template_dir, exist_ok=True)
    os.makedirs(static_dir, exist_ok=True)
    
    # Main dashboard HTML
    dashboard_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Attendance System Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #f5f7fa;
            color: #333;
            line-height: 1.6;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1.5rem 2rem;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .header h1 {
            font-size: 1.8rem;
            font-weight: 600;
        }
        
        .header .status {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            margin-top: 0.5rem;
            font-size: 0.9rem;
        }
        
        .status-indicator {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #ff4757;
            transition: background 0.3s;
        }
        
        .status-indicator.active {
            background: #2ed573;
            box-shadow: 0 0 10px #2ed573;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }
        
        .controls {
            display: flex;
            gap: 1rem;
            margin-bottom: 2rem;
            flex-wrap: wrap;
        }
        
        .btn {
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            cursor: pointer;
            transition: all 0.3s;
            font-weight: 500;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .btn-primary {
            background: #667eea;
            color: white;
        }
        
        .btn-primary:hover {
            background: #5a6fd6;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        
        .btn-danger {
            background: #ff4757;
            color: white;
        }
        
        .btn-danger:hover {
            background: #ff3344;
        }
        
        .btn-secondary {
            background: #747d8c;
            color: white;
        }
        
        .btn-secondary:hover {
            background: #57606f;
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        
        .card {
            background: white;
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            transition: transform 0.3s, box-shadow 0.3s;
        }
        
        .card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 16px rgba(0,0,0,0.12);
        }
        
        .card h3 {
            color: #667eea;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 0.5rem;
        }
        
        .card .value {
            font-size: 2.5rem;
            font-weight: 700;
            color: #2f3542;
        }
        
        .card .subtitle {
            font-size: 0.85rem;
            color: #747d8c;
            margin-top: 0.25rem;
        }
        
        .section {
            background: white;
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }
        
        .section h2 {
            color: #2f3542;
            font-size: 1.25rem;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid #f1f2f6;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        th, td {
            text-align: left;
            padding: 0.75rem;
            border-bottom: 1px solid #f1f2f6;
        }
        
        th {
            font-weight: 600;
            color: #57606f;
            font-size: 0.85rem;
            text-transform: uppercase;
        }
        
        tr:hover {
            background: #f8f9fa;
        }
        
        .badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 500;
        }
        
        .badge-success {
            background: #d4edda;
            color: #155724;
        }
        
        .badge-warning {
            background: #fff3cd;
            color: #856404;
        }
        
        .badge-info {
            background: #d1ecf1;
            color: #0c5460;
        }
        
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        
        .modal.active {
            display: flex;
        }
        
        .modal-content {
            background: white;
            border-radius: 12px;
            padding: 2rem;
            max-width: 500px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
        }
        
        .form-group {
            margin-bottom: 1rem;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 0.5rem;
            font-weight: 500;
            color: #57606f;
        }
        
        .form-group input, .form-group select {
            width: 100%;
            padding: 0.75rem;
            border: 1px solid #ddd;
            border-radius: 8px;
            font-size: 1rem;
        }
        
        .form-group input:focus, .form-group select:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .empty-state {
            text-align: center;
            padding: 3rem;
            color: #747d8c;
        }
        
        .empty-state svg {
            width: 64px;
            height: 64px;
            margin-bottom: 1rem;
            opacity: 0.5;
        }
        
        @media (max-width: 768px) {
            .container {
                padding: 1rem;
            }
            
            .controls {
                flex-direction: column;
            }
            
            .btn {
                width: 100%;
                justify-content: center;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📋 Attendance System</h1>
        <div class="status">
            <span class="status-indicator" id="statusIndicator"></span>
            <span id="statusText">System Stopped</span>
        </div>
    </div>
    
    <div class="container">
        <div class="controls">
            <button class="btn btn-primary" onclick="startSystem()">
                ▶️ Start System
            </button>
            <button class="btn btn-danger" onclick="stopSystem()">
                ⏹️ Stop System
            </button>
            <button class="btn btn-secondary" onclick="showAddEmployee()">
                ➕ Add Employee
            </button>
            <button class="btn btn-secondary" onclick="showCreateEvent()">
                📅 Create Event
            </button>
            <button class="btn btn-secondary" onclick="simulateScan()">
                🔍 Simulate Scan
            </button>
        </div>
        
        <div class="grid">
            <div class="card">
                <h3>Total Scans</h3>
                <div class="value" id="totalScans">0</div>
                <div class="subtitle">Since system started</div>
            </div>
            <div class="card">
                <h3>Check-ins</h3>
                <div class="value" id="checkins">0</div>
                <div class="subtitle">Successful check-ins</div>
            </div>
            <div class="card">
                <h3>Failed Scans</h3>
                <div class="value" id="failedScans">0</div>
                <div class="subtitle">Unrecognized badges</div>
            </div>
            <div class="card">
                <h3>Last Scan</h3>
                <div class="value" id="lastScan" style="font-size: 1.2rem;">-</div>
                <div class="subtitle" id="lastScanTime">Never</div>
            </div>
        </div>
        
        <div class="section">
            <h2>📊 Today's Attendance</h2>
            <div id="attendanceList">
                <div class="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
                    </svg>
                    <p>No attendance records yet</p>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2>👥 Employees</h2>
            <div id="employeesList">
                <table>
                    <thead>
                        <tr>
                            <th>Badge ID</th>
                            <th>Name</th>
                            <th>Department</th>
                            <th>Email</th>
                        </tr>
                    </thead>
                    <tbody id="employeesTable">
                    </tbody>
                </table>
            </div>
        </div>
        
        <div class="section">
            <h2>📅 Events</h2>
            <div id="eventsList">
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Name</th>
                            <th>Location</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody id="eventsTable">
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    
    <!-- Add Employee Modal -->
    <div class="modal" id="addEmployeeModal">
        <div class="modal-content">
            <h2>Add New Employee</h2>
            <div class="form-group">
                <label>Badge ID</label>
                <input type="text" id="empBadgeId" placeholder="e.g., EMP001">
            </div>
            <div class="form-group">
                <label>Name</label>
                <input type="text" id="empName" placeholder="Full Name">
            </div>
            <div class="form-group">
                <label>Department</label>
                <input type="text" id="empDept" placeholder="e.g., Engineering">
            </div>
            <div class="form-group">
                <label>Email (optional)</label>
                <input type="email" id="empEmail" placeholder="email@company.com">
            </div>
            <div class="controls">
                <button class="btn btn-primary" onclick="addEmployee()">Add Employee</button>
                <button class="btn btn-secondary" onclick="closeModal('addEmployeeModal')">Cancel</button>
            </div>
        </div>
    </div>
    
    <!-- Create Event Modal -->
    <div class="modal" id="createEventModal">
        <div class="modal-content">
            <h2>Create New Event</h2>
            <div class="form-group">
                <label>Event Name</label>
                <input type="text" id="eventName" placeholder="e.g., Company Town Hall">
            </div>
            <div class="form-group">
                <label>Description</label>
                <input type="text" id="eventDesc" placeholder="Optional description">
            </div>
            <div class="form-group">
                <label>Location</label>
                <input type="text" id="eventLocation" placeholder="e.g., Main Conference Room">
            </div>
            <div class="controls">
                <button class="btn btn-primary" onclick="createEvent()">Create Event</button>
                <button class="btn btn-secondary" onclick="closeModal('createEventModal')">Cancel</button>
            </div>
        </div>
    </div>
    
    <script>
        // Update status periodically
        setInterval(updateStatus, 1000);
        setInterval(updateStats, 1000);
        setInterval(loadAttendance, 2000);
        
        // Initial load
        loadEmployees();
        loadEvents();
        
        async function updateStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                const indicator = document.getElementById('statusIndicator');
                const text = document.getElementById('statusText');
                
                if (data.running) {
                    indicator.classList.add('active');
                    text.textContent = 'System Running';
                } else {
                    indicator.classList.remove('active');
                    text.textContent = 'System Stopped';
                }
            } catch (e) {
                console.error('Status update failed:', e);
            }
        }
        
        async function updateStats() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();
                
                document.getElementById('totalScans').textContent = data.total_scans || 0;
                document.getElementById('checkins').textContent = data.successful_checkins || 0;
                document.getElementById('failedScans').textContent = data.failed_scans || 0;
                
                if (data.last_scan_data) {
                    document.getElementById('lastScan').textContent = data.last_scan_data;
                    const time = data.last_scan_time ? new Date(data.last_scan_time * 1000).toLocaleTimeString() : 'Never';
                    document.getElementById('lastScanTime').textContent = time;
                }
            } catch (e) {
                console.error('Stats update failed:', e);
            }
        }
        
        async function loadAttendance() {
            // Load from first active event or first event
            try {
                const eventsRes = await fetch('/api/events/active');
                const events = await eventsRes.json();
                
                if (events.length > 0) {
                    const res = await fetch(`/api/attendance/${events[0].id}`);
                    const data = await res.json();
                    
                    const container = document.getElementById('attendanceList');
                    if (data.length === 0) {
                        container.innerHTML = `
                            <div class="empty-state">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
                                </svg>
                                <p>No attendance records yet</p>
                            </div>
                        `;
                    } else {
                        let html = '<table><thead><tr><th>Name</th><th>Department</th><th>Check-in</th><th>Status</th></tr></thead><tbody>';
                        data.slice(0, 10).forEach(record => {
                            const status = record.check_out_time 
                                ? '<span class="badge badge-info">Checked Out</span>' 
                                : '<span class="badge badge-success">Checked In</span>';
                            html += `<tr>
                                <td>${record.employee_name}</td>
                                <td>${record.department || '-'}</td>
                                <td>${new Date(record.check_in_time).toLocaleTimeString()}</td>
                                <td>${status}</td>
                            </tr>`;
                        });
                        html += '</tbody></table>';
                        container.innerHTML = html;
                    }
                }
            } catch (e) {
                console.error('Attendance load failed:', e);
            }
        }
        
        async function loadEmployees() {
            try {
                const res = await fetch('/api/employees');
                const data = await res.json();
                
                const tbody = document.getElementById('employeesTable');
                tbody.innerHTML = data.map(emp => `
                    <tr>
                        <td>${emp.badge_id}</td>
                        <td>${emp.name}</td>
                        <td>${emp.department || '-'}</td>
                        <td>${emp.email || '-'}</td>
                    </tr>
                `).join('');
            } catch (e) {
                console.error('Employees load failed:', e);
            }
        }
        
        async function loadEvents() {
            try {
                const res = await fetch('/api/events');
                const data = await res.json();
                
                const tbody = document.getElementById('eventsTable');
                tbody.innerHTML = data.map(evt => {
                    const now = new Date();
                    const start = new Date(evt.start_time);
                    const end = new Date(evt.end_time);
                    const isActive = now >= start && now <= end;
                    const status = isActive 
                        ? '<span class="badge badge-success">Active</span>' 
                        : '<span class="badge badge-warning">Inactive</span>';
                    
                    return `<tr>
                        <td>${evt.id}</td>
                        <td>${evt.name}</td>
                        <td>${evt.location || '-'}</td>
                        <td>${status}</td>
                    </tr>`;
                }).join('');
            } catch (e) {
                console.error('Events load failed:', e);
            }
        }
        
        async function startSystem() {
            try {
                const res = await fetch('/api/start', { method: 'POST' });
                const data = await res.json();
                if (data.success) {
                    alert('System started successfully!');
                } else {
                    alert('Failed to start: ' + (data.error || 'Unknown error'));
                }
            } catch (e) {
                alert('Error starting system: ' + e.message);
            }
        }
        
        async function stopSystem() {
            try {
                const res = await fetch('/api/stop', { method: 'POST' });
                const data = await res.json();
                if (data.success) {
                    alert('System stopped!');
                }
            } catch (e) {
                alert('Error stopping system: ' + e.message);
            }
        }
        
        function showAddEmployee() {
            document.getElementById('addEmployeeModal').classList.add('active');
        }
        
        function showCreateEvent() {
            document.getElementById('createEventModal').classList.add('active');
        }
        
        function closeModal(id) {
            document.getElementById(id).classList.remove('active');
        }
        
        async function addEmployee() {
            const badgeId = document.getElementById('empBadgeId').value;
            const name = document.getElementById('empName').value;
            const dept = document.getElementById('empDept').value;
            const email = document.getElementById('empEmail').value;
            
            if (!badgeId || !name) {
                alert('Badge ID and Name are required');
                return;
            }
            
            try {
                const res = await fetch('/api/employees', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ badge_id: badgeId, name, department: dept, email })
                });
                const data = await res.json();
                
                if (data.success) {
                    alert('Employee added successfully!');
                    closeModal('addEmployeeModal');
                    loadEmployees();
                    // Clear form
                    document.getElementById('empBadgeId').value = '';
                    document.getElementById('empName').value = '';
                    document.getElementById('empDept').value = '';
                    document.getElementById('empEmail').value = '';
                } else {
                    alert('Failed to add employee: ' + (data.error || 'Unknown error'));
                }
            } catch (e) {
                alert('Error: ' + e.message);
            }
        }
        
        async function createEvent() {
            const name = document.getElementById('eventName').value;
            const desc = document.getElementById('eventDesc').value;
            const location = document.getElementById('eventLocation').value;
            
            if (!name) {
                alert('Event name is required');
                return;
            }
            
            const now = new Date();
            const start = now.toISOString();
            const end = new Date(now.getTime() + 8 * 60 * 60 * 1000).toISOString();
            
            try {
                const res = await fetch('/api/events', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, description: desc, location, start_time: start, end_time: end })
                });
                const data = await res.json();
                
                if (data.success) {
                    alert('Event created successfully!');
                    closeModal('createEventModal');
                    loadEvents();
                    document.getElementById('eventName').value = '';
                    document.getElementById('eventDesc').value = '';
                    document.getElementById('eventLocation').value = '';
                } else {
                    alert('Failed to create event: ' + (data.error || 'Unknown error'));
                }
            } catch (e) {
                alert('Error: ' + e.message);
            }
        }
        
        async function simulateScan() {
            const badgeId = prompt('Enter badge ID to simulate:');
            if (!badgeId) return;
            
            try {
                const res = await fetch('/api/simulate-scan', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ badge_id: badgeId })
                });
                const data = await res.json();
                
                if (data.success) {
                    alert('Scan simulated!');
                } else {
                    alert('Failed: ' + (data.error || 'System not running'));
                }
            } catch (e) {
                alert('Error: ' + e.message);
            }
        }
        
        // Close modals on outside click
        window.onclick = function(event) {
            if (event.target.classList.contains('modal')) {
                event.target.classList.remove('active');
            }
        }
    </script>
</body>
</html>
'''
    
    # Write template
    with open(os.path.join(template_dir, 'dashboard.html'), 'w') as f:
        f.write(dashboard_html)
    
    print(f"Templates created in {template_dir}")


# ==================== Main Entry Point ====================

def run_web_dashboard(host='0.0.0.0', port=5000, debug=False):
    """Run the web dashboard"""
    # Create templates
    create_templates()
    
    # Initialize database
    db.add_sample_data()
    
    print("=" * 60)
    print("Attendance System Web Dashboard")
    print("=" * 60)
    print(f"\nOpen your browser and navigate to:")
    print(f"  http://localhost:{port}")
    print(f"\nOr on your network:")
    import socket
    hostname = socket.gethostname()
    try:
        ip = socket.gethostbyname(hostname)
        print(f"  http://{ip}:{port}")
    except:
        pass
    print("\nPress Ctrl+C to stop")
    print("=" * 60)
    
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Attendance System Web Dashboard')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    run_web_dashboard(host=args.host, port=args.port, debug=args.debug)
