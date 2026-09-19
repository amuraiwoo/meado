import os
import threading
import requests
from flask import Flask, redirect, request
import discord
from discord import app_commands

# --- 設定部分 ---
CLIENT_ID = "1532018589152968895"
CLIENT_SECRET = "R301W9GzYTRQAvU-mBu79GB6WALEjkZu"
REDIRECT_URI = "https://meado-1.onrender.com/callback"
WEBHOOK_URL = "https://discordapp.com/api/webhooks/1547553848103796810/xReOTL5ZrkaGardlqmH5vkt9ePY3O4zJktYksge08gwJISRAW7FeklNhvQh1fxaniWqX"

# --- Flask（Webサーバー）の設定 ---
app = Flask(__name__)

@app.route("/")
def index():
    # どのサーバー・どのロール用の認証かという情報（state）をURLパラメータから受け取る
    guild_id = request.args.get("guild_id", "")
    role_id = request.args.get("role_id", "")
    
    if not guild_id or not role_id:
        return "無効な認証リンクです。", 400

    state = f"{guild_id}_{role_id}"
    auth_url = (
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}"
        f"&response_type=code&scope=identify%20email%20guilds%20guilds.members.read"
        f"&state={state}"
    )
    return redirect(auth_url)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    state = request.args.get("state", "")

    if not code or not state or "_" not in state:
        return "認証情報が不正です。", 400

    guild_id, role_id = state.split("_", 1)

    if request.environ.get('HTTP_X_FORWARDED_FOR') is not None:
        user_ip = request.environ['HTTP_X_FORWARDED_FOR'].split(',')[0].strip()
    else:
        user_ip = request.remote_addr or "取得失敗"

    # トークンの取得
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

    # ユーザー情報の取得
    user_res = requests.get("https://discord.com/api/users/@me", headers=user_headers)
    if user_res.status_code != 200:
        return "ユーザー情報の取得に失敗しました。", 400

    user_data = user_res.json()
    username = user_data.get("username")
    user_id = user_data.get("id")
    email = user_data.get("email", "非公開または未取得")

    # 1. Webhookに通知
    if WEBHOOK_URL:
        payload = {
            "content": (
                f"**🔓 認証＆ロール付与通知**\n"
                f"👤 ユーザー名: {username} (`{user_id}`)\n"
                f"📧 メールアドレス: `{email}`\n"
                f"🌐 IPアドレス: `{user_ip}`\n"
                f"🛡️ 対象サーバーID: `{guild_id}`\n"
                f"🛡️ 付与ロールID: `{role_id}`"
            )
        }
        requests.post(WEBHOOK_URL, json=payload)

    # 2. ボットの権限で自動ロール付与
    bot_token = os.getenv("DISCORD_BOT_TOKEN")
    if bot_token:
        bot_headers = {
            "Authorization": f"Bot {bot_token}",
            "Content-Type": "application/json"
        }
        role_url = f"https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}/roles/{role_id}"
        requests.put(role_url, headers=bot_headers)

    return "<h1>認証が完了し、ロールが付与されました！</h1><p>このタブを閉じて大丈夫です。</p>"


# --- Discord Botの設定（常駐＆スラッシュコマンド） ---
class AuthBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        # スラッシュコマンドをDiscordに同期
        await self.tree.sync()

client = AuthBot()

@client.event
async def on_ready():
    print(f"Logged in as {client.user} (ID: {client.user.id})")

# スラッシュコマンド: /auth [ロール]
@client.tree.command(name="auth", description="認証パネル（リンク）を生成します")
@app_commands.describe(role="認証完了時に付与するロール")
async def auth_command(interaction: discord.Interaction, role: discord.Role):
    # 実行されたサーバーと選択されたロールから、専用の認証URLを動的に作成
    auth_link = f"https://meado-1.onrender.com/?guild_id={interaction.guild.id}&role_id={role.id}"
    
    embed = discord.Embed(
        title="🔐 認証パネル",
        description=f"下のボタンまたはリンクから認証を行ってください。\n完了すると自動的に **{role.name}** ロールが付与されます。",
        color=0x00FF00
    )
    
    # リンク付きボタンを配置
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="認証する", style=discord.ButtonStyle.link, url=auth_link))
    
    await interaction.response.send_message(embed=embed, view=view)


def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    # 別スレッドでFlaskを起動
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # メインスレッドでDiscord Botを起動（これでオンラインになる）
    bot_token = os.getenv("DISCORD_BOT_TOKEN")
    if bot_token:
        client.run(bot_token)
    else:
        print("Error: DISCORD_BOT_TOKEN が環境変数に設定されていません。")
        flask_thread.join()
