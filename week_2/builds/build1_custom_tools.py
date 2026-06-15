"""
Build 1: Custom Tool Call Parser
=================================
Before modern SDKs handled tool calls natively, developers used custom text formats
that the model was prompted to emit. This build has you implement that pattern from
scratch: prompt the model to emit tool calls in a structured format, parse them, run
the corresponding Python function, and feed the result back.

This is NOT the production way to do it (Build 2 is). But doing it manually first
makes the mechanics obvious. The SDK is doing exactly this, just more robustly.

The format we'll use:
    The model emits tool calls wrapped in <tool_call> tags, like:

        I need to read the file first.

        <tool_call>
        {"name": "read_file", "arguments": {"path": "notes.txt"}}
        </tool_call>

    Your code finds the tag, parses the JSON, runs the function, and injects
    the result back as a <tool_response> in the next message.

Tasks:
  1. Complete `parse_tool_call` to extract name + arguments from a model response
  2. Complete `dispatch` to route a tool call to the right Python function
  3. Complete `run_agent` to implement the back-and-forth loop

Tools to implement:
  - read_file(path: str) -> dict    reads a file from disk and returns its content
  - write_file(path: str, content: str) -> dict    writes content to a file on disk

Before running, create a file called `sample.txt` with some text in it.
"""

import os
import re
import json
import sys
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)

MODEL = "openrouter/free"

SYSTEM_PROMPT = """You are a helpful file assistant with access to the following tools:

- read_file(path: str): reads a file from disk and returns its content
- write_file(path: str, content: str): writes content to a file on disk

When you need to use a tool, emit EXACTLY this format and nothing else after it:

<tool_call>
{"name": "TOOL_NAME", "arguments": {"arg1": "value1"}}
</tool_call>

After you receive the tool result in a <tool_response> block, continue your response
normally. Do not emit a tool_call and prose in the same turn. Pick one or the other.
"""

# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def read_file(path: str) -> dict:
    try:
        with open(path, 'r') as file:
            content=file.read()
            return {"content":content, "path": path}
            
    except Exception as e:
        return {"error": str(e)}
        

    """
    Read a file from disk and return its content.
    Return {"content": ..., "path": ...} on success.
    Return {"error": ...} if the file doesn't exist or can't be read.
    """
    # TODO: implement using open() in a try/except
   


def write_file(path: str, content: str) -> dict:
    try:
        with open(path, 'w') as f:
            f.write(content)
            size=os.path.getsize(path)
            return {"success": True, "path": path, "bytes_written": size}
            
    except Exception as e:
        return {"error": str(e)}
        

    """     
    Write content to a file on disk.
    Return {"success": True, "path": ..., "bytes_written": ...} on success.
    Return {"error": ...} on failure.

    Hint: open(path, 'w') and then f.write(content).
    """
    # TODO: implement
    


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse_tool_call(response_text: str) -> dict | None:


    pattern = r"<tool_call>\s*(\{.*?\})\s*</tool_call>"
    match = re.search(pattern,response_text, re.DOTALL)
    if match:
        try:
            json_str = match.group(1)
            data = json.loads(json_str)
            return data
        except Exception as e:
            print("error: ", e)
            return None 

    else:
        return None


    """
    Extract a tool call from the model's response text.

    Returns a dict {"name": str, "arguments": dict} if a <tool_call> block is found,
    or None if there is no tool call in the response.

    The format to parse:
        <tool_call>
        {"name": "...", "arguments": {...}}
        </tool_call>

    Hint: use re.search() with re.DOTALL to find the block, then json.loads() the body.
    """
    # TODO: implement
   


def strip_tool_call(response_text: str) -> str:
    clean_response=re.sub(r"<tool_call>.*?</tool_call>","",response_text, flags=re.DOTALL )
    return clean_response.strip()


    """
    Return the response text with any <tool_call>...</tool_call> block removed.
    Useful for printing the model's prose without the raw tag.
    """
    # TODO: implement (re.sub is your friend)
    


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

TOOL_REGISTRY = {
    "read_file": read_file,
    "write_file": write_file,
}

def dispatch(name: str, arguments: dict) -> str:
    try:
        if name=="read_file":
            r_dict=read_file(arguments["path"])
            return json.dumps(r_dict)
        elif name=="write_file":
            w_dict=write_file(arguments["path"], arguments["content"])
            return json.dumps(w_dict)
        else:
            error={"error": f"Unknown tool: {name}"}
            return json.dumps(error)
            
    except Exception as e:
        exception={"error": str(e)}
        return json.dumps(exception)
        

    """
    Look up the tool by name, call it with the given arguments, and return a
    JSON string of the result.

    If the tool is not found, return: {"error": "Unknown tool: <name>"}
    If the call raises an exception, return: {"error": "<exception message>"}

    Always return a string (json.dumps the result dict).
    """
    # TODO: implement
    


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

MAX_ITERATIONS = 6



def run_agent(user_message: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    for iteration in range(MAX_ITERATIONS):
        # 1. Call the model
        response = client.chat.completions.create(
            model=MODEL, # Use the global MODEL variable you defined earlier
            messages=messages
        )
        
        # Extract the text and immediately append the assistant's response to history
        model_text = response.choices[0].message.content
        messages.append({"role": "assistant", "content": model_text})

        # 2. Parse for a tool call
        tool_call_data = parse_tool_call(model_text)

        # 3. Exit Condition: No tool call found
        if not tool_call_data:
            return strip_tool_call(model_text)
            
        # 4. Dispatch Phase: Tool call found
        tool_name = tool_call_data.get("name")
        tool_args = tool_call_data.get("arguments")
        
        # Print diagnostic to stderr as requested
        print(f"-> Agent called tool: {tool_name}", file=sys.stderr)
        
        # Run the tool
        tool_result = dispatch(tool_name, tool_args)
        
        # 5. Feed the results back
        formatted_response = f"<tool_response>\n{tool_result}\n</tool_response>"
        messages.append({"role": "user", "content": formatted_response})
        
        # The loop now restarts, sending the updated history back to the model!

    return f"[Agent stopped after {MAX_ITERATIONS} iterations]"
# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Create a sample file for the agent to work with
    with open("sample.txt", "w") as f:
        f.write("IIT Delhi was established in 1961. It is one of the premier engineering institutions in India.\n")
        f.write("The campus spans 325 acres in Hauz Khas, New Delhi.\n")

    test_queries = [
        "Read sample.txt and summarise what it says.",
        "Read sample.txt and write a one-sentence version of its content to summary.txt.",
    ]

    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print(f"{'='*60}")
        result = run_agent(query)
        print(f"Answer: {result}")
