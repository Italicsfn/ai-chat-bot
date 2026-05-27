import os
import discord
from discord.ext import commands
import aiohttp
import json

# ============================================
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
CHAT_CHANNEL_NAME = "ai-chat"
BOT_PERSONALITY = "You are a helpful, friendly assistant in a Discord server. Keep responses concise and conversational."
# ============================================

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Store conversation history per user
conversation_history = {}


async def ask_gemini(user_id, message, image_url=None):
    """Send message to Gemini API and get response"""

    if user_id not in conversation_history:
        conversation_history[user_id] = []

    # Build message parts
    parts = []

    if image_url:
        # Download image and send as base64
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as img_resp:
                if img_resp.status == 200:
                    img_data = await img_resp.read()
                    import base64
                    img_b64 = base64.b64encode(img_data).decode("utf-8")
                    content_type = img_resp.content_type or "image/png"
                    parts.append({
                        "inline_data": {
                            "mime_type": content_type,
                            "data": img_b64
                        }
                    })

    parts.append({"text": message})

    # Add to history
    conversation_history[user_id].append({
        "role": "user",
        "parts": parts
    })

    # Keep last 10 messages
    if len(conversation_history[user_id]) > 10:
        conversation_history[user_id] = conversation_history[user_id][-10:]

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

    payload = {
        "system_instruction": {
            "parts": [{"text": BOT_PERSONALITY}]
        },
        "contents": conversation_history[user_id],
        "generationConfig": {
            "maxOutputTokens": 1024,
            "temperature": 0.9,
        }
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            if resp.status == 200:
                data = await resp.json()
                reply = data["candidates"][0]["content"]["parts"][0]["text"]

                # Add assistant response to history
                conversation_history[user_id].append({
                    "role": "model",
                    "parts": [{"text": reply}]
                })

                return reply
            else:
                error = await resp.text()
                print(f"Gemini error: {error}")
                return "⚠️ Something went wrong. Try again!"


@bot.event
async def on_ready():
    print(f"✅ {bot.user} is online and ready!")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.channel.name != CHAT_CHANNEL_NAME:
        await bot.process_commands(message)
        return

    if message.content.startswith("!"):
        await bot.process_commands(message)
        return

    async with message.channel.typing():
        image_url = None
        if message.attachments:
            for attachment in message.attachments:
                if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                    image_url = attachment.url
                    break

        response = await ask_gemini(
            str(message.author.id),
            message.content,
            image_url
        )

        if len(response) > 2000:
            chunks = [response[i:i+2000] for i in range(0, len(response), 2000)]
            for chunk in chunks:
                await message.channel.send(chunk)
        else:
            await message.channel.send(response)


@bot.command(name="reset")
async def reset_chat(ctx):
    """Reset conversation history"""
    if str(ctx.author.id) in conversation_history:
        del conversation_history[str(ctx.author.id)]
    await ctx.send("🔄 Conversation reset! Starting fresh.")


@bot.command(name="ask")
async def ask_command(ctx, *, question):
    """Ask Gemini a question with !ask"""
    async with ctx.typing():
        response = await ask_gemini(str(ctx.author.id), question)
        if len(response) > 2000:
            chunks = [response[i:i+2000] for i in range(0, len(response), 2000)]
            for chunk in chunks:
                await ctx.send(chunk)
        else:
            await ctx.send(response)


bot.run(DISCORD_TOKEN)
