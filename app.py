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

# === 메인 사용자 플로우 ===

@app.route('/')
def index():
    """시작 화면 - 학과 선택"""
    conn = get_db_connection()
    departments = conn.execute('SELECT * FROM departments WHERE is_active = 1 ORDER BY name').fetchall()
    conn.close()
    print(f"Found {len(departments)} departments")  # 디버깅용
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
    
    print(f"Department: {department['name'] if department else 'Not found'}")
    print(f"Found {len(professors)} professors for department {department_id}")
    
    if not department:
        flash('해당 학과를 찾을 수 없습니다.')
        return redirect(url_for('index'))
    
    return render_template('select_professor.html', 
                         department=department, 
                         professors=professors)

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
    
    print(f"Department: {department['name'] if department else 'Not found'}")
    print(f"Professor: {professor['name'] if professor else 'Not found'}")
    print(f"Found {len(students)} students")
    
    return render_template('select_student.html', 
                         department=department, 
                         professor=professor, 
                         students=students)

@app.route('/equipment/<int:department_id>/<int:professor_id>/<int:student_id>')
def equipment_selection(department_id, professor_id, student_id):
    """장비 선택 화면"""
    conn = get_db_connection()
    department = conn.execute('SELECT * FROM departments WHERE id = ?', (department_id,)).fetchone()
    professor = conn.execute('SELECT * FROM professors WHERE id = ?', (professor_id,)).fetchone()
    student = conn.execute('SELECT * FROM users WHERE id = ?', (student_id,)).fetchone()
    equipment_list = conn.execute('SELECT * FROM equipment WHERE is_active = 1 ORDER BY name').fetchall()
    conn.close()
    
    print(f"Equipment selection - Student: {student['name'] if student else 'Not found'}")
    print(f"Found {len(equipment_list)} equipment")
    
    return render_template('equipment_selection.html', 
                         department=department,
                         professor=professor,
                         student=student,
                         equipment_list=equipment_list)

# --- 라우트 이름 통일 ---
@app.route('/time_selection/<int:department_id>/<int:professor_id>/<int:student_id>/<equipment_name>')
def time_selection(department_id, professor_id, student_id, equipment_name):
    """시간 선택 화면"""
    conn = get_db_connection()
    department = conn.execute('SELECT * FROM departments WHERE id = ?', (department_id,)).fetchone()
    professor = conn.execute('SELECT * FROM professors WHERE id = ?', (professor_id,)).fetchone()
    student = conn.execute('SELECT * FROM users WHERE id = ?', (student_id,)).fetchone()
    conn.close()
    
    print(f"Time selection - Equipment: {equipment_name}")
    
    # 5분 단위 옵션 생성
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
    current_date = now.strftime('%Y-%m-%d')
    current_time = now.strftime('%H:%M')
    return render_template(
        'time_selection.html',
        department=department,
        professor=professor,
        student=student,
        equipment_name=equipment_name,
        time_options=time_options,
        current_date=current_date,
        current_time=current_time
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

    # 종료 시간 계산
    end_datetime = current_time + timedelta(minutes=duration)
    end_time = end_datetime.strftime('%H:%M')

    conn = get_db_connection()
    conn.execute(
        '''INSERT INTO logs 
           (date, department, professor, student_name, equipment, start_time, end_time, duration) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (date, department_name, professor_name, student_name, equipment_name, start_time, end_time, duration)
    )
    conn.commit()
    conn.close()

    # 성공 메시지 - 시간 정보 포함
    hours = duration // 60
    minutes = duration % 60
    duration_text = f"{hours}시간 {minutes}분" if hours > 0 else f"{minutes}분"

    return render_template(
        'success.html',
        department=department_name,
        professor=professor_name,
        student=student_name,
        equipment=equipment_name,
        start_time=start_time,
        end_time=end_time,
        duration_text=duration_text
    )

# === 빠른 추가 기능 ===

@app.route('/quick-add')
def quick_add():
    """빠른 추가 메뉴"""
    return render_template('departments.html')

@app.route('/quick-add-department')
def quick_add_department():
    """빠른 학과 추가"""
    return render_template('departments.html')

@app.route('/quick-add-professor')
def quick_add_professor():
    """빠른 교수 추가"""
    conn = get_db_connection()
    departments = conn.execute('SELECT * FROM departments WHERE is_active = 1 ORDER BY name').fetchall()
    conn.close()
    return render_template('professor.html', departments=departments)

@app.route('/quick-add-student')
def quick_add_student():
    """빠른 학생 추가"""
    conn = get_db_connection()
    departments = conn.execute('SELECT * FROM departments WHERE is_active = 1 ORDER BY name').fetchall()
    conn.close()
    return render_template('users.html', departments=departments)

@app.route('/quick-save-department', methods=['POST'])
def quick_save_department():
    """빠른 학과 저장"""
    name = request.form.get('name', '').strip()
    
    print(f"Quick save department: {name}")
    
    if not name:
        flash('학과명을 입력해주세요!')
        return redirect(url_for('quick_add_department'))
    
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO departments (name) VALUES (?)', (name,))
        conn.commit()
        flash(f'{name}이(가) 추가되었습니다!')
        print(f"Department {name} added successfully")
    except sqlite3.IntegrityError:
        flash('이미 존재하는 학과입니다!')
        print(f"Department {name} already exists")
    finally:
        conn.close()
    
    return redirect(url_for('index'))


# === API 엔드포인트 ===

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
    print(f"API: Found {len(result)} professors for department {department_id}")
    return jsonify(result)

# === 관리자 기능 ===

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

# === 로그 관리 ===

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

# === 디버깅 라우트 ===

@app.route('/debug')
def debug():
    """디버깅 정보 확인"""
    conn = get_db_connection()
    
    # 모든 테이블 데이터 조회
    departments = conn.execute('SELECT * FROM departments').fetchall()
    professors = conn.execute('SELECT * FROM professors').fetchall()
    users = conn.execute('SELECT * FROM users').fetchall()
    equipment = conn.execute('SELECT * FROM equipment').fetchall()
    
    conn.close()
    
    debug_info = f"""
    <!DOCTYPE html>
    <html>
    <head><title>디버그 정보</title></head>
    <body style="font-family: Arial; padding: 20px;">
    <h2>데이터베이스 상태</h2>
    
    <h3>학과 ({len(departments)}개)</h3>
    <ul>
    {''.join([f"<li>ID: {dept['id']} | {dept['name']} (active: {dept['is_active']})</li>" for dept in departments])}
    </ul>
    
    <h3>교수 ({len(professors)}명)</h3>
    <ul>
    {''.join([f"<li>ID: {prof['id']} | {prof['name']} - Department ID: {prof['department_id']} (active: {prof['is_active']})</li>" for prof in professors])}
    </ul>
    
    <h3>학생 ({len(users)}명)</h3>
    <ul>
    {''.join([f"<li>ID: {user['id']} | {user['name']} - Dept: {user['department_id']}, Prof: {user['professor_id']}</li>" for user in users])}
    </ul>
    
    <h3>장비 ({len(equipment)}개)</h3>
    <ul>
    {''.join([f"<li>ID: {eq['id']} | {eq['name']} (active: {eq['is_active']})</li>" for eq in equipment])}
    </ul>
    
    <p><a href="/">← 메인으로 돌아가기</a></p>
    </body>
    </html>
    """
    
    return debug_info

if __name__ == '__main__':
    # 키오스크 태블릿 전용 - 로컬에서만 실행
    app.run(host='127.0.0.1', port=5000, debug=True)  # 디버그 모드 활성화