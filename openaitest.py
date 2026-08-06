from openai import OpenAI
from config import apikey

client = OpenAI(api_key=apikey)

try:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are Aanya, a helpful personal AI assistant for Srishti Mishra."
            },
            {
                "role": "user",
                "content": "Create a study plan for today."
            }
        ],
        temperature=0.7,
        max_tokens=200
    )
    print(response.choices[0].message.content)
except Exception as e:
    print(f"Failed to get a response from OpenAI: {e}")

'''
{
    "choices": [
        {
            "finish_reason": "stop",
            "index": 0,
            "logprobs": null,
            "text": "\n\nSubject: Resignation\n\nDear [Name],\n\nI am writing to inform you of my intention to resign from my current position at [Company]. My last day of work will be [date].\n\nI have enjoyed my time at [Company], and I am grateful for the opportunity to work here. I have learned a great deal during my time in this position, and I am grateful for the experience.\n\nIf I can be of any assistance during this transition, please do not hesitate to ask.\n\nThank you for your understanding.\n\nSincerely,\n[Your Name]"
        }
    ],
    "created": 1683815400,
    "id": "cmpl-7F1aqg7BkzIY8vBnCxYQh8Xp4wO85",
    "model": "text-davinci-003",
    "object": "text_completion",
    "usage": {
        "completion_tokens": 125,
        "prompt_tokens": 9,
        "total_tokens": 134
    }
}
'''