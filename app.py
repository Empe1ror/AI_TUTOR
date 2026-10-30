from memory import chat_with_memory
from db import db, Database

print("---Welcome to AI Tutor---")
user_id = input("Enter your name: ").lower()
database = Database(db, user_id)
session_id = database.get_session_id()
print(f"Session ID: {session_id}")

conversations = database.get_conversations()

if database.get_student_profile() is None:
    database.create_student_profile(user_id)
while True:
    user_input = input("user : ")

    if user_input.lower() == "exit":
        database.update_student_profile(session_id)
        break


    response = chat_with_memory.invoke(
        {"student_profile": str(database.get_student_profile()),
        "input": user_input},
        config={
            "configurable": {
                "session_id": session_id
            }
        }
    )

    print("AI:", response) 

    history =[]
    history.append(
        {
            "user_input": user_input,
            "ai_response": response
        }
    )

    database.add_conversation(session_id, history)