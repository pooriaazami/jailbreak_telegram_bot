import os
import time
import asyncio
from typing import Annotated
from typing_extensions import TypedDict
from operator import add

from dotenv import load_dotenv

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler,\
                         ContextTypes, filters, MessageHandler

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
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
    x = llm.invoke(state['messages'])
    if x.response_metadata['token_usage']['total_tokens'] >= int(os.environ['TOKEN_LIMIT']):
        reduced_text = llm.invoke([
            SystemMessage('Your task is to summarize the following conversation between a useful AI agent and a user in the sortest possible amount of tokens.'),
            *state['messages'][1:],
            AIMessage(x.content)
        ])  

        state['messages'] = [SystemMessage(system_prompt + '\nYou have been chating with the user for a while. Here is a quick summary of the chat separated with three backtichs(`): ```{reduced_text.content}```'),]

    return {'messages': x}  

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
    text = result['messages'][-1].content
    if len(text) > 4096:
        for x in range(0, len(text), 4000):  
            await update.message.reply_text(text[x:x+4000])
    else:
        await update.message.reply_text(text)

async def other_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('You are not allowed to send this type of message to the bot.')
    

async def reser_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if db.get(update.effective_chat.id) is not None:
        db.put(update.effective_chat.id, None)
        await update.message.reply_text('Done.')

if __name__ == '__main__':
    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('reset', reser_memory))
    app.add_handler(MessageHandler(filters.TEXT, text_message_handler))
    app.add_handler(MessageHandler(filters.ALL, other_messages))
    app.run_polling()
