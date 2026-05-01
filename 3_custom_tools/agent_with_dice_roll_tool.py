from strands import Agent
import logging

logging.getLogger("strands").setLevel(logging.DEBUG)

# Add a handler to see the logs
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler()]
)

import sys
sys.stdout.reconfigure(encoding='utf-8')

# TODO: Import 'tool' from strands to use the @tool decorator

from strands import tool

# TODO: Add the decorator to transform your function into a tool
@tool
def roll_dice(faces: int = 6) -> int:

    # TODO: Modify the docstring with the args and return informations
    """
    🎲 Roll a die with a specified number of faces.

    Args:
        faces (int): Number of faces on the die. Must be greater than or equal to 1.

    Returns:
        int: A random roll result between 1 and `faces`, inclusive.

    Raises:
        ValueError: If `faces` is less than 1.
    """
    
    import random

    if faces < 1:
        raise ValueError("Dice must have at least 1 face")

    return random.randint(1, faces)

from strands.models.openai import OpenAIModel

model = OpenAIModel(
    model_id="gpt-5.4",   # ou le nom de ton deployment Foundry
    client_args={
        "base_url": "https://rg-ava-poc-ia-foundry.cognitiveservices.azure.com/openai/v1/",
        "api_key": "",
    },
)

dice_master = Agent(
    # TODO: Add the tool to the agent
    tools=[
        roll_dice
    ],
    model=model,
    system_prompt="""You are Lady Luck, the mystical keeper of dice and fortune in D&D adventures.
    You speak with theatrical flair and always announce dice rolls with appropriate drama.
    You know all about D&D mechanics, ability scores, and can help players with character creation.
    When rolling ability scores, remember the traditional method: roll 4d6, drop the lowest die."""
)

# Test your dice master's abilities
dice_master("Help me create a new D&D character! Roll the strength, wisdom, charisma and intelligence abilities scores using 4d6 drop lowest method.")

