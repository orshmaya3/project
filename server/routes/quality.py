from flask import Blueprint, render_template, request, redirect, session, url_for, send_file
from db import get_db
from io import BytesIO
import openpyxl
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from utils.send_quality_alert import send_quality_alert

quality_bp = Blueprint('quality', __name__)

@quality_bp.route('/quality-check/<int:plan_id>', methods=['GET'])
def quality_check(plan_id):
    if session.get('role') not in ['operator', 'admin']:
        return redirect(url_for('dashboard'))

    cursor = get_db().cursor(dictionary=True)
    cursor.execute('SELECT * FROM ProductionPlans WHERE id = %s', (plan_id,))
    plan = cursor.fetchone()

    return render_template('quality_check.html', plan=plan)

@quality_bp.route('/quality-dashboard')
def quality_dashboard():
    if session.get('role') not in ['admin', 'operator']:
        return redirect(url_for('dashboard'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    customer = request.args.get('customer')
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    quality_status = request.args.get('quality_status')

    query = '''
        SELECT id, date, customer, quality_status, quality_notes, status
        FROM ProductionPlans
        WHERE (quality_status IS NOT NULL OR status = 'ממתין לבקרת איכות')
    '''
    params = []

    if customer:
        query += ' AND customer LIKE %s'
        params.append(f'%{customer}%')

    if from_date:
        query += ' AND date >= %s'
        params.append(from_date)

    if to_date:
        query += ' AND date <= %s'
        params.append(to_date)

    if quality_status == 'pending':
        query += ' AND quality_status IS NULL'
    elif quality_status:
        query += ' AND quality_status = %s'
        params.append(quality_status)
    else:
        query += ' AND (quality_status IS NOT NULL OR status = "ממתין לבקרת איכות")'

    query += ' ORDER BY id DESC'

    cursor.execute(query, params)
    checks = cursor.fetchall()

    return render_template('quality_dashboard.html', checks=checks)

@quality_bp.route('/submit-quality/<int:plan_id>', methods=['POST'])
def submit_quality(plan_id):
    if session.get('role') not in ['admin', 'operator']:
        return redirect(url_for('dashboard'))

    result = request.form['quality_status']
    notes = request.form['notes']

    if result not in ['עבר', 'נכשל']:
        return "❌ ערך לא תקין בבקרת איכות", 400

    db = get_db()
    cursor = db.cursor()

    new_status = 'עבר בקרת איכות' if result == 'עבר' else 'נכשל בקרת איכות'

    cursor.execute('''
        UPDATE ProductionPlans
        SET quality_status = %s, quality_notes = %s, status = %s
        WHERE id = %s
    ''', (result, notes, new_status, plan_id))

    db.commit()

    # שליפת מידע לשליחת מייל
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM ProductionPlans WHERE id = %s', (plan_id,))
    plan = cursor.fetchone()

    if plan:
        send_quality_alert(
            to_email='orshmaya3@gmail.com',
            plan_id=plan_id,
            status=result,
            customer=plan['customer']
        )

    return redirect('/dashboard')

@quality_bp.route('/export-quality-excel')
def export_quality_excel():
    cursor = get_db().cursor(dictionary=True)
    cursor.execute('''
        SELECT id, date, customer, status, quality_status, quality_notes
        FROM ProductionPlans
        WHERE quality_status IS NOT NULL OR status = 'ממתין לבקרת איכות'
        ORDER BY date DESC
    ''')
    checks = cursor.fetchall()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "בקרת איכות"

    headers = ['ID', 'תאריך', 'לקוח', 'סטטוס תוכנית', 'מצב בקרה', 'הערות']
    ws.append(headers)

    for row in checks:
        ws.append([
            row['id'],
            row['date'],
            row['customer'],
            row['status'],
            row['quality_status'],
            row['quality_notes'] or ''
        ])

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(output, as_attachment=True,
                     download_name="quality_checks.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

def send_quality_email(plan_id, result):
    sender = 'orshmaya3@gmail.com'
    recipient = 'orshmaya3@gmail.com'
    subject = f'עדכון בקרת איכות לתוכנית מס׳ {plan_id}'
    body = f'תוכנית מספר {plan_id} { "עברה" if result == "עבר" else "נכשלה" } בקרת איכות.'

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = recipient
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender, 'your_app_password')  # ← סיסמת אפליקציה
            server.send_message(msg)
            print(f'✔ מייל נשלח בהצלחה עבור תוכנית {plan_id}')
    except Exception as e:
        print(f'❌ שגיאה בשליחת מייל: {e}')