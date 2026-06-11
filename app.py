from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import sqlite3
import os
import json
from datetime import datetime, date
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'log-kios-secret-key-2024')
ADMIN_PIN = os.environ.get('ADMIN_PIN', '1234')
DB_PATH = 'visitor.db'

# ───────────────────────────────
# DB 초기화
# ───────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS visitors (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            visit_date  TEXT    NOT NULL,
            time_in     TEXT    NOT NULL DEFAULT '09:00',
            time_out    TEXT    NOT NULL DEFAULT '18:00',
            name        TEXT    NOT NULL,
            affiliation TEXT    NOT NULL,
            purpose     TEXT    NOT NULL,
            note        TEXT,
            created_at  TEXT    NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ───────────────────────────────
# 키오스크 메인
# ───────────────────────────────
@app.route('/')
def index():
    today = date.today().strftime('%Y-%m-%d')
    return render_template('index.html', today=today)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        visit_date  = request.form.get('visit_date', '').strip()
        time_in     = request.form.get('time_in', '09:00').strip()
        time_out    = request.form.get('time_out', '18:00').strip()
        name        = request.form.get('name', '').strip()
        affiliation = request.form.get('affiliation', '').strip()
        purpose     = request.form.get('purpose', '').strip()
        note        = request.form.get('note', '').strip()

        if not all([visit_date, time_in, time_out, name, affiliation, purpose]):
            flash('필수 항목을 모두 입력해주세요.', 'error')
            return redirect(url_for('register'))

        conn = get_db()
        conn.execute(
            'INSERT INTO visitors (visit_date,time_in,time_out,name,affiliation,purpose,note,created_at) VALUES (?,?,?,?,?,?,?,?)',
            (visit_date, time_in, time_out, name, affiliation, purpose, note,
             datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        conn.commit()
        conn.close()
        return redirect(url_for('success', name=name))

    today = date.today().strftime('%Y-%m-%d')
    return render_template('register.html', today=today)

@app.route('/success')
def success():
    name = request.args.get('name', '')
    return render_template('success.html', name=name)

# ───────────────────────────────
# 관리자
# ───────────────────────────────
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('pin') == ADMIN_PIN:
            session['admin'] = True
            return redirect(url_for('admin'))
        flash('PIN이 올바르지 않습니다.', 'error')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('index'))

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/admin')
@admin_required
def admin():
    conn = get_db()
    page      = request.args.get('page', 1, type=int)
    per_page  = 20
    search    = request.args.get('search', '').strip()
    date_from = request.args.get('date_from', '')
    date_to   = request.args.get('date_to', '')

    query  = 'SELECT * FROM visitors WHERE 1=1'
    params = []
    if search:
        query  += ' AND (name LIKE ? OR affiliation LIKE ? OR purpose LIKE ?)'
        params += [f'%{search}%', f'%{search}%', f'%{search}%']
    if date_from:
        query  += ' AND visit_date >= ?'
        params.append(date_from)
    if date_to:
        query  += ' AND visit_date <= ?'
        params.append(date_to)

    total = conn.execute('SELECT COUNT(*) FROM (' + query + ')', params).fetchone()[0]
    query += ' ORDER BY visit_date DESC, time_in DESC LIMIT ? OFFSET ?'
    params += [per_page, (page - 1) * per_page]
    visitors = conn.execute(query, params).fetchall()
    conn.close()

    total_pages = (total + per_page - 1) // per_page
    return render_template('admin.html',
        visitors=visitors, page=page, total_pages=total_pages,
        total=total, search=search, date_from=date_from, date_to=date_to)

@app.route('/admin/delete/<int:vid>', methods=['POST'])
@admin_required
def delete_visitor(vid):
    conn = get_db()
    conn.execute('DELETE FROM visitors WHERE id=?', (vid,))
    conn.commit()
    conn.close()
    flash('기록이 삭제되었습니다.')
    return redirect(url_for('admin'))

@app.route('/admin/delete_all', methods=['POST'])
@admin_required
def delete_all():
    conn = get_db()
    conn.execute('DELETE FROM visitors')
    conn.commit()
    conn.close()
    flash('모든 기록이 삭제되었습니다.')
    return redirect(url_for('admin'))

@app.route('/admin/export')
@admin_required
def export():
    conn = get_db()
    rows = conn.execute('SELECT * FROM visitors ORDER BY visit_date DESC, time_in DESC').fetchall()
    conn.close()

    os.makedirs('export_logs', exist_ok=True)
    fname = f'export_logs/visitors_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '출입자 기록'

    headers = ['No', '날짜', '입실', '퇴실', '이름', '소속', '방문목적', '기타', '등록시각']
    header_fill = PatternFill('solid', fgColor='667EEA')
    header_font = Font(bold=True, color='FFFFFF')
    thin = Side(style='thin')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill   = header_fill
        cell.font   = header_font
        cell.alignment = Alignment(horizontal='center')
        cell.border = border

    for i, row in enumerate(rows, 1):
        data = [i, row['visit_date'], row['time_in'], row['time_out'],
                row['name'], row['affiliation'], row['purpose'],
                row['note'] or '', row['created_at']]
        for col, val in enumerate(data, 1):
            cell = ws.cell(row=i+1, column=col, value=val)
            cell.border = border
            cell.alignment = Alignment(horizontal='center' if col <= 4 else 'left')

    col_widths = [6, 12, 8, 8, 10, 16, 20, 16, 18]
    for col, w in enumerate(col_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = w

    wb.save(fname)
    resp = send_file(os.path.abspath(fname), as_attachment=True,
                     download_name=os.path.basename(fname))
    # 전송 후 파일 삭제
    @resp.call_on_close
    def cleanup():
        try:
            os.remove(fname)
        except:
            pass
    return resp

# 오프라인 페이지
@app.route('/offline')
def offline():
    return render_template('offline.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
