#!/usr/bin/env python3
"""
speaker-proxy — Thin auth proxy between Speaker clients and ClickHouse.
Handles API key auth, signup, query forwarding, usage logging.
"""

import hashlib
import json
import logging
import os
import re
import secrets
import sqlite3
import time
from collections import defaultdict
from datetime import datetime

import httpx
import sqlglot
from sqlglot import exp
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse, JSONResponse

logger = logging.getLogger("speaker-proxy")

# --- Config ---
CH_HOST = os.environ.get("CH_HOST", "http://localhost:8123")
CH_USER = os.environ.get("CH_USER", "speaker_reader")
CH_PASS = os.environ["CH_PASS"]  # required — set in systemd unit or .env
DB_PATH = os.environ.get("DB_PATH", "/data/leads-proxy/keys.db")
LOG_PATH = os.environ.get("LOG_PATH", "/data/leads-proxy/queries.log")
MAX_RESULT_ROWS = 100000  # hard cap per query
RATE_LIMIT_PER_SECOND = 20

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

# --- Rate Limiting (in-memory, per-worker) ---
class RateLimiter:
    def __init__(self):
        self.requests = defaultdict(list)  # key -> [timestamps]
    
    def check(self, api_key: str):
        now = time.time()
        
        # Per-second: keep only last 1 second of timestamps
        self.requests[api_key] = [t for t in self.requests[api_key] if now - t < 1.0]
        if len(self.requests[api_key]) >= RATE_LIMIT_PER_SECOND:
            raise HTTPException(status_code=429, detail=f"Rate limit: max {RATE_LIMIT_PER_SECOND} queries/second. Fire in parallel, not sequential.")
        
        # Record
        self.requests[api_key].append(now)

rate_limiter = RateLimiter()

# --- Database ---
def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            api_key TEXT UNIQUE NOT NULL,
            plan TEXT DEFAULT 'free',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            active INTEGER DEFAULT 1
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS invite_codes (
            code TEXT PRIMARY KEY,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            used_by TEXT DEFAULT NULL,
            used_at TEXT DEFAULT NULL
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_key TEXT NOT NULL,
            query TEXT NOT NULL,
            rows_returned INTEGER DEFAULT 0,
            duration_ms INTEGER DEFAULT 0,
            ts TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()
    return db

def get_db():
    return sqlite3.connect(DB_PATH)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def generate_key() -> str:
    return "sk-" + secrets.token_hex(24)

# --- Auth ---
def validate_key(api_key: str) -> dict:
    db = get_db()
    row = db.execute(
        "SELECT email, plan, active FROM users WHERE api_key = ?", (api_key,)
    ).fetchone()
    db.close()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid API key")
    if not row[2]:
        raise HTTPException(status_code=403, detail="Account disabled")
    return {"email": row[0], "plan": row[1]}

# --- Query enforcement (AST parser + string fallback) ---

ALLOWED_DATABASES = {"people", "companies", "web"}

BLOCKED_FUNCTIONS = {
    # Introspection / server fingerprinting
    "getsetting", "getserverport", "tcpport", "version", "hostname", "fqdn",
    "uptime", "timezone", "currentuser", "currentdatabase",
    "currentprofiles", "currentroles", "enabledroles", "defaultroles",
    "buildid", "connection_id", "queryid", "currentqueryid", "initialqueryid",
    # Dangerous table functions
    "merge", "remote", "file", "s3", "url", "input", "cluster",
    "generaterandom", "viewifpermitted", "numbers",
}

def _validate_sql_parser(sql: str):
    """Validate SQL using AST parser. Raises HTTPException if blocked."""
    # Parse — rejects SETTINGS, INTO OUTFILE, malformed SQL
    try:
        stmts = sqlglot.parse(sql, dialect="clickhouse")
    except sqlglot.errors.ParseError:
        raise HTTPException(status_code=400, detail="Query syntax error. Check your SQL.")
    
    if len(stmts) != 1 or stmts[0] is None:
        raise HTTPException(status_code=400, detail="Only single statements allowed.")
    
    parsed = stmts[0]
    
    # Must be SELECT, UNION, or DESCRIBE/SHOW
    if not isinstance(parsed, (exp.Select, exp.Union, exp.Describe, exp.Show)):
        raise HTTPException(status_code=400, detail="Only SELECT and DESCRIBE queries allowed.")
    
    # Check all referenced tables — must use database.table format
    for table in parsed.find_all(exp.Table):
        if not table.name:
            continue
        db = table.db or ""
        if not db:
            raise HTTPException(status_code=400, detail=f"Use database.table format: people.main, companies.main, etc.")
        if db.lower() not in ALLOWED_DATABASES:
            raise HTTPException(status_code=403, detail=f"Access denied: database '{db}' not available.")
    
    # Check all function calls (Anonymous = unknown to sqlglot)
    for func in parsed.find_all(exp.Anonymous):
        if func.name.lower() in BLOCKED_FUNCTIONS:
            raise HTTPException(status_code=403, detail="Access denied: restricted function.")
    
    # Block built-in function types that sqlglot recognizes (not caught as Anonymous)
    BLOCKED_FUNC_TYPES = (
        exp.CurrentDatabase, exp.CurrentUser, exp.CurrentTimestamp,
        exp.CurrentDate, exp.CurrentDatetime, exp.CurrentTime,
        exp.CurrentTimezone, exp.CurrentSchema, exp.CurrentRole,
        exp.Version,
    )
    if parsed.find(*BLOCKED_FUNC_TYPES):
        raise HTTPException(status_code=403, detail="Access denied: restricted function.")

def _validate_sql_string(sql: str):
    """Legacy string-based validation. Used as fallback if parser hits unexpected error."""
    sql_upper = sql.strip().upper()
    sql_norm = re.sub(r'/\*.*?\*/', ' ', sql_upper)
    sql_norm = re.sub(r'--[^\n]*', ' ', sql_norm)
    sql_norm = sql_norm.replace("`", "").replace('"', '')
    sql_norm = re.sub(r'\s+', ' ', sql_norm)
    sql_check = re.sub(r"'[^']*'", "''", sql_norm)
    
    if not (sql_upper.startswith("SELECT") or sql_upper.startswith("DESCRIBE") or sql_upper.startswith("SHOW")):
        raise HTTPException(status_code=400, detail="Only SELECT and DESCRIBE queries allowed")
    for kw in ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "TRUNCATE", "CREATE"]:
        if kw in sql_check:
            raise HTTPException(status_code=400, detail=f"Forbidden: {kw} not allowed")
    if re.search(r'\bINTO\s+OUTFILE\b', sql_check):
        raise HTTPException(status_code=400, detail="INTO OUTFILE is not allowed")
    # Block access to internal databases
    for blocked_db in ["SPEAKER_DATASOURCE", "B2B", "SYSTEM", "INFORMATION_SCHEMA", "WEBSEARCH"]:
        if blocked_db + "." in sql_check:
            raise HTTPException(status_code=403, detail="Access denied: restricted database")
    if "SETTINGS" in sql_check:
        raise HTTPException(status_code=400, detail="SETTINGS not allowed")
    blocked_funcs_legacy = [
        "GETSETTING(", "GETSERVERPORT(", "TCPPORT(", "VERSION(", "HOSTNAME(", "FQDN(",
        "UPTIME(", "TIMEZONE(", "CURRENTUSER(", "CURRENTDATABASE(", "CURRENTPROFILES(",
        "CURRENTROLES(", "ENABLEDROLES(", "DEFAULTROLES(", "BUILDID(", "CONNECTION_ID(",
        "QUERYID(", "CURRENTQUERYID(", "INITIALQUERYID(", "FILE(", "URL(", "S3(", "REMOTE(",
        "INPUT(", "CLUSTER(", "MERGE(", "GENERATERANDOM(", "VALUES(", "VIEWIFPERMITTED(",
        "NUMBERS(",
    ]
    for func in blocked_funcs_legacy:
        if func in sql_check.replace(" ", ""):
            raise HTTPException(status_code=400, detail="Access denied: restricted function")
    if ";" in sql.strip().rstrip(";"):
        raise HTTPException(status_code=400, detail="Only single statements allowed")

def _cap_limit(sql: str) -> str:
    """Cap LIMIT to MAX_RESULT_ROWS, inject LIMIT if missing."""
    sql_upper = sql.strip().upper()
    
    limit_offset_match = re.search(r'\bLIMIT\s+(\d+)\s*,\s*(\d+)', sql_upper)
    limit_match = re.search(r'\bLIMIT\s+(\d+)(?!\s*,)', sql_upper)
    
    if limit_offset_match:
        count = int(limit_offset_match.group(2))
        if count > MAX_RESULT_ROWS:
            sql = sql[:limit_offset_match.start(2)] + str(MAX_RESULT_ROWS) + sql[limit_offset_match.end(2):]
    elif limit_match:
        user_limit = int(limit_match.group(1))
        if user_limit > MAX_RESULT_ROWS:
            sql = sql[:limit_match.start(1)] + str(MAX_RESULT_ROWS) + sql[limit_match.end(1):]
    else:
        sql = sql.rstrip().rstrip(";") + f" LIMIT {MAX_RESULT_ROWS}"
    
    return sql

def enforce_limits(sql: str) -> str:
    """Validate SQL security and cap LIMIT."""
    sql_stripped = sql.strip()
    sql_upper = sql_stripped.upper()
    
    # DESCRIBE/SHOW COLUMNS — allow if database is in allowed list
    if sql_upper.startswith("DESCRIBE ") or sql_upper.startswith("DESC "):
        table_ref = sql_stripped.split(None, 1)[1].strip().rstrip(";")
        parts = table_ref.split(".")
        if len(parts) != 2 or parts[0].lower() not in ALLOWED_DATABASES:
            raise HTTPException(status_code=400, detail="Use database.table format: people.main, companies.main, etc.")
        return sql_stripped
    
    # Primary: AST parser
    try:
        _validate_sql_parser(sql)
    except HTTPException:
        raise  # parser caught something — block it
    except Exception as e:
        # Parser hit unexpected error — fall back to string filter
        logger.warning(f"SQL parser unexpected error, falling back to string filter: {e}")
        _validate_sql_string(sql)
    
    return _cap_limit(sql)

# --- Log ---
def log_query(api_key: str, sql: str, rows: int, duration_ms: int):
    try:
        db = get_db()
        db.execute(
            "INSERT INTO usage (api_key, query, rows_returned, duration_ms) VALUES (?, ?, ?, ?)",
            (api_key, sql[:2000], rows, duration_ms),
        )
        db.commit()
        db.close()
    except Exception:
        pass  # don't break queries if logging fails

# --- Routes ---
@app.on_event("startup")
def startup():
    init_db()

@app.post("/signup")
async def signup(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    email = body.get("email", "") if isinstance(body.get("email"), str) else ""
    invite_code = body.get("invite_code", "") if isinstance(body.get("invite_code"), str) else ""
    email = email.strip().lower()
    invite_code = invite_code.strip()
    
    if not email or not invite_code:
        raise HTTPException(status_code=400, detail="Email and invite code required")
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        raise HTTPException(status_code=400, detail="Invalid email address")
    
    # Validate invite code
    db = get_db()
    code_row = db.execute(
        "SELECT code FROM invite_codes WHERE code = ? AND used_by IS NULL", (invite_code,)
    ).fetchone()
    if not code_row:
        db.close()
        raise HTTPException(status_code=403, detail="Invalid or already used invite code")
    
    # Create account (instantly active)
    api_key = generate_key()
    try:
        db.execute(
            "INSERT INTO users (email, password_hash, api_key, active) VALUES (?, ?, ?, 1)",
            (email, "invite:" + invite_code, api_key),
        )
        # Burn the invite code
        db.execute(
            "UPDATE invite_codes SET used_by = ?, used_at = CURRENT_TIMESTAMP WHERE code = ?",
            (email, invite_code),
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.close()
        raise HTTPException(status_code=409, detail="Email already registered")
    db.close()
    
    # Notify on signup
    try:
        # Mask email: show first 2 chars + domain first 2 chars
        parts = email.split("@")
        masked = parts[0][:2] + "***@" + parts[1][:2] + "***"
        httpx.post(NTFY_TOPIC, content=f"New signup: {masked}")
    except Exception:
        pass

    return {"status": "active", "email": email, "api_key": api_key}

@app.post("/login")
async def login(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    email = body.get("email", "") if isinstance(body.get("email"), str) else ""
    password = body.get("password", "") if isinstance(body.get("password"), str) else ""
    email = email.strip().lower()
    
    db = get_db()
    row = db.execute(
        "SELECT api_key, password_hash, active FROM users WHERE email = ?", (email,)
    ).fetchone()
    db.close()
    
    if not row or row[1] != hash_password(password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not row[2]:
        raise HTTPException(status_code=403, detail="Account disabled")
    
    return {"api_key": row[0], "email": email}

@app.post("/query")
async def query(request: Request, x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key. Run 'speaker login' first.")
    
    user = validate_key(x_api_key)
    rate_limiter.check(x_api_key)
    
    body = await request.body()
    sql = body.decode("utf-8").strip()
    if not sql:
        raise HTTPException(status_code=400, detail="Empty query")
    
    sql = enforce_limits(sql)
    
    # Forward to ClickHouse
    start = time.time()
    try:
        async with httpx.AsyncClient(verify=False) as client:
            resp = await client.post(
                f"{CH_HOST}/",
                auth=(CH_USER, CH_PASS),
                content=f"{sql} FORMAT JSONEachRow",
                timeout=60.0,
            )
    except Exception as e:
        raise HTTPException(status_code=502, detail="Database unavailable")
    
    duration_ms = int((time.time() - start) * 1000)
    
    if resp.status_code != 200:
        # Return generic error messages — log full details server-side
        raw_error = resp.text[:1000]
        log_query(x_api_key, f"ERROR: {sql}", 0, duration_ms)
        
        # Map ClickHouse error codes to generic messages
        if "SYNTAX_ERROR" in raw_error:
            detail = "Query syntax error. Check your SQL."
        elif "TOO_MANY_ROWS" in raw_error or "TOO_MANY_BYTES" in raw_error:
            detail = "Query exceeds resource limits. Try a narrower filter or smaller table."
        elif "ACCESS_DENIED" in raw_error or "Not enough privileges" in raw_error:
            detail = "Access denied."
        elif "INTO_OUTFILE_NOT_ALLOWED" in raw_error:
            detail = "INTO OUTFILE is not allowed."
        elif "TIMEOUT_EXCEEDED" in raw_error:
            detail = "Query timed out. Try a simpler query."
        else:
            detail = "Query failed."
        
        raise HTTPException(status_code=400, detail=detail)
    
    # Count rows
    result = resp.text.strip()
    rows = len(result.split("\n")) if result else 0
    
    log_query(x_api_key, sql, rows, duration_ms)
    
    return PlainTextResponse(result, media_type="application/x-ndjson")

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")  # set in .env
ADMIN_KEY = os.environ["ADMIN_KEY"]  # required — set in systemd unit or .env

@app.post("/status")
async def status(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    email = body.get("email", "") if isinstance(body.get("email"), str) else ""
    email = email.strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email required")
    
    db = get_db()
    row = db.execute(
        "SELECT active FROM users WHERE email = ?", (email,)
    ).fetchone()
    db.close()
    
    # Generic response for unknown emails (prevents user enumeration)
    if not row:
        return {"status": "unknown"}
    
    return {"status": "approved" if row[0] else "pending"}

@app.get("/health")
async def health():
    return {"status": "ok", "people": "818M", "companies": "3.7M", "tables": 10, "version": "3.0.0"}

@app.get("/admin/pending")
async def admin_pending(x_admin_key: str = Header(None)):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    db = get_db()
    rows = db.execute(
        "SELECT id, email, created_at FROM users WHERE active = 0 ORDER BY created_at DESC"
    ).fetchall()
    db.close()
    return [{"id": r[0], "email": r[1], "created_at": r[2]} for r in rows]

@app.post("/admin/approve/{user_id}")
async def admin_approve(user_id: int, x_admin_key: str = Header(None)):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    db = get_db()
    row = db.execute("SELECT email, api_key FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        db.close()
        raise HTTPException(status_code=404, detail="User not found")
    db.execute("UPDATE users SET active = 1 WHERE id = ?", (user_id,))
    db.commit()
    db.close()
    return {"approved": True, "email": row[0], "api_key": row[1]}

@app.post("/admin/reject/{user_id}")
async def admin_reject(user_id: int, x_admin_key: str = Header(None)):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    db = get_db()
    db.execute("DELETE FROM users WHERE id = ? AND active = 0", (user_id,))
    db.commit()
    db.close()
    return {"rejected": True}

@app.get("/admin/users")
async def admin_users(x_admin_key: str = Header(None)):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    db = get_db()
    rows = db.execute(
        """SELECT u.id, u.email, u.active, u.created_at,
           COUNT(usage.id) as queries, COALESCE(SUM(usage.rows_returned), 0) as total_rows,
           MAX(usage.ts) as last_query
           FROM users u LEFT JOIN usage ON u.api_key = usage.api_key
           GROUP BY u.id ORDER BY u.created_at DESC"""
    ).fetchall()
    db.close()
    return [{"id": r[0], "email": r[1], "active": bool(r[2]), "created_at": r[3],
             "queries": r[4], "total_rows": r[5], "last_query": r[6]} for r in rows]

@app.post("/admin/invite")
async def admin_create_invite(x_admin_key: str = Header(None)):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    code = "INV-" + secrets.token_hex(6)
    db = get_db()
    db.execute("INSERT INTO invite_codes (code) VALUES (?)", (code,))
    db.commit()
    db.close()
    return {"invite_code": code}

@app.get("/admin/invites")
async def admin_list_invites(x_admin_key: str = Header(None)):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    db = get_db()
    rows = db.execute(
        "SELECT code, created_at, used_by, used_at FROM invite_codes ORDER BY created_at DESC"
    ).fetchall()
    db.close()
    return [{"code": r[0], "created_at": r[1], "used_by": r[2], "used_at": r[3]} for r in rows]

@app.get("/schema")
async def schema(x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    validate_key(x_api_key)
    
    return {
        "mesh": {
            "people.main":       {"rows": "818M", "description": "Identity, role, skills, education, scores"},
            "people.career":     {"rows": "974M", "description": "Full role history"},
            "people.education":  {"rows": "333M", "description": "Schools, degrees, fields of study"},
            "people.contact":    {"rows": "863M", "description": "LinkedIn, email, Twitter, GitHub, website"},
            "people.repos":      {"rows": "40M",  "description": "GitHub repositories"},
            "companies.main":    {"rows": "3.7M", "description": "AI-synthesized company profiles"},
            "companies.jobs":    {"rows": "755K", "description": "Active job postings"},
            "companies.news":    {"rows": "19M",  "description": "News articles"},
            "web.links":         {"rows": "56M",  "description": "Domain-to-domain link graph"},
            "web.pages":         {"rows": "1.3B", "description": "Company web pages (always filter by domain)"},
        },
        "notes": "Use DESCRIBE database.table for full column list. Hops not JOINs. Carry IDs between queries.",
    }
