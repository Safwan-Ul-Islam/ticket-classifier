import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
    category: str
    confidence: int
    auto_reply: str | None
    agent_summary: str | None
    urgency: str
    should_auto_reply: bool


@app.get("/")
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

        return TicketResponse(
            category=result.get("category", "general_inquiry"),
            confidence=confidence,
            auto_reply=result.get("auto_reply"),
            agent_summary=result.get("agent_summary"),
            urgency=result.get("urgency", "normal"),
            should_auto_reply=confidence >= 85
        )

    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"AI returned invalid JSON: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
