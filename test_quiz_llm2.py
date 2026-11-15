from llm import profile_client
from quiz import templates

system = templates.GEN_SYS.format(
    topic="Artificial intelligence", difficulty="medium", count=10,
    kind_label=templates.MCQ_LABEL, kind_rules=templates.MCQ_RULES,
    source_rule=templates.KNOWLEDGE_RULE, student_brief="Name: judah",
    avoid="none", context="(none)",
) + "\n\nReturn ONLY one valid JSON object with a 'subject' string and a 'questions' list."

r = profile_client.invoke([("system", system), ("human", templates.GEN_HUMAN)])
print("CONTENT:", repr(r.content[:200]))
print("FINISH:", r.response_metadata.get("finish_reason"))
print("TOKENS:", r.response_metadata.get("token_usage"))