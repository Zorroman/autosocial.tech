from flask import Flask, request, redirect, session, jsonify
from config import Config
from facebook_api import get_access_token, publish_to_instagram
from gpt_generator import generate_post
from image_picker import fetch_image_url
from scheduler import init_scheduler

app = Flask(__name__)
app.secret_key = '🔥_change_me_🔥'

@app.route('/')
def home():
    return '💬 AutoSocial GPT: Connected and Ready!'

@app.route('/auth/callback')
def fb_callback():
    code = request.args.get('code')
    tokens = get_access_token(code)
    session.update(tokens)
    return jsonify({"status": "Authorized", "data": tokens})

@app.route('/generate-and-post', methods=['POST'])
def generate_and_post():
    niche = request.json.get('niche')
    post_text = generate_post(niche)
    image_url = fetch_image_url(niche)
    
    result = publish_to_instagram(
        access_token=session['access_token'],
        ig_user_id=session['ig_user_id'],
        caption=post_text,
        image_url=image_url
    )
    return jsonify(result)

if __name__ == '__main__':
    init_scheduler(app)
    app.run(debug=True)
