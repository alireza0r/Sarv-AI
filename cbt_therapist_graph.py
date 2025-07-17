"""
CBT Therapist Multi‑Session Agent built with LangGraph.

This file defines:
1. Full PromptTemplates for the thinking (reasoning) and conversation layers.
2. Node callbacks that use those prompts with an LLM.
3. A graph with three nodes (thinking → conversation → update_memory) that can be called
   repeatedly across multiple sessions, persisting therapeutic insights.

Replace `YOUR_MODEL` with your preferred ChatOpenAI / local LLM constructor.
"""

from __future__ import annotations

# from langchain.chat_models import ChatOpenAI  # or any LCEL‑compatible model
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers.json import JsonOutputParser
# from langchain.output_parsers import JsonOutputParser
from langchain.schema import BaseMessage
from langgraph.graph import Graph
from typing import Dict, Any
from dotenv import load_dotenv
load_dotenv()

################################################################################
# 0. LOGGER
################################################################################
session_trace = {"steps": []}  # ← global per session
def track_node_execution(node_name: str):
    def decorator(func):
        def wrapper(state: Dict[str, Any]):
            result = func(state)
            snapshot = {
                "node": node_name,
                "state": result.copy()  # shallow copy to avoid mutation
            }
            session_trace["steps"].append(snapshot)
            return result
        return wrapper
    return decorator

################################################################################
# 1. PROMPT TEMPLATES
################################################################################

# ──────────────────────────────────────────────────────────────────────────────
# THINKING PROMPT (Reasoning Layer)
# ──────────────────────────────────────────────────────────────────────────────
# cbt_thinking_prompt = PromptTemplate(
#     input_variables=[
#         "session_stage",
#         "user_input",
#         "user_profile",
#         "conversation_history",
#         "cbt_insights",
#     ],
#     template="""
# You are an expert CBT (Cognitive Behavioral Therapy) therapist model guiding the *thinking* layer of a multi‑stage dialogue system.
# You will reason step‑by‑step about the user input and produce structured JSON.

# ---
# 🔷 Context
# Session stage: {session_stage}
# User profile: {user_profile}
# Previous CBT insights: {cbt_insights}
# Dialogue history: {conversation_history}

# 🔷 New user input
# "{user_input}"

# ---
# 🔶 Thinking steps (follow exactly):
# 1. Identify the user situation (A). If session_stage is "first_session", assume no prior context and treat this as rapport‑building. If "ongoing", use past insights.
# 2. Extract the automatic negative thought (B).
# 3. Identify the emotional reaction (C).
# 4. Detect cognitive distortions (list).
# 5. Generate 2–3 Socratic challenge questions (D).
# 6. Produce **proposed_reframe** = a realistic, balanced alternative thought the user *might* adopt.
#    ⚠️ This is only a suggestion. The conversation layer must *first* invite the user to create their own reframe.
# 7. Predict how the emotion might shift if the new thought is adopted.
# 8. Propose a small homework task (optional).

# ---
# 📤 Output JSON keys (required):
# situation, automatic_thought, emotion, cognitive_distortion, challenge_questions, proposed_reframe, predicted_emotion_change, suggested_homework
# """
# )




# V2
cbt_thinking_prompt = PromptTemplate(
    input_variables=[
        "session_stage",
        "user_input",
        "user_profile",
        "conversation_history",
        "cbt_insights",
    ],
    template="""
You are an expert CBT (Cognitive Behavioral Therapy) therapist model guiding the *thinking* layer of a multi‑stage dialogue system.
You will reason step‑by‑step about the user input and produce structured JSON.

Your main goals:
✅ Deeply explore and clarify the user's current issue before moving to any new topic.
✅ Specifically ask and reflect on:
• What exactly happened to the user.
• What feelings it caused.
• Any physical or psychological symptoms that appeared.
• What thoughts came to mind in that situation.
• What consequence or outcome followed.
⚠️ Do **not** add or switch to a new topic until the current issue is fully explored.

---
🔷 Context
Session stage: {session_stage}
User profile: {user_profile}
Previous CBT insights: {cbt_insights}
Dialogue history: {conversation_history}

🔷 New user input
"{user_input}"

---
🔶 Thinking steps (follow exactly):
1. Identify and describe in detail the user situation (A): what happened, what feelings it caused, what physical or mental symptoms appeared, what thoughts came to mind, and what the consequence was.  
   If session_stage is "first_session", assume no prior context and treat this as rapport‑building. If "ongoing", use past insights.
2. Extract the automatic negative thought (B).
3. Identify the emotional reaction (C).
4. Detect cognitive distortions (list).
5. Generate 2–3 Socratic challenge questions (D) that help the user reflect more deeply.
6. Produce **proposed_reframe** = a realistic, balanced alternative thought the user *might* adopt.
   ⚠️ This is only a suggestion; the conversation layer must *first* invite the user to propose their own reframe.
7. Predict how the emotion might shift if the new thought is adopted.
8. Propose a small homework task (optional).

---
📤 Output JSON keys (required):
situation, automatic_thought, emotion, cognitive_distortion, challenge_questions, proposed_reframe, predicted_emotion_change, suggested_homework
"""
)




# ──────────────────────────────────────────────────────────────────────────────
# CONVERSATION PROMPT (Dialogue Layer)
# ──────────────────────────────────────────────────────────────────────────────
# cbt_conversation_prompt = PromptTemplate(
#     input_variables=[
#         "user_input",
#         "thinking_output",
#         "session_stage",
#         "conversation_history",
#         "user_profile",
#     ],
#     template="""
# You are the *conversation* layer of a CBT therapeutic assistant. Analysis is complete; your job is to interact warmly in Persian (use English only for technical terms).

# ---
# 🔷 State
# Session stage: {session_stage}
# User profile: {user_profile}
# Dialogue history: {conversation_history}

# 🔷 Latest user input
# "{user_input}"

# 🔷 Guidance from thinking layer
# ```json
# {thinking_output}
# ```

# ---
# 🔶 How to proceed
# 1. Validate the user's feeling(s).
# 2. Explore the situation and automatic thought.
# 3. Ask ONE Socratic question at a time from `challenge_questions`.
# 4. Invite the user to craft their own balanced thought.
# 5. If the user struggles, *offer* `proposed_reframe` as an example, never as an order.
# 6. Confirm the final `accepted_reframe` and note the emotional shift.
# 7. Offer `suggested_homework` if rapport is sufficient.
# 8. Keep tone empathic, non‑judgmental, conversational.
# """
# )



cbt_conversation_prompt = PromptTemplate(
    input_variables=[
        "user_input",
        "thinking_output",
        "session_stage",
        "conversation_history",
        "user_profile",
    ],
    template="""
You are the *conversation* layer of a CBT therapeutic assistant.
The thinking layer already did the analysis; your job is to use that guidance to talk naturally and warmly in Persian (use English only for technical terms).

⚠️ Important:
- Follow the guidance from thinking_output closely; do **not** add new analysis or topics.
- Avoid starting your reply with generic validation sentences like “متوجه هستم…” or “کاملاً طبیعی‌ست…”.
- Instead, weave validation naturally into the dialogue when it feels appropriate.
- Keep the tone friendly, human, and non‑judgmental — sound more like a caring friend than a formal therapist.
- Answer short as much as possible.

---
🔷 State
Session stage: {session_stage}
User profile: {user_profile}
Dialogue history: {conversation_history}

🔷 Latest user input
"{user_input}"

🔷 Guidance from thinking layer
```json
{thinking_output}

""")

################################################################################
# 2. LLM & OUTPUT PARSER
################################################################################

llm = ChatOpenAI(model_name="gpt-4o", temperature=0.3)  # ← swap with your model
json_parser = JsonOutputParser()

################################################################################
# 3. GRAPH NODE CALLBACKS
################################################################################

@track_node_execution("thinking_node")
def thinking_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Run the reasoning layer and attach its JSON output to state."""
    session_stage = "first_session" if not state["memory"].get("history") else "ongoing"
    chain = cbt_thinking_prompt | llm | json_parser
    thinking_output = chain.invoke({
        "session_stage": session_stage,
        "user_input": state["user_input"],
        "user_profile": state["memory"].get("user_profile", ""),
        "conversation_history": state["memory"].get("history", ""),
        "cbt_insights": state["memory"].get("cbt_insights", ""),
    })
    state["thinking_output"] = thinking_output
    state["session_stage"] = session_stage
    print("thinking finished")
    print(state)
    return state


@track_node_execution("conversation_node")
def conversation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Hold a conversational turn using guidance from thinking layer."""
    chain = cbt_conversation_prompt | llm
    assistant_response: str = chain.invoke({
        "user_input": state["user_input"],
        "thinking_output": state["thinking_output"],
        "session_stage": state["session_stage"],
        "conversation_history": state["memory"].get("history", ""),
        "user_profile": state["memory"].get("user_profile"),
    })
    state["assistant_response"] = assistant_response
    print("conversation_node finished")
    print(state)
    return state


@track_node_execution("memory_node")
def update_memory_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Persist history and accepted reframes for future sessions."""
    mem = state["memory"]
    # Append plain text history
    hist = mem.get("history", "")
    new_turn = f"\nUser: {state['user_input']}\nAssistant: {state['assistant_response']}"
    mem["history"] = hist + new_turn

    # Extract accepted reframe if conversation node marked it by a special tag
    if "accepted_reframe:" in state["assistant_response"]:
        accepted = state["assistant_response"].split("accepted_reframe:")[-1].strip()
        mem.setdefault("accepted_reframes", []).append(accepted)
    
    # Store last thinking output for insight reference
    mem["cbt_insights"] = state["thinking_output"]
    state["memory"] = mem
    print("update_memory_node finished")
    print(state)
    return state

################################################################################
# 4. BUILD GRAPH
################################################################################

graph = Graph()

graph.add_node("thinking", thinking_node)

graph.add_node("conversation", conversation_node)

graph.add_node("update_memory", update_memory_node)

# linear flow: thinking → conversation → update_memory → (end)

graph.set_entry_point("thinking")
graph.add_edge("thinking", "conversation")
graph.add_edge("conversation", "update_memory")
graph.set_finish_point("update_memory")

cbt_agent = graph.compile()

################################################################################
# 5. Gradio (optional)
################################################################################
import json
from langchain.load.dump import dumps
memory: Dict[str, Any] = {}
def conv(query):
    global memory
    # print("🧠 CBT Therapist Agent (multi‑session)\nType 'exit' to quit.\n")
    user_input = query
    state = {"user_input": user_input, "memory": memory}
    result = cbt_agent.invoke(state)
    memory = result["memory"]
    print("*"*30)
    print(f"🤖: \n{result}\n")

    with open("full_session_trace.json", "a", encoding="utf-8") as f:
        json.dump(json.loads(dumps(session_trace, ensure_ascii=False)), f, ensure_ascii=False)

    return result['assistant_response'].content

################################################################################
# 6. COMMAND‑LINE DEMO (optional)
################################################################################

if __name__ == "__main__":
    # from pprint import pprint
    # print("🧠 CBT Therapist Agent (multi‑session)\nType 'exit' to quit.\n")
    # memory: Dict[str, Any] = {}
    # while True:
    #     user_input = input("👤: ")
    #     if user_input.lower() in {"exit", "quit"}:
    #         break
    #     state = {"user_input": user_input, "memory": memory}
    #     result = cbt_agent.invoke(state)
    #     memory = result["memory"]
    #     print("*"*30)
    #     print(f"🤖: {result['assistant_response'].content}\n")

    import gradio as gr
    demo = gr.Interface(fn=conv, inputs="textbox", outputs='textbox')
    demo.launch(share=True)
