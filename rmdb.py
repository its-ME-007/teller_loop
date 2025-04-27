import sqlite3

DATABASE = 'lan_monitoring.db'

def clear_db_contents():
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()

    # Get a list of all user-created tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = cur.fetchall()

    # Clear contents of all user-created tables
    for table in tables:
        cur.execute(f"DELETE FROM {table[0]}")
        conn.commit()  # Commit after each table to ensure changes are saved

    conn.close()

clear_db_contents()
