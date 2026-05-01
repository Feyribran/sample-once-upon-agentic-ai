from strands import Agent

# Pour gérer les caractères spéciaux
import sys
sys.stdout.reconfigure(encoding='utf-8')

# TODO: Add debug logging to see what your agent is thinking

import logging

# logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
# Configure the root strands logger
logging.getLogger("strands").setLevel(logging.DEBUG)

# Add a handler to see the logs
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler()]
)

# TODO: Create the agent with the following system prompt: "You are a game master for a Dungeon & Dragon game"

from strands.models.ollama import OllamaModel

ollama_model = OllamaModel(
    host="http://localhost:11434",
    # model_id="llama3"
    model_id="tinyllama"
)

agent = Agent(
    model=ollama_model,
    system_prompt=(
        "Vous êtes le Maître du Jeu d'une partie de Donjon & Dragon."
    )
)

# TODO: Summon your agent with a basic incantation such as "Hi, I am an advanturer ready for adventure!"

response = agent("Salut, je suis un aventurier paré pour l'aventure !")
