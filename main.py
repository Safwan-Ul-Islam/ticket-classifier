import os
import re
import json
import sqlite3
import smtplib
import imaplib
import asyncio
import urllib.request
import email as email_lib
from email.mime.text import MIMEText
from email.header import decode_header
from contextlib import contextmanager, asynccontextmanager
from datetime import datetime, timedelta
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
                resolved BOOLEAN DEFAULT FALSE,
                language TEXT DEFAULT 'en',
                sentiment_score INTEGER DEFAULT 5,
                suggested_reply TEXT,
                resolved_at TIMESTAMP
            )
        """)
        # Migrate existing DB if columns don't exist
        for col_def in [
            "ALTER TABLE tickets ADD COLUMN language TEXT DEFAULT 'en'",
            "ALTER TABLE tickets ADD COLUMN sentiment_score INTEGER DEFAULT 5",
            "ALTER TABLE tickets ADD COLUMN suggested_reply TEXT",
            "ALTER TABLE tickets ADD COLUMN resolved_at TIMESTAMP",
        ]:
            try:
                conn.execute(col_def)
            except sqlite3.OperationalError:
                pass


def send_alert_email(ticket_id: int, customer_name: str, category: str, ticket_body: str, agent_summary: str | None, sentiment_score: int = 5):
    sender = os.getenv("ALERT_EMAIL")
    password = os.getenv("ALERT_EMAIL_PASSWORD")
    recipient = os.getenv("ALERT_EMAIL_RECIPIENT", sender)

    if not sender or not password:
        return

    body = f"""HIGH URGENCY TICKET ALERT

Ticket ID  : #{ticket_id}
Customer   : {customer_name}
Category   : {category}
Sentiment  : {sentiment_score}/10

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


def send_slack_notification(ticket_id: int, customer_name: str, category: str, urgency: str, sentiment_score: int, ticket_body: str, should_auto_reply: bool):
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        return

    emoji = "🚨" if urgency == "high" else "📋"
    status = "Auto Replied ✅" if should_auto_reply else "Needs Human ⚠️"
    sentiment_label = "😠 Angry" if sentiment_score <= 3 else "😐 Neutral" if sentiment_score <= 6 else "😊 Happy"

    message = {
        "text": f"{emoji} *Ticket #{ticket_id}* | {category.replace('_', ' ').title()} | {status}",
        "attachments": [{
            "color": "#ef4444" if urgency == "high" else "#6366f1",
            "fields": [
                {"title": "Customer", "value": customer_name, "short": True},
                {"title": "Urgency", "value": urgency.upper(), "short": True},
                {"title": "Sentiment", "value": f"{sentiment_label} ({sentiment_score}/10)", "short": True},
                {"title": "Message", "value": ticket_body[:200] + ("..." if len(ticket_body) > 200 else ""), "short": False},
            ]
        }]
    }

    try:
        data = json.dumps(message).encode()
        req = urllib.request.Request(webhook_url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
        print(f"[SLACK] Notification sent for ticket #{ticket_id}")
    except Exception as e:
        print(f"[SLACK ERROR] {e}")


def send_weekly_summary():
    sender = os.getenv("ALERT_EMAIL")
    password = os.getenv("ALERT_EMAIL_PASSWORD")
    recipient = os.getenv("ALERT_EMAIL_RECIPIENT", sender)

    if not sender or not password:
        return

    with sqlite3.connect(DB_PATH) as conn:
        total = conn.execute("SELECT COUNT(*) FROM tickets WHERE created_at >= DATE('now', '-7 days')").fetchone()[0]
        auto = conn.execute("SELECT COUNT(*) FROM tickets WHERE should_auto_reply = TRUE AND created_at >= DATE('now', '-7 days')").fetchone()[0]
        urgent = conn.execute("SELECT COUNT(*) FROM tickets WHERE urgency = 'high' AND created_at >= DATE('now', '-7 days')").fetchone()[0]
        resolved = conn.execute("SELECT COUNT(*) FROM tickets WHERE resolved = TRUE AND created_at >= DATE('now', '-7 days')").fetchone()[0]
        avg_sentiment = conn.execute("SELECT ROUND(AVG(sentiment_score), 1) FROM tickets WHERE created_at >= DATE('now', '-7 days')").fetchone()[0]
        by_cat = conn.execute("SELECT category, COUNT(*) FROM tickets WHERE created_at >= DATE('now', '-7 days') GROUP BY category ORDER BY 2 DESC").fetchall()

    if total == 0:
        return

    auto_rate = round(auto / total * 100)
    cat_lines = "\n".join([f"  {r[0].replace('_', ' ').title()}: {r[1]}" for r in by_cat])

    body = f"""WEEKLY SUPPORT SUMMARY
{'='*40}
Period: Last 7 days

Total Tickets      : {total}
Auto Replied       : {auto} ({auto_rate}% automation rate)
Needed Human       : {total - auto}
High Urgency       : {urgent}
Resolved           : {resolved}
Avg Sentiment      : {avg_sentiment or 'N/A'} / 10

By Category:
{cat_lines}
{'='*40}
View dashboard: http://127.0.0.1:8000
"""
    msg = MIMEText(body)
    msg["Subject"] = f"Weekly Support Summary — {total} tickets, {auto_rate}% automated"
    msg["From"] = sender
    msg["To"] = recipient

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, recipient, msg.as_string())
        print("[EMAIL] Weekly summary sent")
    except Exception as e:
        print(f"[EMAIL ERROR] Weekly summary: {e}")


def _decode_header(value):
    parts = decode_header(value or "")
    result = ""
    for part, charset in parts:
        if isinstance(part, bytes):
            result += part.decode(charset or "utf-8", errors="replace")
        else:
            result += part
    return result.strip()


def _extract_body(msg):
    text = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                charset = part.get_content_charset() or "utf-8"
                text = part.get_payload(decode=True).decode(charset, errors="replace")
                break
            elif ct == "text/html" and not text:
                charset = part.get_content_charset() or "utf-8"
                html = part.get_payload(decode=True).decode(charset, errors="replace")
                text = re.sub(r"<[^>]+>", " ", html)
    else:
        charset = msg.get_content_charset() or "utf-8"
        text = msg.get_payload(decode=True).decode(charset, errors="replace")
    return text.strip()


def send_auto_reply_email(to_email: str, to_name: str, subject: str, reply_text: str, ticket_id: int):
    sender = os.getenv("ALERT_EMAIL")
    password = os.getenv("ALERT_EMAIL_PASSWORD")
    if not sender or not password:
        return

    reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    body = f"""{reply_text}

---
Ticket #{ticket_id} | HIVE Marketplace Support
support@hivemarketplace.com
"""
    msg = MIMEText(body)
    msg["Subject"] = reply_subject
    msg["From"] = f"HIVE Support <{sender}>"
    msg["To"] = to_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, to_email, msg.as_string())
        print(f"[EMAIL] Auto-reply sent to {to_email} (ticket #{ticket_id})")
    except Exception as e:
        print(f"[EMAIL ERROR] Auto-reply: {e}")


def process_email_inbox():
    imap_user = os.getenv("ALERT_EMAIL")
    imap_pass = os.getenv("ALERT_EMAIL_PASSWORD")
    if not imap_user or not imap_pass:
        return

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(imap_user, imap_pass)
        mail.select("inbox")

        status, messages = mail.search(None, "UNSEEN")
        if status != "OK" or not messages[0].strip():
            mail.logout()
            return

        email_ids = messages[0].split()
        print(f"[EMAIL POLL] {len(email_ids)} new email(s)")

        for eid in email_ids:
            mail.store(eid, "+FLAGS", "\\Seen")
            status, data = mail.fetch(eid, "(RFC822)")
            if status != "OK":
                continue

            msg = email_lib.message_from_bytes(data[0][1])
            from_raw = _decode_header(msg.get("From", ""))
            subject = _decode_header(msg.get("Subject", "No Subject"))
            body = _extract_body(msg)

            if not body or len(body.strip()) < 10:
                continue

            match = re.match(r'"?([^"<]+?)"?\s*<([^>]+)>', from_raw)
            if match:
                customer_name = match.group(1).strip()
                customer_email = match.group(2).strip()
            else:
                customer_email = from_raw.strip()
                customer_name = customer_email.split("@")[0].replace(".", " ").title()

            # skip self-sent emails (alerts, summaries)
            if customer_email.lower() == imap_user.lower():
                continue

            print(f"[EMAIL POLL] Processing from {customer_name} <{customer_email}>")

            ticket_body = f"Subject: {subject}\n\n{body}"[:2000]
            prompt = build_classify_prompt(
                ticket_body=ticket_body,
                customer_name=customer_name,
                product_name="HIVE Marketplace",
                faq_context=SAMPLE_FAQ
            )

            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=700
            )
            result = json.loads(response.choices[0].message.content)

            confidence = int(result.get("confidence", 0))
            sentiment_score = int(result.get("sentiment_score", 5))
            should_auto_reply = confidence >= 70
            urgency = result.get("urgency", "normal")

            with get_db() as conn:
                cursor = conn.execute("""
                    INSERT INTO tickets
                        (customer_name, customer_email, product_name, ticket_body,
                         category, confidence, urgency, should_auto_reply, auto_reply,
                         agent_summary, language, sentiment_score, suggested_reply)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    customer_name, customer_email, "HIVE Marketplace", ticket_body,
                    result.get("category", "general_inquiry"), confidence, urgency,
                    should_auto_reply, result.get("auto_reply"), result.get("agent_summary"),
                    result.get("language", "en"), sentiment_score, result.get("suggested_reply"),
                ))
                conn.commit()
                ticket_id = cursor.lastrowid

            if should_auto_reply and result.get("auto_reply"):
                send_auto_reply_email(customer_email, customer_name, subject, result["auto_reply"], ticket_id)

            if urgency == "high" or sentiment_score <= 3:
                send_alert_email(ticket_id, customer_name, result.get("category", "general_inquiry"), ticket_body, result.get("agent_summary"), sentiment_score)

            send_slack_notification(ticket_id, customer_name, result.get("category", "general_inquiry"), urgency, sentiment_score, ticket_body, should_auto_reply)

        mail.logout()
    except Exception as e:
        print(f"[EMAIL POLL ERROR] {e}")


async def email_polling_scheduler():
    await asyncio.sleep(10)  # short delay on startup
    while True:
        try:
            process_email_inbox()
        except Exception as e:
            print(f"[EMAIL POLL SCHEDULER ERROR] {e}")
        await asyncio.sleep(120)  # poll every 2 minutes


async def weekly_scheduler():
    while True:
        now = datetime.now()
        days_until_monday = (7 - now.weekday()) % 7 or 7
        next_run = (now + timedelta(days=days_until_monday)).replace(hour=9, minute=0, second=0, microsecond=0)
        await asyncio.sleep((next_run - now).total_seconds())
        send_weekly_summary()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    asyncio.create_task(weekly_scheduler())
    asyncio.create_task(email_polling_scheduler())
    yield


app = FastAPI(title="Ticket Classifier API", version="2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


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
    language: str
    sentiment_score: int
    auto_reply: str | None
    suggested_reply: str | None
    agent_summary: str | None
    urgency: str
    should_auto_reply: bool


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.get("/submit")
def submit_form():
    return FileResponse("static/submit.html")


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
            max_tokens=700
        )
        raw = response.choices[0].message.content
        result = json.loads(raw)
        confidence = int(result.get("confidence", 0))
        sentiment_score = int(result.get("sentiment_score", 5))
        should_auto_reply = confidence >= 70

        with get_db() as conn:
            cursor = conn.execute("""
                INSERT INTO tickets
                    (customer_name, customer_email, product_name, ticket_body,
                     category, confidence, urgency, should_auto_reply, auto_reply,
                     agent_summary, language, sentiment_score, suggested_reply)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                result.get("language", "en"),
                sentiment_score,
                result.get("suggested_reply"),
            ))
            conn.commit()
            ticket_id = cursor.lastrowid

        urgency = result.get("urgency", "normal")
        if urgency == "high" or sentiment_score <= 3:
            send_alert_email(
                ticket_id=ticket_id,
                customer_name=request.customer_name,
                category=result.get("category", "general_inquiry"),
                ticket_body=request.ticket_body,
                agent_summary=result.get("agent_summary"),
                sentiment_score=sentiment_score,
            )

        send_slack_notification(
            ticket_id=ticket_id,
            customer_name=request.customer_name,
            category=result.get("category", "general_inquiry"),
            urgency=urgency,
            sentiment_score=sentiment_score,
            ticket_body=request.ticket_body,
            should_auto_reply=should_auto_reply,
        )

        return TicketResponse(
            id=ticket_id,
            category=result.get("category", "general_inquiry"),
            confidence=confidence,
            language=result.get("language", "en"),
            sentiment_score=sentiment_score,
            auto_reply=result.get("auto_reply"),
            suggested_reply=result.get("suggested_reply"),
            agent_summary=result.get("agent_summary"),
            urgency=urgency,
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
        conn.execute(
            "UPDATE tickets SET resolved = TRUE, resolved_at = CURRENT_TIMESTAMP WHERE id = ?",
            (ticket_id,)
        )
        conn.commit()
    return {"message": f"Ticket {ticket_id} marked as resolved"}


@app.post("/send-weekly-summary")
def trigger_weekly_summary():
    send_weekly_summary()
    return {"message": "Weekly summary sent"}


@app.get("/analytics")
def get_analytics():
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
        auto_replied = conn.execute("SELECT COUNT(*) FROM tickets WHERE should_auto_reply = TRUE").fetchone()[0]
        high_urgency = conn.execute("SELECT COUNT(*) FROM tickets WHERE urgency = 'high'").fetchone()[0]
        resolved = conn.execute("SELECT COUNT(*) FROM tickets WHERE resolved = TRUE").fetchone()[0]
        avg_sentiment = conn.execute("SELECT ROUND(AVG(sentiment_score), 1) FROM tickets").fetchone()[0]

        avg_resolution_hours = conn.execute("""
            SELECT ROUND(AVG((JULIANDAY(resolved_at) - JULIANDAY(created_at)) * 24), 1)
            FROM tickets WHERE resolved = TRUE AND resolved_at IS NOT NULL
        """).fetchone()[0]

        sentiment_breakdown = conn.execute("""
            SELECT
                SUM(CASE WHEN sentiment_score BETWEEN 1 AND 3 THEN 1 ELSE 0 END),
                SUM(CASE WHEN sentiment_score BETWEEN 4 AND 6 THEN 1 ELSE 0 END),
                SUM(CASE WHEN sentiment_score BETWEEN 7 AND 10 THEN 1 ELSE 0 END)
            FROM tickets
        """).fetchone()

        by_category = conn.execute("SELECT category, COUNT(*) FROM tickets GROUP BY category").fetchall()
        by_urgency = conn.execute("SELECT urgency, COUNT(*) FROM tickets GROUP BY urgency").fetchall()

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
        "avg_sentiment": avg_sentiment or 0,
        "avg_resolution_hours": avg_resolution_hours,
        "sentiment_breakdown": {
            "negative": sentiment_breakdown[0] or 0,
            "neutral": sentiment_breakdown[1] or 0,
            "positive": sentiment_breakdown[2] or 0,
        },
        "by_category": [{"category": r[0], "count": r[1]} for r in by_category],
        "by_urgency": [{"urgency": r[0], "count": r[1]} for r in by_urgency],
        "daily": [{"day": r[0], "count": r[1]} for r in reversed(daily)],
    }
