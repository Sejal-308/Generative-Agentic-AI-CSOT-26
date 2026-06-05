import os
from openai import OpenAI
from dotenv import load_dotenv
import json
load_dotenv()
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
    
    
)
def call_model(prompt: str) -> str:

    try:
        response = client.chat.completions.create(
        model="openrouter/free",
        messages=[{"role": "user", "content": prompt}])

        
        
       
    except Exception as e:
        print(f"THE API CALL FAILED WITH THIS ERROR: {e}")
    try:
        return response.choices[0].message.content
    except Exception as q:
        print(f'the response has an error: {q}')
    
  
   
if __name__=="__main__":
    print(call_model("What is the capital of ireland?"))