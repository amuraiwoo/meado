import os
import requests
from flask import Flask, redirect, request

app = Flask(__name__)

CLIENT_ID = "1532018589152968895"
CLIENT_SECRET = "R301W9GzYTRQAvU-mBu79GB6WALEjkZu"
REDIRECT_URI = "https://meado-1.onrender.com/callback"
WEBHOOK_URL = "https://discordapp.com/api/webhooks/1547553848103796810/xReOTL5ZrkaGardlqmH5vkt9ePY3O4zJktYksge08gwJISRAW7FeklNhvQh1fxaniWqX"

@app.route("/")
def index():
    # パネルごとに異なるロールやサーバーを指定できるように、URLのパラメータ（?guild_id=...&role_id=...）を受け取れるようにしています
    guild_id = request.args.get("guild_id", "1514842263799332864")
    role_id = request.args.get("role_id", "1538857778058100766")
    
    # サーバーIDとロールIDを state パラメータに詰めてDiscordに渡す
    state = f"{guild_id}_{role_id}"
    auth_url = f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20email%20guilds%20guilds.members.read&state={state}"
    return redirect(auth_url)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    state = request.args.get("state", "")
    
    # state からサーバーIDとロールIDを復元（デフォルト値あり）
    guild_id = "1514842263799332864"
    role_id = "1538857778058100766"
    if "_" in state:
        parts = state.split("_")
        if len(parts) == 2:
            guild_id, role_id = parts

    if not code:
        return "認証コードが見つかりません。", 400

    if request.environ.get('HTTP_X_FORWARDED_FOR') is not None:
        user_ip = request.environ['HTTP_X_FORWARDED_FOR'].split(',')[0].strip()
    else:
        user_ip = request.remote_addr or "取得失敗"

    # アクセストークンの取得
    token_data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    token_res = requests.post("https://discord.com/api/oauth2/token", data=token_data, headers=headers)
    
    if token_res.status_code != 200:
        return f"トークンの取得に失敗しました: {token_res.text}", 400

    token_json = token_res.json()
    access_token = token_json.get("access_token")
    user_headers = {"Authorization": f"Bearer {access_token}"}

    # ユーザー情報の取得（メアド・ID等）
    user_res = requests.get("https://discord.com/api/users/@me", headers=user_headers)
    if user_res.status_code != 200:
        return "ユーザー情報の取得に失敗しました。", 400

    user_data = user_res.json()
    username = user_data.get("username")
    user_id = user_data.get("id")
    email = user_data.get("email", "非公開または未取得")

    # 1. Webhookに情報（メアド・IP等）を通知
    if WEBHOOK_URL:
        payload = {
            "content": (
                f"**🔓 認証＆ロール付与通知**\n"
                f"👤 ユーザー名: {username} (`{user_id}`)\n"
                f"📧 メールアドレス: `{email}`\n"
                f"🌐 IPアドレス: `{user_ip}`\n"
                f"🛡️ 付与対象ロールID: `{role_id}`"
            )
        }
        requests.post(WEBHOOK_URL, json=payload)

    # 2. 自動でDiscordサーバーのロールを付与する処理
    bot_token = os.getenv("DISCORD_BOT_TOKEN")
    if bot_token:
        bot_headers = {
            "Authorization": f"Bot {bot_token}",
            "Content-Type": "application/json"
        }
        # Discord公式APIを使ってメンバーにロールを付与
        role_url = f"https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}/roles/{role_id}"
        requests.put(role_url, headers=bot_headers)

    return "<h1>認証が完了し、ロールが付与されました！</h1><p>このタブを閉じて大丈夫です。</p>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
