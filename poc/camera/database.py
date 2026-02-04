"""
SQLite Database Module for Employee Attendance System
Handles employee data, attendance records, and event management
"""

import sqlite3
import os
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from contextlib import contextmanager

DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'attendance.db')

@dataclass
class Employee:
    id: int
    badge_id: str
    name: str
    department: str
    email: Optional[str] = None
    created_at: Optional[str] = None

@dataclass
class AttendanceRecord:
    id: int
    employee_id: int
    event_id: int
    check_in_time: str
    check_out_time: Optional[str] = None
    check_in_method: str = 'usb_scanner'  # 'usb_scanner', 'camera', 'manual'
    check_out_method: Optional[str] = None

@dataclass
class Event:
    id: int
    name: str
    description: Optional[str]
    start_time: str
    end_time: str
    location: Optional[str]
    created_at: Optional[str] = None


class AttendanceDatabase:
    """SQLite database manager for attendance system"""
    
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self._init_database()
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _init_database(self):
        """Initialize database tables"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Employees table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS employees (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    badge_id TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    department TEXT,
                    email TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Events table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP NOT NULL,
                    location TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Attendance records table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_id INTEGER NOT NULL,
                    event_id INTEGER NOT NULL,
                    check_in_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    check_out_time TIMESTAMP,
                    check_in_method TEXT DEFAULT 'usb_scanner',
                    check_out_method TEXT,
                    FOREIGN KEY (employee_id) REFERENCES employees(id),
                    FOREIGN KEY (event_id) REFERENCES events(id),
                    UNIQUE(employee_id, event_id, check_in_time)
                )
            ''')
            
            # Create indexes for faster queries
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_badge_id ON employees(badge_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_attendance_employee ON attendance(employee_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_attendance_event ON attendance(event_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_attendance_checkin ON attendance(check_in_time)')
            
            conn.commit()
    
    # ==================== Employee Operations ====================
    
    def add_employee(self, badge_id: str, name: str, department: str = '',
                     email: Optional[str] = None) -> Employee:
        """Add a new employee"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO employees (badge_id, name, department, email)
                VALUES (?, ?, ?, ?)
            ''', (badge_id, name, department, email))

            employee_id = cursor.lastrowid
            conn.commit()
        return self.get_employee_by_id(employee_id)
    
    def get_employee_by_badge(self, badge_id: str) -> Optional[Employee]:
        """Get employee by badge ID"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM employees WHERE badge_id = ?', (badge_id,))
            row = cursor.fetchone()
            
            if row:
                return Employee(
                    id=row['id'],
                    badge_id=row['badge_id'],
                    name=row['name'],
                    department=row['department'] or '',
                    email=row['email'],
                    created_at=row['created_at']
                )
            return None
    
    def get_employee_by_id(self, employee_id: int) -> Optional[Employee]:
        """Get employee by internal ID"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM employees WHERE id = ?', (employee_id,))
            row = cursor.fetchone()
            
            if row:
                return Employee(
                    id=row['id'],
                    badge_id=row['badge_id'],
                    name=row['name'],
                    department=row['department'] or '',
                    email=row['email'],
                    created_at=row['created_at']
                )
            return None
    
    def get_all_employees(self) -> List[Employee]:
        """Get all employees"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM employees ORDER BY name')
            rows = cursor.fetchall()
            
            return [Employee(
                id=row['id'],
                badge_id=row['badge_id'],
                name=row['name'],
                department=row['department'] or '',
                email=row['email'],
                created_at=row['created_at']
            ) for row in rows]
    
    def update_employee(self, employee_id: int, **kwargs) -> Optional[Employee]:
        """Update employee information"""
        allowed_fields = ['badge_id', 'name', 'department', 'email']
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not updates:
            return None
        
        set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [employee_id]
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                UPDATE employees SET {set_clause} WHERE id = ?
            ''', values)
            
            if cursor.rowcount > 0:
                return self.get_employee_by_id(employee_id)
            return None
    
    def delete_employee(self, employee_id: int) -> bool:
        """Delete an employee"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM employees WHERE id = ?', (employee_id,))
            return cursor.rowcount > 0
    
    # ==================== Event Operations ====================
    
    def create_event(self, name: str, start_time: str, end_time: str,
                     description: Optional[str] = None,
                     location: Optional[str] = None) -> Event:
        """Create a new event"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO events (name, description, start_time, end_time, location)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, description, start_time, end_time, location))

            event_id = cursor.lastrowid
            conn.commit()
        return self.get_event_by_id(event_id)
    
    def get_event_by_id(self, event_id: int) -> Optional[Event]:
        """Get event by ID"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM events WHERE id = ?', (event_id,))
            row = cursor.fetchone()
            
            if row:
                return Event(
                    id=row['id'],
                    name=row['name'],
                    description=row['description'],
                    start_time=row['start_time'],
                    end_time=row['end_time'],
                    location=row['location'],
                    created_at=row['created_at']
                )
            return None
    
    def get_active_events(self) -> List[Event]:
        """Get currently active events"""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM events 
                WHERE start_time <= ? AND end_time >= ?
                ORDER BY start_time
            ''', (now, now))
            rows = cursor.fetchall()
            
            return [Event(
                id=row['id'],
                name=row['name'],
                description=row['description'],
                start_time=row['start_time'],
                end_time=row['end_time'],
                location=row['location'],
                created_at=row['created_at']
            ) for row in rows]
    
    def get_all_events(self) -> List[Event]:
        """Get all events"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM events ORDER BY start_time DESC')
            rows = cursor.fetchall()
            
            return [Event(
                id=row['id'],
                name=row['name'],
                description=row['description'],
                start_time=row['start_time'],
                end_time=row['end_time'],
                location=row['location'],
                created_at=row['created_at']
            ) for row in rows]
    
    # ==================== Attendance Operations ====================
    
    def record_check_in(self, employee_id: int, event_id: int, 
                        method: str = 'usb_scanner') -> Optional[AttendanceRecord]:
        """Record employee check-in"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            check_in_time = datetime.now().isoformat()
            
            try:
                cursor.execute('''
                    INSERT INTO attendance (employee_id, event_id, check_in_time, check_in_method)
                    VALUES (?, ?, ?, ?)
                ''', (employee_id, event_id, check_in_time, method))
                
                record_id = cursor.lastrowid
                conn.commit()
                return self.get_attendance_record(record_id)
            except Exception as e:
                print(f"Error recording check-in: {e}")
                return None
    
    def record_check_out(self, record_id: int, method: str = 'usb_scanner') -> Optional[AttendanceRecord]:
        """Record employee check-out"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            check_out_time = datetime.now().isoformat()

            cursor.execute('''
                UPDATE attendance
                SET check_out_time = ?, check_out_method = ?
                WHERE id = ? AND check_out_time IS NULL
            ''', (check_out_time, method, record_id))

            updated = cursor.rowcount > 0
            conn.commit()
        if updated:
            return self.get_attendance_record(record_id)
        return None
    
    def get_attendance_record(self, record_id: int) -> Optional[AttendanceRecord]:
        """Get attendance record by ID"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM attendance WHERE id = ?', (record_id,))
            row = cursor.fetchone()
            
            if row:
                return AttendanceRecord(
                    id=row['id'],
                    employee_id=row['employee_id'],
                    event_id=row['event_id'],
                    check_in_time=row['check_in_time'],
                    check_out_time=row['check_out_time'],
                    check_in_method=row['check_in_method'],
                    check_out_method=row['check_out_method']
                )
            return None
    
    def get_today_attendance_for_employee(self, employee_id: int, 
                                          event_id: int) -> Optional[AttendanceRecord]:
        """Get today's attendance record for an employee at an event"""
        today = datetime.now().strftime('%Y-%m-%d')
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM attendance 
                WHERE employee_id = ? AND event_id = ? 
                AND DATE(check_in_time) = ?
                ORDER BY check_in_time DESC LIMIT 1
            ''', (employee_id, event_id, today))
            row = cursor.fetchone()
            
            if row:
                return AttendanceRecord(
                    id=row['id'],
                    employee_id=row['employee_id'],
                    event_id=row['event_id'],
                    check_in_time=row['check_in_time'],
                    check_out_time=row['check_out_time'],
                    check_in_method=row['check_in_method'],
                    check_out_method=row['check_out_method']
                )
            return None
    
    def get_event_attendance(self, event_id: int) -> List[Dict[str, Any]]:
        """Get all attendance records for an event with employee details"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT a.*, e.badge_id, e.name as employee_name, e.department
                FROM attendance a
                JOIN employees e ON a.employee_id = e.id
                WHERE a.event_id = ?
                ORDER BY a.check_in_time DESC
            ''', (event_id,))
            rows = cursor.fetchall()
            
            return [{
                'id': row['id'],
                'employee_id': row['employee_id'],
                'badge_id': row['badge_id'],
                'employee_name': row['employee_name'],
                'department': row['department'],
                'check_in_time': row['check_in_time'],
                'check_out_time': row['check_out_time'],
                'check_in_method': row['check_in_method'],
                'check_out_method': row['check_out_method']
            } for row in rows]
    
    def get_attendance_stats(self, event_id: int) -> Dict[str, Any]:
        """Get attendance statistics for an event"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Total check-ins
            cursor.execute('''
                SELECT COUNT(DISTINCT employee_id) as total_checkins
                FROM attendance WHERE event_id = ?
            ''', (event_id,))
            total_checkins = cursor.fetchone()['total_checkins']
            
            # Currently checked in (no check-out)
            cursor.execute('''
                SELECT COUNT(*) as currently_checked_in
                FROM attendance WHERE event_id = ? AND check_out_time IS NULL
            ''', (event_id,))
            currently_checked_in = cursor.fetchone()['currently_checked_in']
            
            # Check-outs
            cursor.execute('''
                SELECT COUNT(*) as checkouts
                FROM attendance WHERE event_id = ? AND check_out_time IS NOT NULL
            ''', (event_id,))
            checkouts = cursor.fetchone()['checkouts']
            
            # Method breakdown
            cursor.execute('''
                SELECT check_in_method, COUNT(*) as count
                FROM attendance WHERE event_id = ?
                GROUP BY check_in_method
            ''', (event_id,))
            method_breakdown = {row['check_in_method']: row['count'] 
                               for row in cursor.fetchall()}
            
            return {
                'total_checkins': total_checkins,
                'currently_checked_in': currently_checked_in,
                'checkouts': checkouts,
                'method_breakdown': method_breakdown
            }
    
    # ==================== Sample Data ====================
    
    def add_sample_data(self):
        """Add sample data for testing"""
        # Add sample employees
        employees = [
            ('EMP001', 'John Smith', 'Engineering', 'john@company.com'),
            ('EMP002', 'Sarah Johnson', 'Marketing', 'sarah@company.com'),
            ('EMP003', 'Mike Chen', 'Sales', 'mike@company.com'),
            ('EMP004', 'Emily Davis', 'HR', 'emily@company.com'),
            ('EMP005', 'Robert Wilson', 'Engineering', 'robert@company.com'),
        ]
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for badge_id, name, dept, email in employees:
                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO employees (badge_id, name, department, email)
                        VALUES (?, ?, ?, ?)
                    ''', (badge_id, name, dept, email))
                except sqlite3.IntegrityError:
                    pass
        
        # Create a sample event
        now = datetime.now()
        event_start = now.replace(hour=9, minute=0, second=0).isoformat()
        event_end = now.replace(hour=18, minute=0, second=0).isoformat()
        
        try:
            self.create_event(
                name='Company Town Hall',
                description='Monthly all-hands meeting',
                start_time=event_start,
                end_time=event_end,
                location='Main Conference Room'
            )
        except Exception:
            pass


# Singleton instance
db = AttendanceDatabase()

if __name__ == '__main__':
    # Test the database
    db.add_sample_data()
    print("Database initialized with sample data")
    print(f"Total employees: {len(db.get_all_employees())}")
    print(f"Total events: {len(db.get_all_events())}")
