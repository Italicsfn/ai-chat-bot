import os
import discord
from discord.ext import commands
import aiohttp
import json

# ============================================
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")
CHAT_CHANNEL_NAME = "ai-chat"  # Change to your channel name
BOT_PERSONALITY = "You are a helpful assistant in a Discord server. Keep responses concise and friendly."
# ============================================

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Store conversation history per user
conversation_history = {}


async def ask_claude(user_id, message, image_url=None):
    """Send message to Claude API and get response"""
    
    # Get or create conversation history for this user
    if user_id not in conversation_history:
        conversation_history[user_id] = []

    # Build message content
    content = []
    
    # Add image if provided
    if image_url:
        content.append({
            "type": "image",
            "source": {
                "type": "url",
                "url": image_url
            }
        })

    content.append({
        "type": "text",
        "text": message
    })

    # Add user message to history
    conversation_history[user_id].append({
        "role": "user",
        "content": content
    })

    # Keep last 10 messages to avoid token limits
    if len(conversation_history[user_id]) > 10:
        conversation_history[user_id] = conversation_history[user_id][-10:]

    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }

    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1024,
        "system": BOT_PERSONALITY,
        "messages": conversation_history[user_id]
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                reply = data["content"][0]["text"]
                
                # Add assistant response to history
                conversation_history[user_id].append({
                    "role": "assistant",
                    "content": reply
                })
                
                return reply
            else:
                return "⚠️ Something went wrong. Try again!"


@bot.event
async def on_ready():
    print(f"✅ {bot.user} is online and ready!")


@bot.event
async def on_message(message):
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    # Only respond in the ai-chat channel
    if message.channel.name != CHAT_CHANNEL_NAME:
        await bot.process_commands(message)
        return

    # Ignore commands
    if message.content.startswith("!"):
        await bot.process_commands(message)
        return

    # Show typing indicator
    async with message.channel.typing():
        # Check for image attachments
        image_url = None
        if message.attachments:
            for attachment in message.attachments:
                if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                    image_url = attachment.url
                    break

        # Get response from Claude
        response = await ask_claude(
            str(message.author.id),
            message.content,
            image_url
        )

        # Split long messages
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
    """Ask Claude a question with !ask"""
    async with ctx.typing():
        response = await ask_claude(str(ctx.author.id), question)
        if len(response) > 2000:
            chunks = [response[i:i+2000] for i in range(0, len(response), 2000)]
            for chunk in chunks:
                await ctx.send(chunk)
        else:
            await ctx.send(response)


bot.run(DISCORD_TOKEN)
