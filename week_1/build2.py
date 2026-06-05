import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)

def run_chatbot():
    prev_response=None
    """
    A terminal chatbot that holds a coherent multi-turn conversation.

    Your implementation should:
    - Start with a system message that sets the assistant's behaviour.
    - Maintain a `messages` list with alternating user/assistant turns.
    - Append the assistant's reply to `messages` after each call.
    - Resend the full history on every API call.
    - Allow the user to type 'exit' or 'quit' to end the session.

    Stretch:
    - Add a '/reset' command that clears history so you can feel context loss live.
    - Add a '/tokens' command that prints response.usage after the last call.
    """
    messages = [
        {"role": "system", "content": "You are a helpful assistant who gives short answers."}
    ]

    print("Chat started. Type 'exit' to quit.\n")

    while True:
       prompt=input() # TODO: take user input
       if prompt=='exit':
           print('exiting chat. see you later!')
           print('Total tokens used in this chat: ', prev_response.usage.total_tokens)
           break

       messages.append({"role": "system", "content": prompt}) # TODO: append the user turn to messages

       response = client.chat.completions.create(
        model="openrouter/free",
        messages=messages)   # TODO: call the API with the full messages list
       prev_response=response      
       reply=response.choices[0].message.content    # TODO: extract the assistant's reply
      
       messages.append({"role": "system","content": reply})   # TODO: append the assistant turn to messages

       print(reply) 
       print('The model which answered this prompt was', response.model) # TODO: print the reply
       
        

if __name__ == "__main__":
    run_chatbot()
