import os
import discord
from discord.ext import commands
import aiohttp
import json

# ============================================
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
CHAT_CHANNEL_NAME = "ai-chat"
BOT_PERSONALITY = "You are a helpful, friendly assistant in a Discord server. Keep responses concise and conversational."
# ============================================

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Store conversation history per user
conversation_history = {}


async def ask_groq(user_id, message, image_url=None):
    """Send message to Groq API and get response"""

    if user_id not in conversation_history:
        conversation_history[user_id] = []

    # Add user message to history
    conversation_history[user_id].append({
        "role": "user",
        "content": message
    })

    # Keep last 10 messages
    if len(conversation_history[user_id]) > 10:
        conversation_history[user_id] = conversation_history[user_id][-10:]

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama3-8b-8192",
        "messages": [
            {"role": "system", "content": BOT_PERSONALITY},
            *conversation_history[user_id]
        ],
        "max_tokens": 1024,
        "temperature": 0.9,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                reply = data["choices"][0]["message"]["content"]

                # Add assistant response to history
                conversation_history[user_id].append({
                    "role": "assistant",
                    "content": reply
                })

                return reply
            else:
                error = await resp.text()
                print(f"Groq error: {error}")
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
        response = await ask_groq(
            str(message.author.id),
            message.content
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
    """Ask Groq a question with !ask"""
    async with ctx.typing():
        response = await ask_groq(str(ctx.author.id), question)
        if len(response) > 2000:
            chunks = [response[i:i+2000] for i in range(0, len(response), 2000)]
            for chunk in chunks:
                await ctx.send(chunk)
        else:
            await ctx.send(response)


bot.run(DISCORD_TOKEN)
