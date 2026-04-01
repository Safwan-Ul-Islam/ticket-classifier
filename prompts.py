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

1. DETECT the language of the customer's message and return the ISO 639-1
   two-letter code (e.g. "en", "ur", "ar", "fr", "es", "de").

2. SCORE the customer's sentiment from 1 to 10:
   1-3 = very angry or frustrated
   4-6 = neutral
   7-10 = happy or satisfied

3. CLASSIFY the issue into exactly one of these categories:
   - billing
   - refund
   - technical
   - shipping
   - general_inquiry
   - complaint

4. SCORE your confidence from 0 to 100 on how well you can resolve
   this using only the FAQ below. Be honest.

5. If confidence is 70 or above:
   Write a warm, helpful reply under 150 words using only the FAQ.
   Reply in the SAME LANGUAGE as the customer's message.
   Address the customer by their first name.
   End with: Let me know if there is anything else I can help with!
   Set agent_summary to null.

6. If confidence is below 70:
   Write a short 2-3 sentence agent_summary for a human agent explaining
   what the customer needs and any important details.
   Set auto_reply to null.

7. ALWAYS write a suggested_reply: a 2-4 sentence draft response the human
   agent can edit and send to the customer. Write it in the customer's language.
   This is required even when auto_reply is set.

FAQ KNOWLEDGE BASE:
{faq_context}

IMPORTANT: Respond ONLY as a valid JSON object.
No explanation, no markdown, no code fences. Just raw JSON like this:
{{
  "category": "billing",
  "confidence": 92,
  "language": "en",
  "sentiment_score": 4,
  "auto_reply": "Hi Sarah, thanks for reaching out...",
  "suggested_reply": "Hi Sarah, I understand you have a question about billing...",
  "agent_summary": null,
  "urgency": "normal"
}}

For urgency: use "high" if sentiment_score is 3 or below OR the customer
mentions losing money or is very angry. Use "normal" for everything else.
If you write an auto_reply, set agent_summary to null.
If you write an agent_summary, set auto_reply to null.
"""
