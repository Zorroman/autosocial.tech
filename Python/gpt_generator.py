import openai
from config import Config

openai.api_key = Config.OPENAI_API_KEY

def generate_post(niche):
    prompt = f"Создай интересный Instagram пост по теме: {niche}. Добавь call-to-action."
    res = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return res['choices'][0]['message']['content']
