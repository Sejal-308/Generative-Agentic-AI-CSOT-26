I'm new to the github interface so firstly it took me a while to clone the repository and figure out what the task actually was. Ultimately, I understood that i need to complete build1 and build2 like fill in the blanks (and also explore and understand the meaning of those codes) and then use what I've learnt to create a class called ChatAgent and create a chatbot using that.

Build1.py: it was quite interesting to explore the 'responses' variable. by printing response.choices i could literally see what the ai was thinking, and response.usage told me how much each of my prompts was costing. it has actually made me type my prompts more cautiously now, free limits are becoming increasingly precious!!

Build2.py: I found this even simpler. After understanding build1 all I had to do was type some simple commands in python as per the TODO comments given!

Main Issue: the main issue i have is that currently i use 'openrouter/free' which is not a single model exactly, it just goes to openrouter and whichever ai agent is available that agent was answering my prompts (i also print response.model to see which models are answering). but whenever i type a single model i would repeatedly get 'no end points found' error. i just could not figure out why. i tried many solutions but nothing worked. 

Privacy of the API Key: even though we used free keys, i have a fair understanding of why api keys shouldn't be made public. if someone has access to my key they are essentially using my money to gain access to ai agents! (if i start using a paid key ofcourse)

chatbot.py: i created a ChatAgent class with two methods: first one simply calls the ai model and genreates a response and the second (most interesting one) was the summarize. then i simply write a function which asks for the user input (prompt) and then uses a ChatAgent variable to answer and summarize whenever the specified maximum turns are reached. 

**SUMMARIZE**: first what i implemented was that after 5 turns, we would drop the oldest question-answer, summarize the next three and leave the last one as it is. It was pretty decent but removing the conversations (and eventually whole summaries) wasn't a good idea for accurate responses. so finally what the current summarize method does is that it leaves system prompt and the recent 10 turns as it is, and between those two things whatever is there it summarizes. that felt slightly better. i think it can still improve but i wasn't able to go beyond this point :'(
    