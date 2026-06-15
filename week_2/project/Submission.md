Overall this week the workflow looked like: understanding the concept and codes line by line in the .md files. Then start working on the builds using the sample codes and starter script as a base. There were various new terms so it took alot of time

I downloaded all packages and dependencies inside a virtual environment. 

Build1: To understand what tools are, how they are fed into the model, how the response is scanned for tool calls and error handling. Instead of the model just generating conversational prose, the model was now able to indicate which tool it wants to execute and with what arguments. Rather than stopping after a single question and answer, the loop terminates only when model thinks it has sufficient info

Build2: in build1 we had to instruct the model to format its tool calls in a very specific way so that our function could identify, parse and strip them. the manual identification, stripping and parsing is handled by Native SDK Tool Calling Approach

Build3: The TUI makes the chatbot more interactive and 'realistic' by incorporating asynchronous operations and an interactive interface. the terminal doesn't feel dead even while the response is being processed

Agent: The most crucial addition to the tool calling, web search, url fetching was the MCP servers. Now all the MCP tools and local tools that were inside my script (web search, fetching info from urls) and to be combined into a single schema. The agent loop itself ran inside the _get_response function of the Chatapp class. An important modification was that OpenAI was replaced with AsyncOpenAI to accomodate asynchronous operations, so that the UI doesn't freeze