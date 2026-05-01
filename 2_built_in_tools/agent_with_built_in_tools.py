from strands import Agent

import logging
logging.getLogger("strands").setLevel(logging.DEBUG)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler()]
)

# TODO: Import the http_request built-in tool

from strands_tools import http_request

# from strands.models.ollama import OllamaModel

# ollama_model = OllamaModel(
#     host="http://localhost:11434",
#     model_id="qwen2.5"
#     # model_id="tinyllama"
# )

from strands.models.openai import OpenAIModel

model = OpenAIModel(
    model_id="gpt-5.4",   # ou le nom de ton deployment Foundry
    client_args={
        "base_url": "https://rg-ava-poc-ia-foundry.cognitiveservices.azure.com/openai/v1/",
        "api_key": "",
    },
)

agent = Agent(
    # model=ollama_model,
    model=model,
    tools=[
        # TODO: Add the http_request built-in-tool
        http_request
    ]
)

agent("""
    Using the website https://en.wikipedia.org/wiki/Dungeons_%26_Dragons tell me the name of the designers of
    Dungeons and Dragons.
    """
)

