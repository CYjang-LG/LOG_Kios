from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
import sqlite3
import os
import pandas as pd
import sys
from datetime import datetime, timedelta
import json

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

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
    
    # 사용자 테이블 (수정된 구조)
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
    
    # 로그 테이블 (수정된 구조)
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
    
    # 기본 데이터 삽입
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

# DB 초기화
init_db()

@app.route('/')
def index():
    """시작 화면 - 사용자 선택"""
    conn = get_db_connection()
    users = conn.execute('''
        SELECT u.*, d.name as department_name, p.name as professor_name
        FROM users u
        LEFT JOIN departments d ON u.department_id = d.id
        LEFT JOIN professors p ON u.professor_id = p.id
        ORDER BY u.name
    ''').fetchall()
    conn.close()
    return render_template('index.html', users=users)

@app.route('/equipment-simple/<user_name>')
def equipment_selection_simple(user_name):
    """단순 장비 선택 화면"""
    conn = get_db_connection()
    equipment_list = conn.execute(
        'SELECT * FROM equipment WHERE is_active = 1 ORDER BY name'
    ).fetchall()
    conn.close()
    return render_template('equipment_simple.html', user_name=user_name, equipment_list=equipment_list)

@app.route('/equipment/<user_name>')
def equipment_selection(user_name):
    """일반 장비 선택 화면"""
    conn = get_db_connection()
    equipment_list = conn.execute(
        'SELECT * FROM equipment WHERE is_active = 1 ORDER BY name'
    ).fetchall()
    conn.close()
    return render_template('equipment.html', user_name=user_name, equipment_list=equipment_list)

@app.route('/time-selection/<user_name>/<equipment_name>')
def time_selection(user_name, equipment_name):
    """시간 선택 화면"""
    # 5분 단위로 5분부터 4시간까지
    time_options = []
    for minutes in range(5, 241, 5):  # 5분부터 240분(4시간)까지 5분 단위
        hours = minutes // 60
        mins = minutes % 60
        if hours > 0:
            time_text = f"{hours}시간 {mins}분" if mins > 0 else f"{hours}시간"
        else:
            time_text = f"{mins}분"
        time_options.append({'minutes': minutes, 'text': time_text})
    
    return render_template('time_selection.html', 
                         user_name=user_name, 
                         equipment_name=equipment_name, 
                         time_options=time_options)

@app.route('/confirm-usage', methods=['POST'])
def confirm_usage():
    """사용 기록 저장"""
    user_name = request.form.get('user_name')
    equipment_name = request.form.get('equipment_name')
    duration = int(request.form.get('duration'))
    
    # 사용자 정보 조회
    conn = get_db_connection()
    user_info = conn.execute('''
        SELECT u.*, d.name as department_name, p.name as professor_name
        FROM users u
        LEFT JOIN departments d ON u.department_id = d.id
        LEFT JOIN professors p ON u.professor_id = p.id
        WHERE u.name = ?
    ''', (user_name,)).fetchone()
    
    current_time = datetime.now()
    date = current_time.strftime('%Y-%m-%d')
    start_time = current_time.strftime('%H:%M')
    
    # 종료 시간 계산
    end_datetime = current_time + timedelta(minutes=duration)
    end_time = end_datetime.strftime('%H:%M')
    
    # 기본값 설정
    department_name = user_info['department_name'] if user_info and user_info['department_name'] else '정보없음'
    professor_name = user_info['professor_name'] if user_info and user_info['professor_name'] else '정보없음'
    
    conn.execute('''INSERT INTO logs 
                   (date, department, professor, student_name, equipment, start_time, end_time, duration) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                 (date, department_name, professor_name, user_name, equipment_name, start_time, end_time, duration))
    conn.commit()
    conn.close()
    
    # 성공 메시지 - 시간 정보 포함
    hours = duration // 60
    minutes = duration % 60
    duration_text = f"{hours}시간 {minutes}분" if hours > 0 else f"{minutes}분"
    
    success_msg = f"""
    <div style="text-align: center; line-height: 1.8;">
        <div style="font-size: 1.5em; margin-bottom: 20px;">✅ 기록되었습니다!</div>
        <div><strong>학과:</strong> {department_name}</div>
        <div><strong>교수:</strong> {professor_name}</div>
        <div><strong>학생:</strong> {user_name}</div>
        <div><strong>장비:</strong> {equipment_name}</div>
        <div><strong>사용시간:</strong> {start_time} ~ {end_time} ({duration_text})</div>
    </div>
    """
    
    flash(success_msg)
    return redirect(url_for('index'))

@app.route('/admin')
def admin():
    """관리자 페이지"""
    return render_template('admin.html')

@app.route('/logs')
def logs():
    """로그 확인 페이지 (페이지네이션 포함)"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    equipment_filter = request.args.get('equipment', '', type=str)
    per_page = 20
    
    conn = get_db_connection()
    
    # 기본 쿼리
    base_query = "SELECT * FROM logs"
    count_query = "SELECT COUNT(*) FROM logs"
    params = []
    
    # 검색 조건 추가
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
    
    # 전체 개수 조회
    total = conn.execute(count_query, params).fetchone()[0]
    
    # 페이지네이션 적용
    offset = (page - 1) * per_page
    logs_query = base_query + " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    logs_data = conn.execute(logs_query, params + [per_page, offset]).fetchall()
    
    # 장비 목록 (필터용)
    equipment_list = conn.execute('SELECT DISTINCT equipment FROM logs ORDER BY equipment').fetchall()
    
    conn.close()
    
    # 페이지네이션 정보 계산
    total_pages = (total + per_page - 1) // per_page
    has_prev = page > 1
    has_next = page < total_pages
    
    return render_template('logs.html', 
                         logs=logs_data, 
                         page=page,
                         total_pages=total_pages,
                         has_prev=has_prev,
                         has_next=has_next,
                         search=search,
                         equipment_filter=equipment_filter,
                         equipment_list=equipment_list)

# === 사용자 관리 ===
@app.route('/users')
def users():
    """사용자 관리 페이지"""
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
    """사용자 추가"""
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
        print(f"Error adding user: {e}")
    finally:
        conn.close()
    
    return redirect(url_for('users'))

@app.route('/delete-user/<int:user_id>')
def delete_user(user_id):
    """사용자 삭제"""
    conn = get_db_connection()
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    flash('사용자가 삭제되었습니다!')
    return redirect(url_for('users'))

@app.route('/get-professors/<int:department_id>')
def get_professors(department_id):
    """특정 학과의 교수 목록 API"""
    conn = get_db_connection()
    professors = conn.execute(
        'SELECT * FROM professors WHERE department_id = ? AND is_active = 1 ORDER BY name', 
        (department_id,)
    ).fetchall()
    conn.close()
    
    result = [{'id': p['id'], 'name': p['name']} for p in professors]
    return jsonify(result)

# === 학과 관리 ===
@app.route('/departments')
def departments():
    """학과 관리 페이지"""
    conn = get_db_connection()
    departments_data = conn.execute('SELECT * FROM departments ORDER BY name').fetchall()
    conn.close()
    return render_template('departments.html', departments=departments_data)

@app.route('/add-department', methods=['POST'])
def add_department():
    """학과 추가"""
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

@app.route('/toggle-department/<int:department_id>')
def toggle_department(department_id):
    """학과 활성화/비활성화"""
    conn = get_db_connection()
    conn.execute('UPDATE departments SET is_active = NOT is_active WHERE id = ?', (department_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('departments'))

# === 교수 관리 ===
@app.route('/professors')
def professors():
    """교수 관리 페이지"""
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
    """교수 추가"""
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
        print(f"Error adding professor: {e}")
    finally:
        conn.close()
    
    return redirect(url_for('professors'))

@app.route('/toggle-professor/<int:professor_id>')
def toggle_professor(professor_id):
    """교수 활성화/비활성화"""
    conn = get_db_connection()
    conn.execute('UPDATE professors SET is_active = NOT is_active WHERE id = ?', (professor_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('professors'))

# === 장비 관리 ===
@app.route('/equipment-manage')
def equipment_manage():
    """장비 관리 페이지"""
    conn = get_db_connection()
    equipment_data = conn.execute('SELECT * FROM equipment ORDER BY name').fetchall()
    conn.close()
    return render_template('equipment_manage.html', equipment=equipment_data)

@app.route('/add-equipment', methods=['POST'])
def add_equipment():
    """장비 추가"""
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

@app.route('/toggle-equipment/<int:equipment_id>')
def toggle_equipment(equipment_id):
    """장비 활성화/비활성화"""
    conn = get_db_connection()
    conn.execute('UPDATE equipment SET is_active = NOT is_active WHERE id = ?', (equipment_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('equipment_manage'))

@app.route('/delete/<int:log_id>')
def delete(log_id):
    """개별 로그 삭제"""
    conn = get_db_connection()
    conn.execute("DELETE FROM logs WHERE id=?", (log_id,))
    conn.commit()
    conn.close()
    flash("로그가 삭제되었습니다!")
    return redirect(url_for('logs'))

@app.route('/delete_all')
def delete_all():
    """전체 로그 삭제"""
    conn = get_db_connection()
    conn.execute("DELETE FROM logs")
    conn.execute("DELETE FROM sqlite_sequence WHERE name='logs'")
    conn.commit()
    conn.close()
    flash("모든 로그가 삭제되었습니다!")
    return redirect(url_for('logs'))

@app.route('/export')
def export():
    """엑셀 내보내기"""
    conn = get_db_connection()
    logs_data = conn.execute("""
        SELECT date, department, professor, student_name, equipment, start_time, end_time, duration, created_at 
        FROM logs ORDER BY created_at DESC
    """).fetchall()
    conn.close()
    
    # 데이터 변환
    export_data = []
    for log in logs_data:
        hours = log['duration'] // 60
        minutes = log['duration'] % 60
        duration_text = f"{hours}시간 {minutes}분" if hours > 0 else f"{minutes}분"
        
        export_data.append({
            '날짜': log['date'],
            '학과': log['department'],
            '교수': log['professor'],
            '학생': log['student_name'],
            '장비': log['equipment'],
            '시작시간': log['start_time'],
            '종료시간': log['end_time'],
            '사용시간': duration_text,
            '등록일시': log['created_at']
        })
    
    df = pd.DataFrame(export_data)
    file_path = os.path.join(EXPORT_DIR, f'equipment_logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx')
    df.to_excel(file_path, index=False)
    
    return send_file(file_path, as_attachment=True)

if __name__ == '__main__':
    # 키오스크 태블릿 전용 - 로컬에서만 실행
    app.run(host='127.0.0.1', port=5000, debug=False)
