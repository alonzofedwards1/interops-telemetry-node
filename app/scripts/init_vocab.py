import sqlite3

DB_PATH = r"C:\Users\alonz\Documents\interops-telemetry-api\app\db\telemetry.db"


# ============================
# Connection Helper
# ============================

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ============================
# Table Creators
# ============================

def create_event_types(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS event_types (
            code TEXT PRIMARY KEY,
            description TEXT NOT NULL
        )
    """)


def create_event_statuses(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS event_statuses (
            code TEXT PRIMARY KEY,
            description TEXT NOT NULL
        )
    """)


def create_environments(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS environments (
            code TEXT PRIMARY KEY
        )
    """)


def create_protocol_standards(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS protocol_standards (
            code TEXT PRIMARY KEY
        )
    """)


def create_event_subtypes(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS event_subtypes (
            code TEXT PRIMARY KEY,
            description TEXT,
            event_type TEXT
        )
    """)


# ============================
# Seed Data
# ============================

EVENT_TYPES = [
    ("PD_REQUEST", "Patient Discovery request"),
    ("PD_RESPONSE", "Patient Discovery response"),
    ("DQ_REQUEST", "Document Query request"),
    ("DQ_RESPONSE", "Document Query response"),
    ("RD_REQUEST", "Document Retrieve request"),
    ("RD_RESPONSE", "Document Retrieve response"),
    ("SYSTEM", "System-level event"),
    ("SECURITY", "Security-related event"),
    ("VALIDATION", "Validation/parsing event"),
]

EVENT_STATUSES = [
    ("SUCCESS", "Operation completed successfully"),
    ("FAILURE", "Operation failed"),
    ("WARNING", "Completed with warnings"),
    ("UNKNOWN", "Outcome could not be determined"),
]

ENVIRONMENTS = [
    ("LOCAL",),
    ("DEV",),
    ("TEST",),
    ("STAGE",),
    ("PROD",),
]

PROTOCOL_STANDARDS = [
    ("IHE",),
    ("FHIR",),
    ("HL7V2",),
    ("SOAP",),
    ("REST",),
]

EVENT_SUBTYPES = [
    ("INGEST_RECEIVED", "Telemetry received", None),
    ("UPSERT_COMMITTED", "Record persisted", None),
    ("RESPONSE_PARSED", "Response parsed successfully", None),
    ("VALIDATION_FAILED", "Validation failure", "VALIDATION"),
    ("TIMEOUT", "Timeout occurred", None),
]


# ============================
# Seed Helper
# ============================

def seed_table(conn, table_name, rows):
    if not rows:
        return

    placeholders = ",".join("?" * len(rows[0]))
    conn.executemany(
        f"INSERT OR IGNORE INTO {table_name} VALUES ({placeholders})",
        rows
    )


# ============================
# Init Orchestrator
# ============================

def init_vocab():
    conn = get_conn()

    # Create tables
    create_event_types(conn)
    create_event_statuses(conn)
    create_environments(conn)
    create_protocol_standards(conn)
    create_event_subtypes(conn)

    # Seed tables
    seed_table(conn, "event_types", EVENT_TYPES)
    seed_table(conn, "event_statuses", EVENT_STATUSES)
    seed_table(conn, "environments", ENVIRONMENTS)
    seed_table(conn, "protocol_standards", PROTOCOL_STANDARDS)
    seed_table(conn, "event_subtypes", EVENT_SUBTYPES)

    conn.commit()
    conn.close()


# ============================
# Validation Helper (Runtime)
# ============================

def is_valid_code(conn, table_name, code):
    if code is None:
        return True

    cur = conn.execute(
        f"SELECT 1 FROM {table_name} WHERE code = ?",
        (code,)
    )
    return cur.fetchone() is not None


# ============================
# Main Entry
# ============================

if __name__ == "__main__":
    init_vocab()
    print("✅ Vocabulary tables created and seeded successfully")
