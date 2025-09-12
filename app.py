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
    # 로그 테이블
    conn.execute('''CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT,
                    user_name TEXT,
                    equipment TEXT,
                    start_time TEXT,
                    duration INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    
    # 사용자 테이블
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    department TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    
    # 장비 테이블
    conn.execute('''CREATE TABLE IF NOT EXISTS equipment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    
    # 기본 장비 데이터 삽입
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
    users = conn.execute('SELECT * FROM users ORDER BY name').fetchall()
    conn.close()
    return render_template('index.html', users=users)

@app.route('/equipment-simple/<user_name>')
def equipment_selection_simple(user_name):
    """단순 장비 선택 화면"""
    conn = get_db_connection()
    # 필요한 장비 목록만 가져오거나, 단순화된 데이터만 가져오기
    equipment_list = conn.execute(
        'SELECT * FROM equipment WHERE is_active = 1 ORDER BY name'
    ).fetchall()
    conn.close()

    # 별도의 템플릿으로 렌더링
    return render_template(
        'equipment_simple.html',
        user_name=user_name,
        equipment_list=equipment_list
    )
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
    department_name = request.form.get('department_name')
    professor_name = request.form.get('professor_name')
    student_name = request.form.get('student_name')
    equipment_name = request.form.get('equipment_name')
    duration = int(request.form.get('duration'))
    
    current_time = datetime.now()
    date = current_time.strftime('%Y-%m-%d')
    start_time = current_time.strftime('%H:%M')
    
    # 종료 시간 계산
    end_datetime = current_time + timedelta(minutes=duration)
    end_time = end_datetime.strftime('%H:%M')
    
    conn = get_db_connection()
    conn.execute('''INSERT INTO logs 
                   (date, department, professor, student_name, equipment, start_time, end_time, duration) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                 (date, department_name, professor_name, student_name, equipment_name, start_time, end_time, duration))
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
        <div><strong>학생:</strong> {student_name}</div>
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
        conditions.append("user_name LIKE ?")
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

# 기존 users 관련 라우트 제거하고 새로운 구조로 변경

# users 관련 라우트 제거됨 - 이제 departments와 professors 사용

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