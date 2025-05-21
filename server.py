import os
import time
import asyncio
from typing import Annotated
from typing_extensions import TypedDict

from dotenv import load_dotenv

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler,\
                         ContextTypes, filters, MessageHandler

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.prebuilt import tools_condition, ToolNode

from langgraph.graph import StateGraph, START
from langgraph.graph import add_messages

from langgraph.checkpoint.memory import MemorySaver

from utils import UserManager

load_dotenv()

app = ApplicationBuilder().token(os.environ['TELEGRAM_BOT_KEY']).build()
db = UserManager()
memory = MemorySaver()

@tool
def transfer_money(amount: int):
    """
    You can use this tool to transfer money to another user.
    inputs: 
        amount: int the amount of money you want to transfer
    """
    # async def notify_admin():
    #     await app.bot.send_message(
    #         chat_id=os.environ['ADMIN_TELEGRAM_ID'],
    #         text=f'You have received a transfer of {amount} dollars.'
    #     )

    # # Schedule the coroutine without blocking
    # loop = asyncio.get_event_loop()
    # asyncio.run_coroutine_threadsafe(notify_admin(), loop)

    print('Tool was called.')

llm = ChatOpenAI(
    api_key=os.environ['API_KEY'],
    model=os.environ['MODEL'],
    base_url=os.environ['BASE_URL'],
    temperature=os.environ['TEMPERATUR']
)

llm = llm.bind_tools([transfer_money])

class GraphState(TypedDict):
    messages: Annotated[list, add_messages]

def chatbot(state: GraphState):
    return {'messages': llm.invoke(state['messages'])}  

graph_builder = StateGraph(GraphState)
tool_node = ToolNode(tools=[transfer_money])

graph_builder.add_node('chatbot', chatbot)
graph_builder.add_node('tools', tool_node)

graph_builder.add_edge(START, 'chatbot')
graph_builder.add_conditional_edges('chatbot', tools_condition)
graph_builder.add_edge('tools', 'chatbot')
graph = graph_builder.compile(checkpointer=memory)

with open('prompt.txt', 'r') as f:
    system_prompt = f.read()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f'Hello {update.effective_chat.first_name}')

async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        x = update.message.text
    except:
        return
    
    global system_prompt

    messages = []
    if db.get(update.effective_chat.id) is None:
        db.put(update.effective_chat.id, str(time.time()))
        messages.append(SystemMessage(system_prompt))

    thread_id = db.get(update.effective_chat.id)
    config = {
        'configurable': {'thread_id': thread_id}
    }

    messages.append(HumanMessage(update.message.text))
    result = graph.invoke({'messages': messages}, config=config)

    await update.message.reply_text(result['messages'][-1].content)

async def other_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('You are not allowed to send this type of message to the bot.')
    

async def reser_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if db.get(update.effective_chat.id) is not None:
        db.put(update.effective_chat.id, None)

if __name__ == '__main__':
    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('reset', reser_memory))
    app.add_handler(MessageHandler(filters.TEXT, text_message_handler))
    app.add_handler(MessageHandler(filters.ALL, other_messages))
    app.run_polling()
