import logging
from strands import Agent

import sys
sys.stdout.reconfigure(encoding='utf-8')

#TODO: import python_repl, file_write
## Python_repl KO sur windows
# from strands_tools import python_repl, file_write
from strands_tools import file_write

#TODO: Enable Strands debug log level

logging.getLogger("strands").setLevel(logging.DEBUG)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler()]
)

from strands.models.openai import OpenAIModel

model = OpenAIModel(
    model_id="gpt-5.4",   # ou le nom de ton deployment Foundry
    client_args={
        "base_url": "https://rg-ava-poc-ia-foundry.cognitiveservices.azure.com/openai/v1/",
        "api_key": "",
    },
)

# Your magical creation here
arcane_scribe = Agent(
    #tools= #TODO: add the tools
    tools=[
        file_write,
        #python_repl
    ],
    model=model,
    system_prompt="""You are Kiro the Grey Hat, a wizard who specializes in the ancient art of code magic. 
    When asked to create spells (code), you inscribe them on parchment (files) and then cast them to demonstrate their power."""
)

response = arcane_scribe("Create a magical scroll that generates the first 10 numbers of the Fibonacci sequence and demonstrate its power!")
# à exécuter depuis cmd ou powershell