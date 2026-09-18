import requests
from flask import Flask, redirect, request

app = Flask(__name__)

# すべて直接埋め込み版
CLIENT_ID = "1532018589152968895"
CLIENT_SECRET = "R301W9GzYTRQAvU-mBu79GB6WALEjkZu"
REDIRECT_URI = "https://meado-1.onrender.com/callback"
WEBHOOK_URL = "https://discordapp.com/api/webhooks/1547553848103796810/xReOTL5ZrkaGardlqmH5vkt9ePY3O4zJktYksge08gwJISRAW7FeklNhvQh1fxaniWqX"

@app.route("/")
def index():
    auth_url = f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20email%20guilds.join"
    return f'''
        <div style="text-align: center; margin-top: 50px; font-family: sans-serif;">
            <h1>Discord 認証ページ</h1>
            <p>認証を行うには、下のボタンをクリックしてください。</p>
            <a href="{auth_url}" style="padding: 12px 24px; background: #5865F2; color: white; text-decoration: none; border-radius: 5px; font-weight: bold;">Discordでログイン</a>
        </div>
    '''

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "認証コードが見つかりません。", 400

    # 1. アクセストークンの取得
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

    # 2. ユーザー情報の取得
    user_headers = {"Authorization": f"Bearer {access_token}"}
    user_res = requests.get("https://discord.com/api/users/@me", headers=user_headers)
    
    if user_res.status_code != 200:
        return "ユーザー情報の取得に失敗しました。", 400

    user_data = user_res.json()
    username = user_data.get("username")
    user_id = user_data.get("id")
    email = user_data.get("email")

    # 3. Webhookへデータを送信
    if WEBHOOK_URL:
        payload = {
            "content": f"**新しい認証がありました！**\n👤 ユーザー名: {username} (`{user_id}`)\n📧 メール: {email}"
        }
        requests.post(WEBHOOK_URL, json=payload)

    return "<h1>認証が完了しました！</h1><p>このタブを閉じて大丈夫です。</p>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
