from flask import Flask, redirect, request, jsonify, send_from_directory, session
from dotenv import load_dotenv
import os
import urllib.parse
import requests
import sqlite3

# ----------- Load Environment Variables -----------
load_dotenv()

CLIENT_ID = os.getenv('DISCORD_CLIENT_ID')
CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET')
BOT_TOKEN = os.getenv('BOT_TOKEN')
REDIRECT_URI = os.getenv('REDIRECT_URI', 'http://localhost:3001/callback')
API_BASE_URL = "https://discord.com/api"

DB_PATH = './data.db'

app = Flask(__name__, static_folder='landing')
app.secret_key = os.getenv("FLASK_SECRET", "default_dev_key")


# ----------- Database Helper -----------
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def query_db(query, args=(), one=False):
    conn = get_db_connection()
    cur = conn.execute(query, args)
    rv = cur.fetchall()
    conn.close()
    return (rv[0] if rv else None) if one else rv


# ----------- Landing Pages -----------

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(app.static_folder, path)


@app.route('/images/<path:path>')
def serve_images(path):
    return send_from_directory(os.path.join(app.static_folder, 'images'), path)


# ----------- Discord OAuth Routes -----------

@app.route('/login')
def login():
    scope = 'identify guilds'
    params = {
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'response_type': 'code',
        'scope': scope
    }
    url = f"{API_BASE_URL}/oauth2/authorize?{urllib.parse.urlencode(params)}"
    return redirect(url)


@app.route('/callback')
def callback():
    code = request.args.get("code")
    if not code:
        return "No code provided", 400

    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI,
        'scope': 'identify guilds'
    }

    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    token_res = requests.post(f"{API_BASE_URL}/oauth2/token", data=data, headers=headers)

    if token_res.status_code != 200:
        return f"Token request failed: {token_res.text}", 400

    credentials = token_res.json()
    access_token = credentials.get("access_token")
    headers_auth = {"Authorization": f"Bearer {access_token}"}

    user = requests.get(f"{API_BASE_URL}/users/@me", headers=headers_auth).json()
    guilds = requests.get(f"{API_BASE_URL}/users/@me/guilds", headers=headers_auth).json()

    session["user"] = user
    session["guilds"] = guilds

    return redirect("/dashboard")


@app.route('/logout')
def logout():
    session.clear()
    return redirect("/login")


# ----------- API Routes -----------

@app.route('/api/user')
def api_user():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(session["user"])


@app.route('/api/guilds')
def api_guilds():
    if "guilds" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    bot_guild_ids = get_bot_guilds()
    filtered = []

    for guild in session["guilds"]:
       if int(guild.get("permissions", 0)) & (0x20 | 0x8):
            filtered.append({
                "id": guild["id"],
                "name": guild["name"],
                "icon": guild["icon"],
                "botInGuild": guild["id"] in bot_guild_ids
            })

    return jsonify({"success": True, "message": "Settings saved successfully"})


def get_bot_guilds():
    if not BOT_TOKEN:
        return []
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    res = requests.get(f"{API_BASE_URL}/users/@me/guilds", headers=headers)
    return [g["id"] for g in res.json()] if res.status_code == 200 else []


# ----------- Server Settings DB -----------

def get_server_settings(guild_id):
    conn = get_db_connection()
    cur = conn.execute('SELECT * FROM server_settings WHERE guild_id = ?', (guild_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def save_server_settings(guild_id, data):
    conn = get_db_connection()
    exists = conn.execute('SELECT 1 FROM server_settings WHERE guild_id = ?', (guild_id,)).fetchone()

    if exists:
        conn.execute('''
            UPDATE server_settings SET
            setting1 = ?, setting2 = ?
            WHERE guild_id = ?
        ''', (data.get('setting1'), data.get('setting2'), guild_id))
    else:
        conn.execute('''
            INSERT INTO server_settings (guild_id, setting1, setting2)
            VALUES (?, ?, ?)
        ''', (guild_id, data.get('setting1'), data.get('setting2')))

    conn.commit()
    conn.close()

# ----------- Permission Checker -----------

def user_can_manage_guild(guild_id):
    if "guilds" not in session:
        return False
    for guild in session["guilds"]:
        if guild["id"] == guild_id:
            return int(guild.get("permissions", 0)) & 0x20 != 0
    return False


# ----------- Config API Endpoints -----------

@app.route('/api/server/<guild_id>/config', methods=['GET'])
def api_get_config(guild_id):
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    if not user_can_manage_guild(guild_id):
        return jsonify({"error": "Forbidden"}), 403

    config = get_server_settings(guild_id)
    return jsonify(config or {"error": "Not configured"})


@app.route('/api/server/<guild_id>/config', methods=['POST'])
def api_save_config(guild_id):
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    if not user_can_manage_guild(guild_id):
        return jsonify({"error": "Forbidden"}), 403

    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    save_server_settings(guild_id, data)
    return jsonify({"success": True})


# ----------- Page Routes -----------

@app.route('/dashboard')
def dashboard():
    if "user" not in session:
        return redirect("/login")
    return send_from_directory(app.static_folder, 'dashboard.html')

@app.route('/invite')
def invite():
    return redirect(f"https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&permissions=8&scope=bot%20applications.commands")

@app.route('/support')
def support():
    if "user" not in session:
        return redirect("/login")
    return send_from_directory(app.static_folder, 'support.html')


@app.route('/configure')
def configure():
    if "user" not in session:
        return redirect("/login")
    return send_from_directory(app.static_folder, 'configure.html')


@app.route('/server/<guild_id>')
def server_configure(guild_id):
    if "user" not in session:
        return redirect("/login")
    if not user_can_manage_guild(guild_id):
        return "Unauthorized: You don't have permission to manage this guild.", 403
    return send_from_directory(app.static_folder, 'configure.html')

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS server_settings (
            guild_id TEXT PRIMARY KEY,
            setting1 TEXT,
            setting2 TEXT
        )
    ''')
    conn.commit()
    conn.close()

# ----------- Run App -----------

if __name__ == "__main__":
    app.run(debug=True, port=3001)
