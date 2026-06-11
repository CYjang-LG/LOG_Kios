from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify, session
import sqlite3
import os
import pandas as pd
import sys
from datetime import datetime, timedelta
import json

app = Flask(__name__)
# SECRET_KEY: 환경변수 없으면 고정 fallback 사용 (서버 재시작 시 세션 유지)
app.secret_key = os.environ.get('SECRET_KEY', 'log-kios-fixed-secret-key-2024')

# 관리자 PIN (환경변수로 변경 가능, 기본값: 1234)
ADMIN_PIN = os.environ.get('ADMIN_PIN', '1234')

# exe 실행용 경로 설정
BASE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'logs.db')
EXPORT_DIR = os.path.join(BASE_DIR, 'export_logs')

# export 폴더 없으면 생성
if not os.path.exists(EXPORT_DIR):
    os.makedirs(EXPORT_DIR)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    
    # 학과 테이블
    conn.execute('''CREATE TABLE IF NOT EXISTS departments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    
    # 교수 테이블
    conn.execute('''CREATE TABLE IF NOT EXISTS professors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    department_id INTEGER,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (department_id) REFERENCES departments (id)
                )''')
    
    # 사용자 테이블
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    department_id INTEGER,
                    professor_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (department_id) REFERENCES departments (id),
                    FOREIGN KEY (professor_id) REFERENCES professors (id)
                )''')
    
    # 장비 테이블
    conn.execute('''CREATE TABLE IF NOT EXISTS equipment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    
    # 로그 테이블
    conn.execute('''CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT,
                    department TEXT,
                    professor TEXT,
                    student_name TEXT,
                    equipment TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    duration INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    
    # 기본 학과 데이터
    default_departments = [
        '생명과학과', '화학과', '물리학과', '수학과', '컴퓨터과학과',
        '전자공학과', '기계공학과', '화학공학과', '재료공학과', '환경공학과'
    ]
    for dept_name in default_departments:
        conn.execute('INSERT OR IGNORE INTO departments (name) VALUES (?)', (dept_name,))
    
    # 기본 장비 데이터
    default_equipment = [
        'PCR Machine', 'Centrifuge', 'Microscope', 'Incubator',
        'Autoclave', 'Spectrophotometer', 'pH Meter', 'Balance',
        'Freezer (-80°C)', 'Refrigerator', 'Water Bath', 'Shaker',
        'Electrophoresis System', 'Gel Doc System', 'Flow Cytometer',
        'Cell Counter', 'Sonicator', 'Laminar Flow Hood', 'Rotary Evaporator',
        'Chromatography System'
    ]
    for equipment_name in default_equipment:
        conn.execute('INSERT OR IGNORE INTO equipment (name) VALUES (?)', (equipment_name,))
    
    conn.commit()
    conn.close()

init_db()

# === 어드민 인증 헬퍼 ===

def is_admin():
    return session.get('is_admin', False)

def require_admin():
    """어드민 인증 안 됐으면 로그인 페이지로 리다이렉트"""
    if not is_admin():
        flash('관리자 인증이 필요합니다.')
        return redirect(url_for('admin_login'))
    return None

# === 메인 사용자 플로우 ===

@app.route('/')
def index():
    """시작 화면 - 학과 선택"""
    conn = get_db_connection()
    departments = conn.execute('SELECT * FROM departments WHERE is_active = 1 ORDER BY name').fetchall()
    conn.close()
    return render_template('index.html', departments=departments)

@app.route('/professors/<int:department_id>')
def select_professor(department_id):
    """교수 선택 화면"""
    conn = get_db_connection()
    department = conn.execute('SELECT * FROM departments WHERE id = ?', (department_id,)).fetchone()
    professors = conn.execute(
        'SELECT * FROM professors WHERE department_id = ? AND is_active = 1 ORDER BY name',
        (department_id,)
    ).fetchall()
    conn.close()
    if not department:
        flash('해당 학과를 찾을 수 없습니다.')
        return redirect(url_for('index'))
    return render_template('select_professor.html', department=department, professors=professors)

@app.route('/students/<int:department_id>/<int:professor_id>')
def select_student(department_id, professor_id):
    """학생 선택 화면"""
    conn = get_db_connection()
    department = conn.execute('SELECT * FROM departments WHERE id = ?', (department_id,)).fetchone()
    professor = conn.execute('SELECT * FROM professors WHERE id = ?', (professor_id,)).fetchone()
    students = conn.execute(
        'SELECT * FROM users WHERE department_id = ? AND professor_id = ? ORDER BY name',
        (department_id, professor_id)
    ).fetchall()
    conn.close()
    return render_template('select_student.html', department=department, professor=professor, students=students)

@app.route('/equipment/<int:department_id>/<int:professor_id>/<int:student_id>')
def equipment_selection(department_id, professor_id, student_id):
    """장비 선택 화면"""
    conn = get_db_connection()
    department = conn.execute('SELECT * FROM departments WHERE id = ?', (department_id,)).fetchone()
    professor = conn.execute('SELECT * FROM professors WHERE id = ?', (professor_id,)).fetchone()
    student = conn.execute('SELECT * FROM users WHERE id = ?', (student_id,)).fetchone()
    equipment_list = conn.execute('SELECT * FROM equipment WHERE is_active = 1 ORDER BY name').fetchall()
    conn.close()
    return render_template('equipment_selection.html', department=department, professor=professor,
                           student=student, equipment_list=equipment_list)

@app.route('/time_selection/<int:department_id>/<int:professor_id>/<int:student_id>/<equipment_name>')
def time_selection(department_id, professor_id, student_id, equipment_name):
    """시간 선택 화면"""
    conn = get_db_connection()
    department = conn.execute('SELECT * FROM departments WHERE id = ?', (department_id,)).fetchone()
    professor = conn.execute('SELECT * FROM professors WHERE id = ?', (professor_id,)).fetchone()
    student = conn.execute('SELECT * FROM users WHERE id = ?', (student_id,)).fetchone()
    conn.close()
    time_options = []
    for minutes in range(5, 241, 5):
        hours = minutes // 60
        mins = minutes % 60
        if hours > 0:
            time_text = f"{hours}시간 {mins}분" if mins > 0 else f"{hours}시간"
        else:
            time_text = f"{mins}분"
        time_options.append({'minutes': minutes, 'text': time_text})
    now = datetime.now()
    return render_template(
        'time_selection.html',
        department=department, professor=professor, student=student,
        equipment_name=equipment_name, time_options=time_options,
        current_date=now.strftime('%Y-%m-%d'), current_time=now.strftime('%H:%M')
    )

@app.route('/confirm-usage', methods=['POST'])
def confirm_usage():
    """사용 기록 저장"""
    department_name = request.form.get('department', '').strip()
    professor_name = request.form.get('professor', '').strip()
    student_name = request.form.get('student', '').strip()
    equipment_name = request.form.get('equipment', '').strip()
    duration = request.form.get('duration', '0').strip()
    try:
        duration = int(duration)
    except ValueError:
        duration = 0
    current_time = datetime.now()
    date = current_time.strftime('%Y-%m-%d')
    start_time = current_time.strftime('%H:%M')
    end_time = (current_time + timedelta(minutes=duration)).strftime('%H:%M')
    conn = get_db_connection()
    conn.execute(
        '''INSERT INTO logs (date, department, professor, student_name, equipment, start_time, end_time, duration)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (date, department_name, professor_name, student_name, equipment_name, start_time, end_time, duration)
    )
    conn.commit()
    conn.close()
    hours = duration // 60
    minutes = duration % 60
    duration_text = f"{hours}시간 {minutes}분" if hours > 0 else f"{minutes}분"
    return render_template(
        'success.html',
        department=department_name, professor=professor_name, student=student_name,
        equipment=equipment_name, start_time=start_time, end_time=end_time, duration_text=duration_text
    )

# === 빠른 추가 기능 ===

@app.route('/quick-add')
def quick_add():
    return render_template('departments.html')

@app.route('/quick-add-department')
def quick_add_department():
    return render_template('departments.html')

@app.route('/quick-add-professor')
def quick_add_professor():
    conn = get_db_connection()
    departments = conn.execute('SELECT * FROM departments WHERE is_active = 1 ORDER BY name').fetchall()
    conn.close()
    return render_template('professor.html', departments=departments)

@app.route('/quick-add-student')
def quick_add_student():
    conn = get_db_connection()
    departments = conn.execute('SELECT * FROM departments WHERE is_active = 1 ORDER BY name').fetchall()
    conn.close()
    return render_template('users.html', departments=departments)

@app.route('/quick-save-department', methods=['POST'])
def quick_save_department():
    name = request.form.get('name', '').strip()
    if not name:
        flash('학과명을 입력해주세요!')
        return redirect(url_for('quick_add_department'))
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO departments (name) VALUES (?)', (name,))
        conn.commit()
        flash(f'{name}이(가) 추가되었습니다!')
    except sqlite3.IntegrityError:
        flash('이미 존재하는 학과입니다!')
    finally:
        conn.close()
    return redirect(url_for('index'))

# === API 엔드포인트 ===

@app.route('/get-professors/<int:department_id>')
def get_professors(department_id):
    conn = get_db_connection()
    professors = conn.execute(
        'SELECT * FROM professors WHERE department_id = ? AND is_active = 1 ORDER BY name',
        (department_id,)
    ).fetchall()
    conn.close()
    return jsonify([{'id': p['id'], 'name': p['name']} for p in professors])

# === 관리자 인증 ===

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """관리자 PIN 로그인"""
    if request.method == 'POST':
        pin = request.form.get('pin', '').strip()
        if pin == ADMIN_PIN:
            session['is_admin'] = True
            flash('관리자로 로그인되었습니다.')
            return redirect(url_for('admin'))
        else:
            flash('PIN이 올바르지 않습니다.')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    """관리자 로그아웃"""
    session.pop('is_admin', None)
    flash('로그아웃되었습니다.')
    return redirect(url_for('index'))

@app.route('/admin')
def admin():
    """관리자 페이지 (인증 필요)"""
    redir = require_admin()
    if redir:
        return redir
    return render_template('admin.html')

# === 로그 관리 (인증 필요) ===

@app.route('/logs')
def logs():
    redir = require_admin()
    if redir:
        return redir
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    equipment_filter = request.args.get('equipment', '', type=str)
    per_page = 20
    conn = get_db_connection()
    base_query = "SELECT * FROM logs"
    count_query = "SELECT COUNT(*) FROM logs"
    params = []
    conditions = []
    if search:
        conditions.append("student_name LIKE ?")
        params.append(f'%{search}%')
    if equipment_filter:
        conditions.append("equipment = ?")
        params.append(equipment_filter)
    if conditions:
        where_clause = " WHERE " + " AND ".join(conditions)
        base_query += where_clause
        count_query += where_clause
    total = conn.execute(count_query, params).fetchone()[0]
    offset = (page - 1) * per_page
    logs_data = conn.execute(base_query + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
                             params + [per_page, offset]).fetchall()
    equipment_list = conn.execute('SELECT DISTINCT equipment FROM logs ORDER BY equipment').fetchall()
    conn.close()
    total_pages = (total + per_page - 1) // per_page
    return render_template('logs.html',
                           logs=logs_data, page=page, total_pages=total_pages,
                           has_prev=page > 1, has_next=page < total_pages,
                           search=search, equipment_filter=equipment_filter,
                           equipment_list=equipment_list)

# === 사용자 관리 (인증 필요) ===

@app.route('/users')
def users():
    redir = require_admin()
    if redir:
        return redir
    conn = get_db_connection()
    users_data = conn.execute('''
        SELECT u.*, d.name as department_name, p.name as professor_name
        FROM users u
        LEFT JOIN departments d ON u.department_id = d.id
        LEFT JOIN professors p ON u.professor_id = p.id
        ORDER BY u.name
    ''').fetchall()
    departments = conn.execute('SELECT * FROM departments WHERE is_active = 1 ORDER BY name').fetchall()
    conn.close()
    return render_template('users.html', users=users_data, departments=departments)

@app.route('/add-user', methods=['POST'])
def add_user():
    redir = require_admin()
    if redir:
        return redir
    name = request.form.get('name', '').strip()
    department_id = request.form.get('department_id')
    professor_id = request.form.get('professor_id')
    if not name:
        flash('학생 이름을 입력해주세요!')
        return redirect(url_for('users'))
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO users (name, department_id, professor_id) VALUES (?, ?, ?)',
                     (name, department_id, professor_id))
        conn.commit()
        flash(f'{name}님이 추가되었습니다!')
    except Exception as e:
        flash('사용자 추가 중 오류가 발생했습니다!')
    finally:
        conn.close()
    return redirect(url_for('users'))

@app.route('/delete-user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    redir = require_admin()
    if redir:
        return redir
    conn = get_db_connection()
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    flash('사용자가 삭제되었습니다!')
    return redirect(url_for('users'))

# === 학과 관리 (인증 필요) ===

@app.route('/departments')
def departments():
    redir = require_admin()
    if redir:
        return redir
    conn = get_db_connection()
    departments_data = conn.execute('SELECT * FROM departments ORDER BY name').fetchall()
    conn.close()
    return render_template('departments.html', departments=departments_data)

@app.route('/add-department', methods=['POST'])
def add_department():
    redir = require_admin()
    if redir:
        return redir
    name = request.form.get('name', '').strip()
    if not name:
        flash('학과명을 입력해주세요!')
        return redirect(url_for('departments'))
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO departments (name) VALUES (?)', (name,))
        conn.commit()
        flash(f'{name}이(가) 추가되었습니다!')
    except sqlite3.IntegrityError:
        flash('이미 존재하는 학과입니다!')
    finally:
        conn.close()
    return redirect(url_for('departments'))

@app.route('/toggle-department/<int:department_id>', methods=['POST'])
def toggle_department(department_id):
    redir = require_admin()
    if redir:
        return redir
    conn = get_db_connection()
    conn.execute('UPDATE departments SET is_active = NOT is_active WHERE id = ?', (department_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('departments'))

# === 교수 관리 (인증 필요) ===

@app.route('/professors')
def professors():
    redir = require_admin()
    if redir:
        return redir
    conn = get_db_connection()
    professors_data = conn.execute('''
        SELECT p.*, d.name as department_name
        FROM professors p
        LEFT JOIN departments d ON p.department_id = d.id
        ORDER BY p.name
    ''').fetchall()
    departments = conn.execute('SELECT * FROM departments WHERE is_active = 1 ORDER BY name').fetchall()
    conn.close()
    return render_template('professor.html', professors=professors_data, departments=departments)

@app.route('/add-professor', methods=['POST'])
def add_professor():
    redir = require_admin()
    if redir:
        return redir
    name = request.form.get('name', '').strip()
    department_id = request.form.get('department_id')
    if not name or not department_id:
        flash('교수명과 학과를 모두 입력해주세요!')
        return redirect(url_for('professors'))
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO professors (name, department_id) VALUES (?, ?)', (name, department_id))
        conn.commit()
        flash(f'{name} 교수가 추가되었습니다!')
    except Exception as e:
        flash('교수 추가 중 오류가 발생했습니다!')
    finally:
        conn.close()
    return redirect(url_for('professors'))

@app.route('/toggle-professor/<int:professor_id>', methods=['POST'])
def toggle_professor(professor_id):
    redir = require_admin()
    if redir:
        return redir
    conn = get_db_connection()
    conn.execute('UPDATE professors SET is_active = NOT is_active WHERE id = ?', (professor_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('professors'))

# === 장비 관리 (인증 필요) ===

@app.route('/equipment-manage')
def equipment_manage():
    redir = require_admin()
    if redir:
        return redir
    conn = get_db_connection()
    equipment_data = conn.execute('SELECT * FROM equipment ORDER BY name').fetchall()
    conn.close()
    return render_template('equipment_manage.html', equipment=equipment_data)

@app.route('/add-equipment', methods=['POST'])
def add_equipment():
    redir = require_admin()
    if redir:
        return redir
    name = request.form.get('name', '').strip()
    if not name:
        flash('장비명을 입력해주세요!')
        return redirect(url_for('equipment_manage'))
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO equipment (name) VALUES (?)', (name,))
        conn.commit()
        flash(f'{name} 장비가 추가되었습니다!')
    except sqlite3.IntegrityError:
        flash('이미 존재하는 장비입니다!')
    finally:
        conn.close()
    return redirect(url_for('equipment_manage'))

@app.route('/toggle-equipment/<int:equipment_id>', methods=['POST'])
def toggle_equipment(equipment_id):
    redir = require_admin()
    if redir:
        return redir
    conn = get_db_connection()
    conn.execute('UPDATE equipment SET is_active = NOT is_active WHERE id = ?', (equipment_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('equipment_manage'))

# === 로그 삭제 (인증 필요, POST 방식) ===

@app.route('/delete/<int:log_id>', methods=['POST'])
def delete(log_id):
    redir = require_admin()
    if redir:
        return redir
    conn = get_db_connection()
    conn.execute('DELETE FROM logs WHERE id=?', (log_id,))
    conn.commit()
    conn.close()
    flash('로그가 삭제되었습니다!')
    return redirect(url_for('logs'))

@app.route('/delete_all', methods=['POST'])
def delete_all():
    redir = require_admin()
    if redir:
        return redir
    conn = get_db_connection()
    conn.execute('DELETE FROM logs')
    conn.execute("DELETE FROM sqlite_sequence WHERE name='logs'")
    conn.commit()
    conn.close()
    flash('모든 로그가 삭제되었습니다!')
    return redirect(url_for('logs'))

# === 엑셀 내보내기 (인증 필요) ===

@app.route('/export')
def export():
    redir = require_admin()
    if redir:
        return redir
    conn = get_db_connection()
    logs_data = conn.execute("""
        SELECT date, department, professor, student_name, equipment, start_time, end_time, duration, created_at
        FROM logs ORDER BY created_at DESC
    """).fetchall()
    conn.close()
    export_data = []
    for log in logs_data:
        hours = log['duration'] // 60
        minutes = log['duration'] % 60
        duration_text = f"{hours}시간 {minutes}분" if hours > 0 else f"{minutes}분"
        export_data.append({
            '날짜': log['date'], '학과': log['department'], '교수': log['professor'],
            '학생': log['student_name'], '장비': log['equipment'],
            '시작시간': log['start_time'], '종료시간': log['end_time'],
            '사용시간': duration_text, '등록일시': log['created_at']
        })
    df = pd.DataFrame(export_data)
    file_path = os.path.join(EXPORT_DIR, f'equipment_logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx')
    df.to_excel(file_path, index=False)
    # 다운로드 후 파일 자동 삭제 (누적 방지)
    try:
        response = send_file(file_path, as_attachment=True)
        os.remove(file_path)
        return response
    except Exception:
        return send_file(file_path, as_attachment=True)

if __name__ == '__main__':
    # 프로덕션 배포 시 debug=False
    app.run(host='127.0.0.1', port=5000, debug=False)
