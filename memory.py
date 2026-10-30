"""Per-session in-process chat memory."""
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from llm import chain

store = {}
def session_history(session_id: str):
    if session_id not in store:
        store[session_id] = InMemoryChatMessageHistory()
    return store[session_id]

def seed_session_history(session_id, rows):
    history = session_history(session_id)
    if history.messages:
        return
    from langchain_core.messages import HumanMessage, AIMessage
    for row in rows:
        if row.get("user_input") is not None:
            history.add_message(HumanMessage(content=str(row["user_input"])))
        if row.get("ai_response") is not None:
            history.add_message(AIMessage(content=str(row["ai_response"])))

chat_with_memory = RunnableWithMessageHistory(
    chain, session_history, input_messages_key="input", history_messages_key="history"
)
