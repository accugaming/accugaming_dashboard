# landing/dashboard_api.py
from flask import Blueprint, session, jsonify, redirect
import requests

dashboard_api = Blueprint('dashboard_api', __name__)

DISCORD_API_BASE = "https://discord.com/api"

@dashboard_api.route("/api/user")
def get_user():
    user = session.get("user")
    if not user:
        return redirect("/login")
    return jsonify(user)

@dashboard_api.route("/api/guilds")
def get_guilds():
    user_guilds = session.get("guilds", [])
    bot_guild_ids = get_bot_guild_ids()  # You need to write this
    result = []
    for g in user_guilds:
        if int(g.get("permissions", 0)) & 0x20:  # Manage Server permission
            result.append({
                "id": g["id"],
                "name": g["name"],
                "icon": g["icon"],
                "botInGuild": g["id"] in bot_guild_ids
            })
    return jsonify(result)

def get_bot_guild_ids():
    # Use your bot's token to get guilds it is in
    headers = {"Authorization": f"Bot YOUR_BOT_TOKEN"}
    res = requests.get(f"{DISCORD_API_BASE}/users/@me/guilds", headers=headers)
    if res.status_code != 200:
        return []
    return [g["id"] for g in res.json()]
