import os
import sys
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List
from tinydb import TinyDB, Query
from strands import Agent
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamable_http_client
from strands_tools.a2a_client import A2AClientToolProvider

from strands.models.openai import OpenAIModel
import logging


logging.getLogger("strands").setLevel(logging.DEBUG)

# Add a handler to see the logs
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler()]
)

model = OpenAIModel(
    model_id="gpt-5.4",   # ou le nom de ton deployment Foundry
    client_args={
        "base_url": "https://rg-ava-poc-ia-foundry.cognitiveservices.azure.com/openai/v1/",
        "api_key": "",
    },
)

app = FastAPI(title="D&D Game Master API")
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QuestionRequest(BaseModel):
    question: str

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.get("/messages")
def get_messages():
    return agent.messages

@app.get("/user/{user_name}")
def get_user(user_name):
    characters_db = TinyDB('./../../../5_a2a_integration/agents/character_agent/characters.json')
    Character_Query = Query()
    result = characters_db.search(Character_Query.name == user_name)
    if not result:
        return f":x: Character with name '{user_name}' not found"
    
    character = result[0]
    print(f"✅ Found character: {character['name']} (ID: {character['character_id']}, {character['character_class']} {character['race']})")
    return character

# TODO: Create MCP Client for dice rolling service
# Initialize MCPClient with a lambda that returns streamablehttp_client("http://localhost:8080/mcp")
# mcp_client = None
def create_streamable_http_transport():
    return streamable_http_client("http://localhost:8080/mcp/")

mcp_client = MCPClient(create_streamable_http_transport)

# System prompt for the agent
SYSTEM_PROMPT = """You are a D&D Game Master orchestrator with access to specialized agents and tools.

Available agents:
- Rules Agent, for D&D mechanics and rules
- Character Agent, for character creation and management
- Campaign Agent, for campaign and scene management

To communicate with agents:
1. Use a2a_list_discovered_agents to see available agents
2. Use a2a_send_message with the agent's URL to send questions
3. Use roll_dice for dice rolling
4. Use character names from character agent to retrieve character ids for campaign and scene creations in campaign agent

Available D&D dice types:
- d4 (4-sided die) - Used for damage rolls of small weapons like daggers
- d6 (6-sided die) - Used for damage rolls of weapons like shortswords, spell damage
- d8 (8-sided die) - Used for damage rolls of weapons like longswords, rapiers
- d10 (10-sided die) - Used for damage rolls of heavy weapons, percentile rolls
- d12 (12-sided die) - Used for damage rolls of great weapons like greataxes
- d20 (20-sided die) - Used for ability checks, attack rolls, saving throws
- d100 (percentile die) - Used for random tables, wild magic surges

IMPORTANT: Always use the exact URLs shown by a2a_list_discovered_agents. Never invent or guess URLs.

Be creative, engaging, and use your available tools to enhance the D&D experience.
"""

class DiceOutput(BaseModel):
    dice_type: str = Field(description="The dice type. Ex: d4, d6, d20, etc")
    result: str = Field(description="The dice result value")
    reason: str = Field(description="The reason the dice was rolled. Ex: attack roll")

# class StoryOutput(BaseModel):
#     """Model that contains information about a Person"""
#     response: str = Field(description="Your narative response as Game Master")
#     actions_suggestions: list[str] = Field(description="['Action 1', 'Action 2', 'Action 3']")
#     details: str = Field(description="Brief summary of tools/agents used")
#     dice_rolls: List[DiceOutput] = Field(default=[], description="List of dice rolls with dice_type, result, and reason")


class CharacterStateOutput(BaseModel):
    character_id: str = Field(description="Unique identifier of the character")
    hp_delta: int = Field(description="Change in hit points, e.g. -3 or +5")
    location: str = Field(description="Updated location of the character")
    status_added: List[str] = Field(default=[], description="Statuses added to the character")

class QuestStateOutput(BaseModel):
    quest_id: str = Field(description="Unique identifier of the quest")
    status: str = Field(description="Updated quest status, e.g. progressed, completed, failed")
    note: str = Field(description="Narrative note about the quest update")

class RelationshipStateOutput(BaseModel):
    from_character_id: str = Field(description="Source character identifier")
    to_character_id: str = Field(description="Target character identifier")
    change: str = Field(description="Relationship change, e.g. trust +1")
    reason: str = Field(description="Reason for the relationship change")

class StateUpdatesOutput(BaseModel):
    characters: List[CharacterStateOutput] = Field(
        default=[],
        description="List of characters state updates"
    )
    quests: List[QuestStateOutput] = Field(
        default=[],
        description="List of quest state updates"
    )
    relationships: List[RelationshipStateOutput] = Field(
        default=[],
        description="List of relationship updates"
    )
    timeline_event: str = Field(description="Summary of the timeline event")

class ActiveSceneOutput(BaseModel):
    scene_id: str = Field(description="Unique identifier of the active scene")
    location: str = Field(description="Current scene location")
    participants: List[str] = Field(description="Characters participating in the scene")
    mode: str = Field(description="Scene mode, e.g. combat, exploration, dialogue")
    summary: str = Field(description="A short summary of the scene")


class MultiPlayerStoryOutput(BaseModel):
    """Model that contains information about a Person"""
    response: str = Field(description="Your narative response as Game Master")
    actions_suggestions: list[str] = Field(description="['Action 1', 'Action 2', 'Action 3']")
    details: str = Field(description="Brief summary of tools/agents used")
    dice_rolls: List[DiceOutput] = Field(default=[], description="List of dice rolls with dice_type, result, and reason")
    state_updates: StateUpdatesOutput = Field(description="Structured updates for characters, quests, relationships, and timeline")
    active_scenes: List[ActiveSceneOutput] = Field(default=[], description="Information about the current active scenes")

try:
    # TODO: Create the A2A client with the A2AClientToolProvider and pass the list of the known agent urls
    # A2A_AGENT_URLS = []
    A2A_AGENT_URLS = [
        "http://localhost:8001",
        "http://localhost:8000",
        "http://localhost:8002",
    ]

    a2a_client = A2AClientToolProvider(known_agent_urls=A2A_AGENT_URLS)
    # Timeout is default to 300 seconds
    # a2a_client = A2AClientToolProvider(known_agent_urls=A2A_AGENT_URLS,timeout=600)

    agent = Agent(
        system_prompt=SYSTEM_PROMPT,
        #TODO: Create the gamemaster agent with both A2A and MCP tools
        name="Gamemaster Agent",
        model=model,
        tools=[mcp_client,a2a_client.tools],
        #TODO: Force the response to use the StoryOutput model
        structured_output_model=CharacterStateOutput
    )

except Exception as e:
    print(f"Error occurred: {str(e)}")

@app.post("/inquire")
async def ask_agent(request: QuestionRequest):
    print("Processing request...")
    try:
        response = await agent.invoke_async(request.question)
        print(response.structured_output)
        return JSONResponse(content={ "response": response.structured_output.model_dump()})
        
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return JSONResponse(content={"error": "Internal server error"}, status_code=500)

if __name__ == "__main__":
    uvicorn.run(app, port=8009)
