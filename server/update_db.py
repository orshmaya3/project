import mysql.connector
import os
from dotenv import load_dotenv

# טען משתני סביבה מהקובץ .env
load_dotenv()

# התחברות למסד הנתונים בענן (Railway)
conn = mysql.connector.connect(
    host=os.environ.get("MYSQL_HOST"),
    port=int(os.environ.get("MYSQL_PORT")),
    user=os.environ.get("MYSQL_USER"),
    password=os.environ.get("MYSQL_PASSWORD"),
    database=os.environ.get("MYSQL_DATABASE")
)

cur = conn.cursor()

# הוספת העמודות אם לא קיימות
try:
    cur.execute("ALTER TABLE ProductionPlans ADD COLUMN quality_status VARCHAR(255);")
except mysql.connector.Error as e:
    if "Duplicate column name" in str(e):
        print("🔁 העמודה quality_status כבר קיימת.")
    else:
        raise e

try:
    cur.execute("ALTER TABLE ProductionPlans ADD COLUMN quality_notes TEXT;")
except mysql.connector.Error as e:
    if "Duplicate column name" in str(e):
        print("🔁 העמודה quality_notes כבר קיימת.")
    else:
        raise e

conn.commit()
conn.close()
print("✅ סיום עדכון מבנה הטבלה.")
