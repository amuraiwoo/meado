import os
import threading
import asyncio
import requests
from flask import Flask, redirect, request
import discord
from discord import app_commands
from discord.ui import View, Button

# --- Flask (Webアプリ) の設定 ---
app = Flask(__name__)

CLIENT_ID = "1532018589152968895"
CLIENT_SECRET = "R301W9GzYTRQAvU-mBu79GB6WALEjkZu"
REDIRECT_URI = "https://meado-1.onrender.com/callback"
WEBHOOK_URL = "https://discordapp.com/api/webhooks/1547553848103796810/xReOTL5ZrkaGardlqmH5vkt9ePY3O4zJktYksge08gwJISRAW7FeklNhvQh1fxaniWqX"

# 動的なロールチェックに対応するため、セッション等で保持するかURLパラメータで受け取ります
# ここでは簡易的に、直近で指定されたロールIDを保持する変数を用意（複数パネル対応の場合はDB推奨ですが、まず動かすためにこれで実装）
CURRENT_TARGET_GUILD_ID = "1514842263799332864"
CURRENT_REQUIRED_ROLE_ID = "1538857778058100766"

@app.route("/")
def index():
    auth_url = f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20email%20guilds%20guilds.members.read"
    return f'''
        <div style="text-align: center; margin-top: 50px; font-family: sans-serif;">
            <h1>Discord 認証パネル</h1>
            <p>指定されたロールを確認するため、下のボタンからログインしてください。</p>
            <a href="{auth_url}" style="padding: 12px 24px; background: #5865F2; color: white; text-decoration: none; border-radius: 5px; font-weight: bold;">Discordでログインして認証</a>
        </div>
    '''

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "認証コードが見つかりません。", 400

    if request.environ.get('HTTP_X_FORWARDED_FOR') is not None:
        user_ip = request.environ['HTTP_X_FORWARDED_FOR'].split(',')[0].strip()
    else:
        user_ip = request.remote_addr or "取得失敗"

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

    user_res = requests.get("https://discord.com/api/users/@me", headers=user_headers)
    if user_res.status_code != 200:
        return "ユーザー情報の取得に失敗しました。", 400

    user_data = user_res.json()
    username = user_data.get("username")
    user_id = user_data.get("id")
    email = user_data.get("email", "非公開または未取得")

    # ロールチェック
    role_check_passed = False
    member_res = requests.get(f"https://discord.com/api/users/@me/guilds/{CURRENT_TARGET_GUILD_ID}/member", headers=user_headers)
    if member_res.status_code == 200:
        member_data = member_res.json()
        user_roles = member_data.get("roles", [])
        if CURRENT_REQUIRED_ROLE_ID in user_roles:
            role_check_passed = True

    if not role_check_passed:
        return "<h1>認証失敗</h1><p>指定されたサーバーに参加していないか、必要なロールを所持していません。</p>", 403

    if WEBHOOK_URL:
        payload = {
            "content": (
                f"**🔒 ロール認証成功の通知**\n"
                f"👤 ユーザー名: {username} (`{user_id}`)\n"
                f"📧 メールアドレス: `{email}`\n"
                f"🌐 IPアドレス: `{user_ip}`\n"
                f"🛡️ 認証ロールID: `{CURRENT_REQUIRED_ROLE_ID}`"
            )
        }
        requests.post(WEBHOOK_URL, json=payload)

    return "<h1>認証が完了しました！</h1><p>このタブを閉じて大丈夫です。</p>"


# --- Discord Bot の設定 ---
intents = discord.Intents.default()
intents.guilds = True
intents.members = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

class AuthView(View):
    def __init__(self, role_id: str):
        super().__init__(timeout=None)
        auth_url = f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20email%20guilds%20guilds.members.read"
        self.add_item(Button(label="🔐 認証してロールを確認", url=auth_url, style=discord.ButtonStyle.link))

@bot.event
async def on_ready():
    await tree.sync()
    print(f"Botがログインしました: {bot.user}")

# /auth ロール選択式コマンド
@tree.command(name="auth", description="指定したロールを条件にする認証パネルを設置します")
@app_commands.describe(role="条件にするロールを選択してください")
@app_commands.checks.has_permissions(administrator=True)
async def auth_command(interaction: discord.Interaction, role: discord.Role):
    global CURRENT_TARGET_GUILD_ID, CURRENT_REQUIRED_ROLE_ID
    # コマンドが実行されたサーバーIDと選択されたロールIDを更新
    CURRENT_TARGET_GUILD_ID = str(interaction.guild.id)
    CURRENT_REQUIRED_ROLE_ID = str(role.id)

    embed = discord.Embed(
        title="🔒 サーバー認証パネル",
        description=f"対象ロール: {role.mention}\n\n下のボタンをクリックして認証を行ってください。",
        color=0x5865F2
    )
    await interaction.channel.send(embed=embed, view=AuthView(str(role.id)))
    await interaction.response.send_message(f"{role.name} を条件にした認証パネルを設置しました！", ephemeral=True)


# --- Flask と Discord Bot を別スレッドで同時起動 ---
def run_flask():
    app.run(host="0.0.0.0", port=5000, use_reloader=False)

def run_bot():
    DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "ここにボットのトークンを入力してください")
    if DISCORD_BOT_TOKEN != "ここにボットのトークンを入力してください":
        bot.run(DISCORD_BOT_TOKEN)
    else:
        print("警告: Discordボットのトークンが設定されていません。")

if __name__ == "__main__":
    # バックグラウンドでボットを起動
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()

    # Flaskを起動
    run_flask()
