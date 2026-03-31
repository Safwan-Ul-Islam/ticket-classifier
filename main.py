import os
import json
import sqlite3
import smtplib
from email.mime.text import MIMEText
from contextlib import contextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator
from groq import Groq
from dotenv import load_dotenv
from prompts import build_classify_prompt
from faq_data import SAMPLE_FAQ

load_dotenv()

app = FastAPI(title="Ticket Classifier API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

DB_PATH = "tickets.db"


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                customer_name TEXT,
                customer_email TEXT,
                product_name TEXT,
                ticket_body TEXT,
                category TEXT,
                confidence INTEGER,
                urgency TEXT,
                should_auto_reply BOOLEAN,
                auto_reply TEXT,
                agent_summary TEXT,
                resolved BOOLEAN DEFAULT FALSE
            )
        """)


init_db()


def send_alert_email(ticket_id: int, customer_name: str, category: str, ticket_body: str, agent_summary: str | None):
    sender = os.getenv("ALERT_EMAIL")
    password = os.getenv("ALERT_EMAIL_PASSWORD")
    recipient = os.getenv("ALERT_EMAIL_RECIPIENT", sender)

    if not sender or not password:
        return

    body = f"""HIGH URGENCY TICKET ALERT

Ticket ID : #{ticket_id}
Customer  : {customer_name}
Category  : {category}

Message:
{ticket_body}

Agent Summary:
{agent_summary or "N/A"}

Review it at: http://127.0.0.1:8000
"""
    msg = MIMEText(body)
    msg["Subject"] = f"[URGENT] New ticket #{ticket_id} from {customer_name}"
    msg["From"] = sender
    msg["To"] = recipient

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, recipient, msg.as_string())
        print(f"[EMAIL] Alert sent to {recipient}")
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


class TicketRequest(BaseModel):
    ticket_body: str
    customer_name: str = "Customer"
    customer_email: str = ""
    product_name: str = "our product"
    faq_context: str = SAMPLE_FAQ

    @field_validator("ticket_body")
    @classmethod
    def ticket_must_have_content(cls, v):
        if len(v.strip()) < 10:
            raise ValueError("ticket_body must be at least 10 characters")
        if len(v) > 2000:
            raise ValueError("ticket_body must be under 2000 characters")
        return v.strip()


class TicketResponse(BaseModel):
    id: int
    category: str
    confidence: int
    auto_reply: str | None
    agent_summary: str | None
    urgency: str
    should_auto_reply: bool


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.get("/health")
def health_check():
    return {"status": "running", "message": "Ticket Classifier API is live"}


@app.post("/classify", response_model=TicketResponse)
async def classify_ticket(request: TicketRequest):
    prompt = build_classify_prompt(
        ticket_body=request.ticket_body,
        customer_name=request.customer_name,
        product_name=request.product_name,
        faq_context=request.faq_context
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=600
        )
        raw = response.choices[0].message.content
        result = json.loads(raw)
        confidence = int(result.get("confidence", 0))
        should_auto_reply = confidence >= 85

        with get_db() as conn:
            cursor = conn.execute("""
                INSERT INTO tickets
                    (customer_name, customer_email, product_name, ticket_body,
                     category, confidence, urgency, should_auto_reply, auto_reply, agent_summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                request.customer_name,
                request.customer_email,
                request.product_name,
                request.ticket_body,
                result.get("category", "general_inquiry"),
                confidence,
                result.get("urgency", "normal"),
                should_auto_reply,
                result.get("auto_reply"),
                result.get("agent_summary"),
            ))
            conn.commit()
            ticket_id = cursor.lastrowid

        if result.get("urgency") == "high":
            send_alert_email(
                ticket_id=ticket_id,
                customer_name=request.customer_name,
                category=result.get("category", "general_inquiry"),
                ticket_body=request.ticket_body,
                agent_summary=result.get("agent_summary"),
            )

        return TicketResponse(
            id=ticket_id,
            category=result.get("category", "general_inquiry"),
            confidence=confidence,
            auto_reply=result.get("auto_reply"),
            agent_summary=result.get("agent_summary"),
            urgency=result.get("urgency", "normal"),
            should_auto_reply=should_auto_reply
        )

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"AI returned invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tickets")
def get_all_tickets():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM tickets ORDER BY created_at DESC").fetchall()
    return [dict(row) for row in rows]


@app.get("/tickets/inbox")
def get_inbox():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM tickets
            WHERE should_auto_reply = FALSE AND resolved = FALSE
            ORDER BY urgency DESC, created_at ASC
        """).fetchall()
    return [dict(row) for row in rows]


@app.patch("/tickets/{ticket_id}/resolve")
def resolve_ticket(ticket_id: int):
    with get_db() as conn:
        conn.execute("UPDATE tickets SET resolved = TRUE WHERE id = ?", (ticket_id,))
        conn.commit()
    return {"message": f"Ticket {ticket_id} marked as resolved"}


@app.get("/analytics")
def get_analytics():
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
        auto_replied = conn.execute("SELECT COUNT(*) FROM tickets WHERE should_auto_reply = TRUE").fetchone()[0]
        high_urgency = conn.execute("SELECT COUNT(*) FROM tickets WHERE urgency = 'high'").fetchone()[0]
        resolved = conn.execute("SELECT COUNT(*) FROM tickets WHERE resolved = TRUE").fetchone()[0]

        by_category = conn.execute("""
            SELECT category, COUNT(*) as count FROM tickets GROUP BY category
        """).fetchall()

        by_urgency = conn.execute("""
            SELECT urgency, COUNT(*) as count FROM tickets GROUP BY urgency
        """).fetchall()

        daily = conn.execute("""
            SELECT DATE(created_at) as day, COUNT(*) as count
            FROM tickets GROUP BY day ORDER BY day DESC LIMIT 7
        """).fetchall()

    return {
        "total": total,
        "auto_replied": auto_replied,
        "needs_human": total - auto_replied,
        "high_urgency": high_urgency,
        "resolved": resolved,
        "by_category": [{"category": r[0], "count": r[1]} for r in by_category],
        "by_urgency": [{"urgency": r[0], "count": r[1]} for r in by_urgency],
        "daily": [{"day": r[0], "count": r[1]} for r in reversed(daily)],
    }
