import os
from flask import Flask, render_template, jsonify, request
import sqlite3

app = Flask(__name__)
DB_FILE = "visa_tracker.db"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database and seeds master documents if empty."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Master Documents Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents_master (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL
        )
    ''')
    
    # 2. Student Progress Table (Using a mock user_id=1 for this prototype)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_progress (
            user_id INTEGER NOT NULL,
            document_id INTEGER NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('missing', 'in_progress', 'ready')),
            PRIMARY KEY (user_id, document_id),
            FOREIGN KEY (document_id) REFERENCES documents_master(id)
        )
    ''')
    
    # Seed data if master table is brand new
    cursor.execute("SELECT COUNT(*) FROM documents_master")
    if cursor.fetchone()[0] == 0:
        vfs_docs = [
            ("Civil Documents", "Valid Passport", "Must have at least 2 blank pages, valid for 90+ days beyond visa expiry."),
            ("Civil Documents", "Passport Photos (x2)", "35mm x 45mm, sharp white background, no edits or smiles."),
            ("Academic Documents", "University Acceptance Letter", "Official enrollment or pre-enrollment document from the university portal."),
            ("Academic Documents", "Degrees & Diplomas", "Original academic certificates, translated or legalized if required."),
            ("Financial & Health", "3-Month Bank Statements", "Personal or sponsor accounts showing sufficient stable funds for the stay."),
            ("Financial & Health", "Travel Medical Insurance", "Minimum €30,000 coverage valid for the entire duration in the Schengen/study area.")
        ]
        cursor.executemany(
            "INSERT INTO documents_master (category, name, description) VALUES (?, ?, ?)", 
            vfs_docs
        )
        
        # Initialize everything as 'missing' for our default user
        cursor.execute("SELECT id FROM documents_master")
        doc_ids = [row['id'] for row in cursor.fetchall()]
        for d_id in doc_ids:
            cursor.execute(
                "INSERT INTO student_progress (user_id, document_id, status) VALUES (1, ?, 'missing')",
                (d_id,)
            )
            
    conn.commit()
    conn.close()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/checklist', methods=['GET'])
def get_checklist():
    """Retrieves the master checklist combined with the student's personal progress."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Left join ensures we fetch document info and match it to our user's specific progress status
    cursor.execute('''
        SELECT m.id, m.category, m.name, m.description, COALESCE(p.status, 'missing') as status
        FROM documents_master m
        LEFT JOIN student_progress p ON m.id = p.document_id AND p.user_id = 1
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    checklist = [dict(row) for row in rows]
    return jsonify(checklist)

@app.route('/api/update-status', methods=['POST'])
def update_status():
    """Updates the database state when a student changes a file's progress."""
    data = request.json
    doc_id = data.get('document_id')
    new_status = data.get('status')
    
    if not doc_id or new_status not in ['missing', 'in_progress', 'ready']:
        return jsonify({"error": "Invalid payload data"}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Upsert pattern (insert or replace) to modify user progress safely
    cursor.execute('''
        INSERT OR REPLACE INTO student_progress (user_id, document_id, status)
        VALUES (1, ?, ?)
    ''', (doc_id, new_status))
    
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": f"Document {doc_id} updated to {new_status}"})

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)