from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

OUTPUT = "TicketAI_Overview.pdf"

# ── Colour palette ──────────────────────────────────────────────────────────
INDIGO   = colors.HexColor("#6366f1")
DARK_BG  = colors.HexColor("#1e293b")
SLATE    = colors.HexColor("#334155")
MUTED    = colors.HexColor("#64748b")
WHITE    = colors.white
GREEN    = colors.HexColor("#10b981")
RED      = colors.HexColor("#ef4444")
YELLOW   = colors.HexColor("#f59e0b")
TEAL     = colors.HexColor("#06b6d4")
LIGHT_BG = colors.HexColor("#f8faff")

# ── Styles ───────────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()

def S(name, **kw):
    return ParagraphStyle(name, **kw)

COVER_TITLE = S("cover_title",
    fontSize=32, fontName="Helvetica-Bold",
    textColor=WHITE, alignment=TA_CENTER, leading=38)

COVER_SUB = S("cover_sub",
    fontSize=13, fontName="Helvetica",
    textColor=colors.HexColor("#a5b4fc"), alignment=TA_CENTER, leading=20)

COVER_META = S("cover_meta",
    fontSize=10, fontName="Helvetica",
    textColor=colors.HexColor("#94a3b8"), alignment=TA_CENTER)

SECTION_TITLE = S("section_title",
    fontSize=16, fontName="Helvetica-Bold",
    textColor=INDIGO, spaceBefore=18, spaceAfter=6, leading=20)

BODY = S("body",
    fontSize=10.5, fontName="Helvetica",
    textColor=colors.HexColor("#1e293b"), leading=16,
    spaceAfter=6, alignment=TA_JUSTIFY)

BULLET = S("bullet",
    fontSize=10.5, fontName="Helvetica",
    textColor=colors.HexColor("#1e293b"), leading=16,
    leftIndent=16, spaceAfter=4,
    bulletIndent=6, bulletFontName="Helvetica", bulletFontSize=10)

BOLD_BODY = S("bold_body",
    fontSize=10.5, fontName="Helvetica-Bold",
    textColor=colors.HexColor("#1e293b"), leading=16, spaceAfter=4)

CAPTION = S("caption",
    fontSize=9, fontName="Helvetica",
    textColor=MUTED, leading=13, spaceAfter=2)

HIGHLIGHT = S("highlight",
    fontSize=11, fontName="Helvetica-Bold",
    textColor=INDIGO, leading=16, spaceAfter=4)

# ── Helpers ──────────────────────────────────────────────────────────────────
def cover_block():
    """Dark cover page block."""
    data = [[
        Paragraph("🎫 TicketAI", COVER_TITLE),
    ]]
    t = Table(data, colWidths=[16*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), DARK_BG),
        ("ROUNDEDCORNERS", [10]),
        ("TOPPADDING",   (0,0), (-1,-1), 40),
        ("BOTTOMPADDING",(0,0), (-1,-1), 40),
        ("LEFTPADDING",  (0,0), (-1,-1), 20),
        ("RIGHTPADDING", (0,0), (-1,-1), 20),
    ]))
    return t

def chip(text, bg, fg=WHITE):
    """Coloured pill badge."""
    data = [[Paragraph(
        f'<font name="Helvetica-Bold" size="9" color="#{fg.hexval()[1:]}">{text}</font>',
        ParagraphStyle("chip", alignment=TA_CENTER))]]
    t = Table(data, colWidths=[3.2*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), bg),
        ("ROUNDEDCORNERS",[14]),
        ("TOPPADDING",   (0,0),(-1,-1),4),
        ("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LEFTPADDING",  (0,0),(-1,-1),8),
        ("RIGHTPADDING", (0,0),(-1,-1),8),
    ]))
    return t

def section_rule():
    return HRFlowable(width="100%", thickness=1,
                      color=colors.HexColor("#e0e7ff"), spaceAfter=8)

def info_table(rows, col_widths=None):
    """Generic two-column info table."""
    if col_widths is None:
        col_widths = [5*cm, 11*cm]
    style = TableStyle([
        ("BACKGROUND",    (0,0),(0,-1), LIGHT_BG),
        ("BACKGROUND",    (1,0),(1,-1), WHITE),
        ("FONTNAME",      (0,0),(0,-1), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),(-1,-1), 10),
        ("TEXTCOLOR",     (0,0),(0,-1), SLATE),
        ("TEXTCOLOR",     (1,0),(1,-1), colors.HexColor("#1e293b")),
        ("GRID",          (0,0),(-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ("ROWBACKGROUNDS",(0,0),(-1,-1),
         [colors.HexColor("#f8faff"), WHITE]),
        ("TOPPADDING",    (0,0),(-1,-1), 8),
        ("BOTTOMPADDING", (0,0),(-1,-1), 8),
        ("LEFTPADDING",   (0,0),(-1,-1), 10),
        ("RIGHTPADDING",  (0,0),(-1,-1), 10),
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
    ])
    t = Table([[Paragraph(k, BOLD_BODY), Paragraph(v, BODY)]
               for k,v in rows], colWidths=col_widths)
    t.setStyle(style)
    return t

def feature_table(rows):
    header = [
        Paragraph("Feature", BOLD_BODY),
        Paragraph("What it does", BOLD_BODY),
        Paragraph("Status", BOLD_BODY),
    ]
    data = [header] + [
        [Paragraph(a, BODY), Paragraph(b, BODY), Paragraph(c, BODY)]
        for a,b,c in rows
    ]
    t = Table(data, colWidths=[4.5*cm, 9*cm, 2.5*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0), DARK_BG),
        ("TEXTCOLOR",     (0,0),(-1,0), WHITE),
        ("FONTNAME",      (0,0),(-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),(-1,-1), 9.5),
        ("GRID",          (0,0),(-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),
         [colors.HexColor("#f8faff"), WHITE]),
        ("TOPPADDING",    (0,0),(-1,-1), 7),
        ("BOTTOMPADDING", (0,0),(-1,-1), 7),
        ("LEFTPADDING",   (0,0),(-1,-1), 8),
        ("RIGHTPADDING",  (0,0),(-1,-1), 8),
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
    ]))
    return t

def pricing_table(rows):
    header = [
        Paragraph("Model", BOLD_BODY),
        Paragraph("Price", BOLD_BODY),
        Paragraph("Best for", BOLD_BODY),
    ]
    data = [header] + [
        [Paragraph(a, BODY), Paragraph(b, BODY), Paragraph(c, BODY)]
        for a,b,c in rows
    ]
    t = Table(data, colWidths=[4*cm, 3.5*cm, 8.5*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0), INDIGO),
        ("TEXTCOLOR",     (0,0),(-1,0), WHITE),
        ("FONTNAME",      (0,0),(-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),(-1,-1), 9.5),
        ("GRID",          (0,0),(-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),
         [colors.HexColor("#f8faff"), WHITE]),
        ("TOPPADDING",    (0,0),(-1,-1), 7),
        ("BOTTOMPADDING", (0,0),(-1,-1), 7),
        ("LEFTPADDING",   (0,0),(-1,-1), 8),
        ("RIGHTPADDING",  (0,0),(-1,-1), 8),
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
    ]))
    return t

# ── Build document ────────────────────────────────────────────────────────────
doc = SimpleDocTemplate(
    OUTPUT,
    pagesize=A4,
    rightMargin=2*cm, leftMargin=2*cm,
    topMargin=2*cm,   bottomMargin=2*cm,
)

story = []

# ── COVER ────────────────────────────────────────────────────────────────────
story.append(cover_block())
story.append(Spacer(1, 0.4*cm))
story.append(Paragraph("AI-Powered Customer Support Automation", COVER_SUB))
story.append(Spacer(1, 0.2*cm))
story.append(Paragraph("Product Overview &amp; Technical Brief  •  2026", COVER_META))
story.append(Spacer(1, 0.8*cm))

# ── 1. WHAT IS TICKETAI ──────────────────────────────────────────────────────
story.append(Paragraph("1. What is TicketAI?", SECTION_TITLE))
story.append(section_rule())
story.append(Paragraph(
    "TicketAI is a complete AI-powered customer support automation system. "
    "It reads incoming customer messages, understands what the customer needs, "
    "and either replies automatically or routes the ticket to a human agent — "
    "all within seconds, with zero manual effort.",
    BODY))
story.append(Spacer(1, 0.3*cm))
story.append(Paragraph(
    "Built for freelancers, agencies, and small-to-medium businesses that want "
    "to reduce the time their team spends answering repetitive support emails "
    "without hiring more staff.",
    BODY))
story.append(Spacer(1, 0.4*cm))

# ── 2. HOW IT WORKS ─────────────────────────────────────────────────────────
story.append(Paragraph("2. How It Works — Step by Step", SECTION_TITLE))
story.append(section_rule())

steps = [
    ("Step 1 — Ticket Received",
     "A customer message is submitted via the public form, API call, or "
     "future integrations (Gmail, WhatsApp, etc.)."),
    ("Step 2 — AI Analysis",
     "The AI reads the message and extracts: category, urgency, sentiment score "
     "(1–10), detected language, confidence score, and a suggested reply draft."),
    ("Step 3 — Smart Routing",
     "If confidence ≥ 85%, an auto-reply is sent instantly. "
     "If confidence &lt; 85%, the ticket is routed to the human inbox with a "
     "summary and draft reply for the agent."),
    ("Step 4 — Alerts",
     "High urgency or angry customers (sentiment ≤ 3) trigger an immediate "
     "email alert and Slack notification to the support team."),
    ("Step 5 — Saved &amp; Tracked",
     "Every ticket is saved to the database with full metadata. "
     "Resolution time is tracked automatically."),
    ("Step 6 — Analytics",
     "The live dashboard shows real-time charts: category breakdown, "
     "sentiment trends, urgency distribution, and daily volume."),
    ("Step 7 — Weekly Report",
     "Every Monday at 9am, an automated email summary is sent with the "
     "week's ticket stats, automation rate, and avg sentiment."),
]
story.append(info_table(steps))
story.append(Spacer(1, 0.4*cm))

# ── 3. FEATURES ─────────────────────────────────────────────────────────────
story.append(Paragraph("3. Full Feature List", SECTION_TITLE))
story.append(section_rule())

features = [
    ("AI Classification",     "Classifies tickets into 6 categories: billing, refund, technical, shipping, complaint, general inquiry", "✅ Live"),
    ("Language Detection",    "Detects customer language (English, Urdu, Arabic, French, etc.) and replies in the same language", "✅ Live"),
    ("Sentiment Scoring",     "Scores customer mood 1–10: 😠 Angry / 😐 Neutral / 😊 Happy. Used for urgency detection.", "✅ Live"),
    ("Auto Reply",            "Generates a warm, helpful reply when AI confidence is ≥ 85%. Uses FAQ knowledge base.", "✅ Live"),
    ("Suggested Draft",       "Always generates a reply draft for human agents to edit and send, even for auto-replied tickets.", "✅ Live"),
    ("Human Inbox",           "Tickets needing human review are listed in a dedicated inbox with agent summary and draft.", "✅ Live"),
    ("Email Alerts",          "Sends instant Gmail alert for high-urgency or very angry customers (sentiment ≤ 3).", "✅ Live"),
    ("Slack Notifications",   "Sends Slack message for every ticket — urgent ones shown in red, normal in indigo.", "✅ Live"),
    ("Database Storage",      "All tickets saved to SQLite with full metadata: timestamps, scores, language, resolution time.", "✅ Live"),
    ("Resolution Tracking",   "Records resolved_at timestamp. Analytics shows average resolution time in hours.", "✅ Live"),
    ("Analytics Dashboard",   "Live charts: category doughnut, sentiment breakdown, urgency bar, 7-day line graph.", "✅ Live"),
    ("Public Customer Form",  "Clean white-label form at /submit. Customers see AI reply instantly or get a 24h message.", "✅ Live"),
    ("Weekly Email Summary",  "Auto-sends every Monday at 9am: total tickets, automation rate, category breakdown.", "✅ Live"),
    ("REST API",              "Full JSON API at /classify, /tickets, /tickets/inbox, /analytics, /tickets/{id}/resolve.", "✅ Live"),
    ("Interactive API Docs",  "Swagger UI available at /docs — test every endpoint in the browser without curl.", "✅ Live"),
]
story.append(feature_table(features))
story.append(Spacer(1, 0.4*cm))

# ── 4. TECHNOLOGY STACK ──────────────────────────────────────────────────────
story.append(Paragraph("4. Technology Stack", SECTION_TITLE))
story.append(section_rule())

stack = [
    ("AI Model",      "Groq API (Llama 3.3 70B) — free tier, extremely fast inference"),
    ("Backend",       "FastAPI (Python) — production-grade REST API framework"),
    ("Database",      "SQLite — zero-setup embedded database, no server required"),
    ("Frontend",      "Vanilla HTML/CSS/JavaScript + Chart.js — no frameworks needed"),
    ("Email Alerts",  "Gmail SMTP — built into Python standard library, no extra cost"),
    ("Slack Alerts",  "Slack Incoming Webhooks — free, no app approval needed"),
    ("Deployment",    "Uvicorn ASGI server — ready for Render, Railway, or VPS"),
    ("Source Code",   "GitHub — github.com/Safwan-Ul-Islam/ticket-classifier"),
]
story.append(info_table(stack))
story.append(Spacer(1, 0.4*cm))

# ── 5. MAKE.COM / N8N ────────────────────────────────────────────────────────
story.append(Paragraph("5. Make.com &amp; n8n — Do You Need Them?", SECTION_TITLE))
story.append(section_rule())
story.append(Paragraph(
    "Make.com and n8n are automation platforms that connect apps together visually. "
    "TicketAI is the <b>AI brain</b>. Make.com/n8n are optional <b>delivery pipes</b> "
    "that feed real-world messages into it.",
    BODY))
story.append(Spacer(1, 0.2*cm))

comparison = [
    ("TicketAI (this system)",
     "Classifies tickets, replies, stores data, sends alerts, shows analytics. "
     "Works right now — no Make.com needed."),
    ("Make.com / n8n (optional)",
     "Connects Gmail, WhatsApp, Shopify, etc. to your API automatically. "
     "Useful when a client wants zero manual copy-paste."),
    ("Together",
     "Gmail inbox → Make.com reads email → POST to /classify → AI replies → "
     "result stored in dashboard. Full automation pipeline."),
]
story.append(info_table(comparison, col_widths=[4.5*cm, 11.5*cm]))
story.append(Spacer(1, 0.2*cm))
story.append(Paragraph(
    "<b>Make.com pricing:</b> Free up to 1,000 tasks/month. Paid plans start at $9/month. "
    "As a freelancer, you build the workflow and the client pays for their own account.",
    BODY))
story.append(Spacer(1, 0.4*cm))

# ── 6. FREELANCING ───────────────────────────────────────────────────────────
story.append(Paragraph("6. How to Sell This as a Freelancer", SECTION_TITLE))
story.append(section_rule())

story.append(Paragraph("<b>Never say:</b>", BOLD_BODY))
story.append(Paragraph(
    '"I built a FastAPI app with Groq LLM, SQLite, and Llama 3.3 70B."',
    BODY))
story.append(Spacer(1, 0.1*cm))
story.append(Paragraph("<b>Always say:</b>", BOLD_BODY))
story.append(Paragraph(
    '"I automate your customer support so 80% of emails get answered '
    'instantly — without hiring anyone."',
    HIGHLIGHT))
story.append(Spacer(1, 0.3*cm))

story.append(Paragraph("<b>Pricing Models</b>", BOLD_BODY))
pricing = [
    ("One-time setup",    "$300 – $800",     "Small businesses, first-time clients"),
    ("Monthly retainer",  "$100 – $300/mo",  "Ongoing support + updates"),
    ("Revenue share",     "Free + % savings","Bigger clients, long-term relationships"),
]
story.append(pricing_table(pricing))
story.append(Spacer(1, 0.3*cm))

story.append(Paragraph("<b>Your Pitch Message (copy this):</b>", BOLD_BODY))
pitch_data = [[
    Paragraph(
        '"I can set up a system that automatically replies to 80% of your customer '
        'emails using AI. You only see the ones that actually need your attention. '
        'Takes 2 days to set up. Want me to show you a live demo?"',
        ParagraphStyle("pitch",
            fontSize=10.5, fontName="Helvetica-Oblique",
            textColor=colors.HexColor("#1e293b"),
            leading=16, leftIndent=0))
]]
pitch_t = Table(pitch_data, colWidths=[16*cm])
pitch_t.setStyle(TableStyle([
    ("BACKGROUND",   (0,0),(-1,-1), colors.HexColor("#eef2ff")),
    ("ROUNDEDCORNERS",[8]),
    ("TOPPADDING",   (0,0),(-1,-1),12),
    ("BOTTOMPADDING",(0,0),(-1,-1),12),
    ("LEFTPADDING",  (0,0),(-1,-1),14),
    ("RIGHTPADDING", (0,0),(-1,-1),14),
    ("BOX",          (0,0),(-1,-1),1.5,INDIGO),
]))
story.append(pitch_t)
story.append(Spacer(1, 0.4*cm))

# ── 7. NEXT STEPS ────────────────────────────────────────────────────────────
story.append(Paragraph("7. Recommended Next Steps", SECTION_TITLE))
story.append(section_rule())

next_steps = [
    ("Step 1 — Deploy Live",
     "Put the system on a real URL using Render.com (free). "
     "A live link is required before any client will take you seriously."),
    ("Step 2 — Record Demo Video",
     "2-minute screen recording: submit ticket → AI classifies → email arrives "
     "→ dashboard updates. Upload to YouTube (unlisted) and link everywhere."),
    ("Step 3 — Find First Client",
     "Target small e-commerce stores, clinics, salons, or repair shops. "
     "Anyone saying 'I spend hours on customer emails' is your client."),
    ("Step 4 — Post on LinkedIn",
     "Post the demo video with your GitHub link. Explain what it does "
     "in plain English. Tag it: #AI #automation #customerservice #freelance"),
    ("Step 5 — Add Make.com",
     "When a client asks for Gmail/WhatsApp integration, add a Make.com "
     "workflow on top. Charge an extra $200–$400 for the integration."),
]
story.append(info_table(next_steps))
story.append(Spacer(1, 0.4*cm))

# ── 8. GITHUB ────────────────────────────────────────────────────────────────
story.append(Paragraph("8. Repository &amp; Links", SECTION_TITLE))
story.append(section_rule())
links = [
    ("GitHub",      "github.com/Safwan-Ul-Islam/ticket-classifier"),
    ("Live API",    "http://127.0.0.1:8000 (local) → deploy to get public URL"),
    ("API Docs",    "http://127.0.0.1:8000/docs"),
    ("Public Form", "http://127.0.0.1:8000/submit"),
    ("Dashboard",   "http://127.0.0.1:8000"),
]
story.append(info_table(links))
story.append(Spacer(1, 0.6*cm))

# ── FOOTER ───────────────────────────────────────────────────────────────────
footer_data = [[
    Paragraph(
        "TicketAI  •  Built by Safwan  •  2026  •  github.com/Safwan-Ul-Islam/ticket-classifier",
        ParagraphStyle("footer",
            fontSize=8.5, fontName="Helvetica",
            textColor=WHITE, alignment=TA_CENTER))
]]
footer_t = Table(footer_data, colWidths=[16*cm])
footer_t.setStyle(TableStyle([
    ("BACKGROUND",   (0,0),(-1,-1), DARK_BG),
    ("ROUNDEDCORNERS",[8]),
    ("TOPPADDING",   (0,0),(-1,-1),10),
    ("BOTTOMPADDING",(0,0),(-1,-1),10),
]))
story.append(footer_t)

doc.build(story)
print(f"✅  PDF saved → {OUTPUT}")
