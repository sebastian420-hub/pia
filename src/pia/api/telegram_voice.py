import os
import asyncio
from loguru import logger
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from dotenv import load_dotenv
from openai import OpenAI
import json

from pia.api.mcp_server import mcp  # We can import the tools directly if in the same repo

load_dotenv()

# --- CONFIGURATION ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_IDS = [int(i) for i in os.getenv("ALLOWED_TELEGRAM_USER_IDS", "").split(",") if i]
MODEL = os.getenv("LLM_MODEL", "z-ai/glm-4.5-air:free")

# LLM Client for reasoning
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    default_headers={
        "HTTP-Referer": "https://github.com/google/gemini-cli",
        "X-Title": "PIA-Telegram-Voice"
    }
)

from datetime import datetime

class TacticalEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle specialized PIA data types like datetimes."""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        return super().default(obj)

class TelegramVoice:
    def __init__(self):
        self.system_prompt = """
        You are the Tactical Voice of the Personal Intelligence Agency (PIA).
        Your job is to assist the Director by using the available MCP tools to query the intelligence database.
        
        Available Tools:
        - search_spatial(lat, lon, radius_km): Use when asked about danger or events near a location.
        - get_entity_network(name, hops): Use when asked about connections or who someone is.
        - get_active_clusters(limit): Use for a general situation report.
        - get_cluster_details(cluster_id): Use for deep dives into a specific situation.
        - get_system_health(): Use to check agent/DB status.
        - submit_tasking(instruction): Use when the Director gives a direct order or task.

        Rules:
        1. If the user's intent matches a tool, output ONLY a JSON call: {"tool": "tool_name", "args": {...}}
        2. If you have tool results, summarize them tactically for a Director on a mission.
        3. If no tool is needed, respond briefly and professionally.
        """

    async def get_reasoning(self, user_text: str, context_history: list = []):
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(context_history)
        messages.append({"role": "user", "content": user_text})
        
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.1
        )
        return response.choices[0].message.content

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in ALLOWED_IDS:
            logger.warning(f"Unauthorized access attempt by ID: {user_id}")
            await update.message.reply_text("Access Denied. Identity not recognized.")
            return

        user_text = update.message.text
        logger.info(f"Director {user_id}: {user_text}")
        
        try:
            # 1. Ask LLM what to do
            reasoning = await self.get_reasoning(user_text)
            
            # 2. Check for Tool Call
            try:
                call = json.loads(reasoning)
                if "tool" in call:
                    tool_name = call["tool"]
                    args = call.get("args", {})
                    
                    await update.message.reply_text(f"📡 Executing: {tool_name}...")
                    
                    # Execute tool directly using the imported mcp instance
                    from pia.api import mcp_server
                    tool_func = getattr(mcp_server, tool_name, None)
                    
                    if tool_func:
                        result = tool_func(**args)
                        # 3. Feed results back to LLM for tactical summary
                        # Use the TacticalEncoder to safely stringify datetimes and objects
                        serialized_result = json.dumps(result, cls=TacticalEncoder)
                        summary_prompt = f"Here are the raw results from {tool_name}: {serialized_result}. Provide a concise tactical summary for the Director."
                        final_response = await self.get_reasoning(summary_prompt, context_history=[{"role": "user", "content": user_text}, {"role": "assistant", "content": reasoning}])
                        await update.message.reply_text(final_response, parse_mode="Markdown")
                    else:
                        await update.message.reply_text(f"Error: Tool {tool_name} not found.")
                else:
                    await update.message.reply_text(reasoning)
            except json.JSONDecodeError:
                # Not a tool call, just a chat response
                await update.message.reply_text(reasoning)
        except Exception as e:
            logger.error(f"Error in handle_message: {e}")
            if "429" in str(e):
                await update.message.reply_text("⚠️ [SYSTEM ALERT]: The Agency's brain is currently rate-limited by the provider. Please stand by for 60 seconds.")
            else:
                await update.message.reply_text(f"❌ [CRITICAL ERROR]: {str(e)}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("PIA Tactical Voice Online. Standing by, Director.\n\nCommands:\n/mission [Category] [Keywords] - Set new focus\n/missions_active - List current focuses")

async def set_mission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ALLOWED_IDS: return
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: /mission [Category] [Keyword1,Keyword2,...]")
        return
        
    category = context.args[0].upper()
    keywords = context.args[1].split(",")
    
    from pia.api.mcp_server import db
    db.execute_query(
        "INSERT INTO mission_focus (category, keywords, is_active) VALUES (%s, %s, TRUE)",
        (category, keywords)
    )
    
    await update.message.reply_text(f"🎯 Mission Activated: {category}\nFocusing on: {', '.join(keywords)}")

async def list_missions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ALLOWED_IDS: return
    
    from pia.api.mcp_server import db
    active = db.execute_query("SELECT category, keywords FROM mission_focus WHERE is_active = TRUE", fetch=True)
    
    if not active:
        await update.message.reply_text("No active missions. The Agency is in general surveillance mode.")
        return
        
    response = "📡 Current Active Missions:\n"
    for m in active:
        response += f"- {m['category']}: {', '.join(m['keywords'])}\n"
    await update.message.reply_text(response)

if __name__ == '__main__':
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment.")
        exit(1)
        
    voice = TelegramVoice()
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('mission', set_mission))
    app.add_handler(CommandHandler('missions_active', list_missions))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), voice.handle_message))
    
    logger.info("Telegram Tactical Voice bot starting...")
    app.run_polling()
