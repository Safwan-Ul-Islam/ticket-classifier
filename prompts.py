def build_classify_prompt(
    ticket_body: str,
    customer_name: str,
    product_name: str,
    faq_context: str
) -> str:
    return f"""You are a helpful support AI for {product_name}.

A customer named {customer_name} sent this support message:
---
{ticket_body}
---

YOUR TASKS:

1. CLASSIFY the issue into exactly one of these categories:
   - billing
   - refund
   - technical
   - shipping
   - general_inquiry
   - complaint

2. SCORE your confidence from 0 to 100 on how well you can resolve
   this using only the FAQ below. Be honest. If the issue is complex
   or unclear, score it lower.

3. If confidence is 85 or above:
   Write a warm, helpful reply under 150 words using only the FAQ.
   Address the customer by their first name.
   End with: Let me know if there is anything else I can help with!

4. If confidence is below 85:
   Write a short 2 to 3 sentence summary for a human agent explaining
   what the customer needs and any important details.

FAQ KNOWLEDGE BASE:
{faq_context}

IMPORTANT: Respond ONLY as a valid JSON object.
No explanation, no markdown, no code fences. Just raw JSON like this:
{{
  "category": "billing",
  "confidence": 92,
  "auto_reply": "Hi Sarah, thanks for reaching out...",
  "agent_summary": null,
  "urgency": "normal"
}}

For urgency: use "high" if the customer seems angry or frustrated
or mentions losing money. Use "normal" for everything else.
If you write an auto_reply, set agent_summary to null.
If you write an agent_summary, set auto_reply to null.
"""
