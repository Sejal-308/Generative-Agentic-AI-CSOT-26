import os
from openai import OpenAI
from dotenv import load_dotenv
import json
load_dotenv()

class ChatAgent:
    def __init__(self, model, max_turns, system_prompt):
        self.model=model

        self.messages=[{"role": "system", "content": system_prompt}]

        self.max_turns=max_turns

        self.client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],)
    
    
    def chat(self, user_input: str) -> str:

        user_turns=(len(self.messages)-1)//2

        if user_turns==self.max_turns:
            self.summarize()
        
        self.messages.append({"role": "user", "content": user_input})

        response = self.client.chat.completions.create(
        model=self.model,
        messages=self.messages)

        reply=response.choices[0].message.content   
      
        self.messages.append({"role": "assistant","content": reply}) 

        return reply
    def summarize(self):
        system_prompt = self.messages[0:1]
        newest_messages = self.messages[-10:] 
        old_messages = self.messages[1:-10]  
        
        
        convo_str = str(old_messages)
        summary = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": "Accurately summarize this conversation. " + convo_str}]
            )
        summary_text = summary.choices[0].message.content
        summary_msg = [{'role': 'assistant', 'content': "Previous conversation summary: "+summary_text}]
        

        
        self.messages = system_prompt + summary_msg + newest_messages

def run_chatbot():
     print("Chat started. Type 'exit' to quit.\n")
     agent=ChatAgent(model="openrouter/free", max_turns=10, system_prompt="you are a helpful and concise assistant")
     while True:
       user_input=input("enter prompt: ")
       if user_input=='exit':
           print('exiting chat. see you later!')
           
           break
      
       try:
            
            reply = agent.chat(user_input)
            print(reply)
       except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    run_chatbot()
       







        
        

    
    
