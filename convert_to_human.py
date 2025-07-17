import json

# Replace this with the path to your JSON file
json_file = 'full_session_trace.json'

# Output file
output_file = 'conversation_readable.txt'

def convert_json_to_readable(json_file, output_file):
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # steps = data.get("steps", [])
    for d in data:
        lines = []
        print(d)

        for idx, step in enumerate(d.get("steps", []), 1):
            node = step.get("node", "")
            state = step.get("state", {})

            user_input = state.get("user_input", "")
            
            if node == "memory_node":
                continue
            
            lines.append(f"Step {idx}: Node type → {node}")
            lines.append(f"User: \n{user_input}")

            assistant_response = None
            if node == "thinking_node":
                print("thinking_node")
                if "thinking_output" in state:
                    assistant_response = "\n".join([f"{tk}: {tv}" for tk, tv in zip(state["thinking_output"].keys(), state["thinking_output"].values())])
                    print(assistant_response)
                    lines.append(f"Assistant Thinking:\n{assistant_response}")
            elif node == "conversation_node":
                print("conversation_node")
                if "assistant_response" in state:
                    assistant_response = state["assistant_response"]["kwargs"]["content"]
                    print(assistant_response)
                    lines.append(f"Assistant Response:\n{assistant_response}")
            elif node == "memory_node":
                print("memory node")

            # cbt_insights = state.get("cbt_insights", {})

            # lines.append(f"Step {idx}: Node type → {node}")
            # lines.append(f"User: {user_input}")
            # if assistant_response:
            #     lines.append(f"Assistant: {assistant_response}")

            # if cbt_insights:
            #     lines.append("\n🔍 CBT Insights:")
            #     lines.append(f"- Situation: {cbt_insights.get('situation', '')}")
            #     lines.append(f"- Automatic Thought: {cbt_insights.get('automatic_thought', '')}")
            #     lines.append(f"- Emotion: {cbt_insights.get('emotion', '')}")
            #     distortions = ', '.join(cbt_insights.get('cognitive_distortion', []))
            #     lines.append(f"- Cognitive Distortion(s): {distortions}")
            #     questions = '\n  * '.join(cbt_insights.get('challenge_questions', []))
            #     lines.append(f"- Challenge Questions:\n  * {questions}")
            #     lines.append(f"- Proposed Reframe: {cbt_insights.get('proposed_reframe', '')}")
            #     lines.append(f"- Predicted Emotion Change: {cbt_insights.get('predicted_emotion_change', '')}")
            #     lines.append(f"- Suggested Homework: {cbt_insights.get('suggested_homework', '')}")
            
            lines.append("\n" + "-"*50 + "\n")

    # Write to output file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"✅ Conversion done! File saved as: {output_file}")

if __name__ == "__main__":
    convert_json_to_readable(json_file, output_file)
