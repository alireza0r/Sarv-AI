import yaml
import google.generativeai as genai
import json
import os
import re

DB_PATH = "db"
if not os.path.exists(DB_PATH):
    os.makedirs(DB_PATH)

class TherapistStateMachine:
    def __init__(self, yaml_path, director_model_name, generator_model_name):
        print("Initializing State Machine (System Instruction Mode)...")
        self._load_config(yaml_path)
        
        DIRECTOR_SYSTEM_INSTRUCTION = """
         You are a silent, high-precision State Machine Controller. Your only function is to select the next state from a list based on the conversation history.

        You must follow the output format EXACTLY. Your response MUST be ONLY the exact state name, enclosed in <choice> XML tags. Do not add any other text, explanation, or punctuation.

        --- EXAMPLE START ---
        [INPUT]
        Current State: PROBLEM_CLARIFICATION
        Available Transitions:
        - State: PROBLEM_EXPLORATION | Condition: "User refutes the summary."
        - State: GOAL_SETTING | Condition: "User confirms the summary."
        User's Last Message: "بله، دقیقا همینه."

        [YOUR RESPONSE]
        <choice>GOAL_SETTING</choice>
        --- EXAMPLE END ---

        You will now receive the real task. Analyze the context and provide your response in the specified format.
        """
        
        GENERATOR_SYSTEM_INSTRUCTION = """
        You are a professional and insightful therapist bot. Your core persona is that of a grounded, confident, and neutral therapist.
        Your primary goal is to provide a clear, non-judgmental space that empowers the user's self-exploration.
        Your communication style is clear, direct, and purposeful. You maintain a calm, steady tone, offering focused insights in concise, conversational responses (typically a few sentences).
        You must adapt your specific approach and tone based on the instructions provided for each turn, while maintaining this core foundation of a stable, non-judgmental presence.
        """
        
        self.director_model = genai.GenerativeModel(
            director_model_name,
            system_instruction=DIRECTOR_SYSTEM_INSTRUCTION
        )
        self.generator_model = genai.GenerativeModel(
            generator_model_name,
            system_instruction=GENERATOR_SYSTEM_INSTRUCTION
        )
        
        self.current_state_name = self.config.get('initial_state', 'GREETING_AND_INTRODUCTION')
        print(f"Initial state set to: {self.current_state_name}")
        self.summary=""
    def _load_config(self, yaml_path):
        with open(yaml_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)['state_machine']
        self.states = {s['state']['name']: s['state'] for s in self.config['states']}
        print("Configuration loaded successfully.")
        
    def get_initial_message(self, user_id):
      self.user_id = user_id
      user_db_file = os.path.join(DB_PATH, f"{user_id}.json")
      
      current_config = self.states[self.current_state_name]['operation']['config']
      
      if os.path.exists(user_db_file):
          try:
              with open(user_db_file, 'r', encoding='utf-8') as f:
                  data = json.load(f)
          except (json.JSONDecodeError, FileNotFoundError):
              return current_config.get('text', 'سلام. مشکلی در بازیابی جلسه قبل پیش آمد. بیایید از نو شروع کنیم.')

          summary_text = data.get("sessionSummary", "خلاصه‌ای یافت نشد.")
          action_plan = data.get("actionPlan", "تمرین مشخصی تعیین نشده بود.")
          self.summary=summary_text

          initial_message_template = current_config.get('text_template')
          if initial_message_template:
              
              return initial_message_template.format(summary=summary_text, action_plan=action_plan)
          else:
              return f"سلام مجدد. خوشحالم که برگشتید. آماده‌اید ادامه دهیم؟"
      else:
          return current_config.get('text', 'سلام. خوش آمدید.')

    async def _choose_next_state(self, director_session,user_input):
        current_state_config = self.states[self.current_state_name]
        options_str = "\n".join([f"- State: {next_state['state']}\n  Condition: {next_state['condition']}" for next_state in current_state_config['next_states']])
        
        prompt = f"""
        Current State: {self.current_state_name}
        
        Your options for the next state are:
        {options_str}

        User's Last Message: "{user_input}"
        
        Based on the full conversation history, choose the next state. Respond with ONLY the state name.
        """
        
        response = await director_session.send_message_async(prompt)
        raw_text = response.text.strip()
        match = re.search(r'<choice>(.*?)</choice>', raw_text)
        
        if match:
            next_state_name = match.group(1).strip()
            print(f"Director chose state (via XML): {next_state_name}")
        else:
            print(f"Warning: Director did not use <choice> tags. Using raw response: '{raw_text}'")
            next_state_name = raw_text.splitlines()[0].strip()

        if next_state_name not in self.states:
            print(f"Error: Director returned an invalid state name '{next_state_name}'. Staying in current state.")
            return self.current_state_name
            
        return next_state_name

    async def _generate_response(self, generator_session,user_input):
        state_config = self.states[self.current_state_name]
        prompt_config = state_config['operation']['config'].get('prompt')

        if not prompt_config:
            return state_config['operation']['config']['text']

        prompt = f"""
        User's Last Message: "{user_input}"
        INSTRUCTION FOR THIS TURN:
        Your Persona: {prompt_config['persona']}
        Your Goal Right Now: {prompt_config['primary_goal']}
        Your Instructions:
        - {'\n- '.join(prompt_config['instructions'])}
        Your Tone: {prompt_config['tone']}
        
        Now, generate your response.
        """
        response = await generator_session.send_message_async(prompt)
        return response.text

    async def _summarize_session(self, full_history):
        summarizer_model = genai.GenerativeModel('gemini-2.5-flash')
        history_str = "\n".join([f"{msg.role}: {msg.parts[0].text}" for msg in full_history])
        
        prompt = f"""
        Analyze the following therapy session transcript and extract key information into a structured JSON object. 
        Adhere strictly to the requested format in farsi.

        [CONVERSATION]
        {history_str}

        [OUTPUT_FORMAT]
        {{
          "sessionSummary": "in farsi A brief, one-paragraph summary of the main topics discussed, insights gained, and the client's emotional state and the task we set for client",
          "keyInsights": [
            "in farsi A list of the most important realizations or breakthroughs for the client."
          ],
          "actionPlan": "in farsi The homework or task the client agreed to for the next session. If none, state 'No specific action plan was set.'."
        }}
        """
        
        response = await summarizer_model.generate_content_async(prompt)
        try:
            clean_json_str = response.text.strip().replace("```json", "").replace("```", "")
            summary_data = json.loads(clean_json_str)
            return summary_data
        except json.JSONDecodeError:
            print("Error: Failed to decode summary JSON. Saving as plain text.")
            return {"sessionSummary": response.text, "actionPlan": "Could not parse."}

    def _save_session_summary(self, summary_data):
        user_db_file = os.path.join(DB_PATH, f"{self.user_id}.json")
        with open(user_db_file, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, ensure_ascii=False, indent=2)
        print(f"Final session summary saved for user {self.user_id}.")


    async def step(self, director_session, generator_session,user_input):

        next_state_name = await self._choose_next_state(director_session,user_input)
        print(next_state_name)
        self.current_state_name = next_state_name
        
        if self.current_state_name == "END_SESSION":
            summary = await self._summarize_session(director_session.history)
            self._save_session_summary(summary)
            final_message = self.states["END_SESSION"]['operation']['config']['text']
            return final_message, True
            
        bot_response = await self._generate_response(generator_session,user_input)
        
        return bot_response, False