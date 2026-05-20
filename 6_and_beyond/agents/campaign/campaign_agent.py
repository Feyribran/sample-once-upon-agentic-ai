import os
import uuid
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict
from strands import Agent, tool
from strands.multiagent.a2a import A2AServer
from tinydb import TinyDB, Query

from strands.models.openai import OpenAIModel
import logging


logging.getLogger("strands").setLevel(logging.INFO)

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

@dataclass
class Party:
    character_ids: str
    relationships: str
    group_reputation: str
    shared_inventory: List[str]

@dataclass
class Scene:
    scene_id: str
    location: str
    participants: List[str]
    mode: str
    summary: str
    status: str
    created_at: str
    updated_at: str

@dataclass
class TimelineEvent:
    timestamp: str
    type: str
    scene_id: str
    event: str
    participants: List[str]

@dataclass
class Campaign:
    campaign_id: str
    name: str
    party: Party
    active_scenes: List[Scene]
    quests: List[str]
    timeline: List[TimelineEvent]
    created_at: str
    updated_at: str


campaigns_db = TinyDB("campaigns.json", indent=4, separators=(",", ": "))
Campaign_Query = Query()

def save_campaign(campaign: Campaign) -> dict:
    campaign_dict = asdict(campaign)
    campaigns_db.update(campaign_dict, Campaign_Query.campaign_id == campaign.campaign_id)

def find_campaign(campaign_id: str) -> dict:
    result = campaigns_db.search(Campaign.campaign_id == campaign_id)
    if not result:
        return {"error": f"Campaign '{campaign_id}' not found"}
    return result[0]

@tool
def create_campaign(name: str, character_ids: list[str]) -> dict:
    """
    Create a new campaign with an initial party.

    Expected arguments:
    {
        "name": "Nouveau Monde",
        "character_ids": [
            "1d1238b3-9518-47f7-909b-ded3d41fd132",
            "156ff57b-2a00-43cf-9d9f-3c6363487871"
        ]
    }

    Args:
        name: Campaign name.
        character_ids: List of character IDs participating in the campaign.
    """
    campaign_id = str(uuid.uuid4())

    campaign = Campaign(
        campaign_id=campaign_id,
        name=name,
        party = Party(
            character_ids=character_ids,
            relationships={},
            group_reputation={},
            shared_inventory=[]
        ),
        active_scenes=[],
        quests=[],
        timeline=[],
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat()
    )

    campaigns_db.insert(asdict(campaign))
    return campaign

@tool
def get_campaign_state(campaign_id: str) -> dict:
    """
    Get the complete campaign state.

    Args:
        campaign_id: ID of the campaign.
    """
    campaign = find_campaign(campaign_id)

    if not campaign:
        return {
            "status": "error",
            "message": f"Campaign '{campaign_id}' not found"
        }

    save_campaign(campaign)

    return campaign

@tool
def create_scene(
    campaign_id: str,
    title: str,
    location: str,
    participants: List[str],
    mode: str = "exploration",
    summary: str = ""
) -> dict:
    """
    Create a new active scene in a campaign.

    Args:
        campaign_id: ID of the campaign.
        title: Scene title.
        location: Scene location.
        participants: List of character IDs participating in the scene.
        mode: Scene mode, for example exploration, combat, social, travel, downtime.
        summary: Initial short summary of the scene.
    """
    campaign = find_campaign(campaign_id)

    if not campaign:
        return {
            "status": "error",
            "message": f"Campaign '{campaign_id}' not found"
        }

    scene_id = str(uuid.uuid4())

    scene = Scene(
        scene_id=scene_id,
        title=title,
        location=location,
        mode=mode,
        participants=participants,
        summary=summary,
        status="active",
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat()
    )

    campaign["active_scenes"].append(scene)

    campaign["timeline"].append(TimelineEvent(
        timestamp=datetime.now().isoformat(),
        type="scene_created",
        scene_id=scene_id,
        event=f"Scene created: {title}",
        participants=participants
    ))

    campaign["updated_at"] = datetime.now().isoformat()
    save_campaign(campaign)

    return scene

@tool
def get_active_scenes(campaign_id: str) -> dict:
    """
    Get all active scenes in a campaign.

    Args:
        campaign_id: ID of the campaign.
    """
    campaign = find_campaign(campaign_id)

    if not campaign:
        return {
            "status": "error",
            "message": f"Campaign '{campaign_id}' not found"
        }

    save_campaign(campaign)

    return campaign["active_scenes"]


@tool
def get_scene(campaign_id: str, scene_id: str) -> dict:
    """
    Get one scene by ID.

    Args:
        campaign_id: ID of the campaign.
        scene_id: ID of the scene.
    """
    campaign = find_campaign(campaign_id)

    if not campaign:
        return {
            "status": "error",
            "message": f"Campaign '{campaign_id}' not found"
        }

    for scene in campaign["active_scenes"]:
        if scene["scene_id"] == scene_id:
            return {
                "status": "ok",
                "scene": scene
            }

    for scene in campaign["archived_scenes"]:
        if scene["scene_id"] == scene_id:
            return scene

    return {
        "status": "error",
        "message": f"Scene '{scene_id}' not found"
    }


@tool
def update_scene_summary(campaign_id: str, scene_id: str, summary: str) -> dict:
    """
    Replace the summary of an active scene.

    Args:
        campaign_id: ID of the campaign.
        scene_id: ID of the scene.
        summary: New scene summary.
    """
    campaign = find_campaign(campaign_id)

    if not campaign:
        return {
            "status": "error",
            "message": f"Campaign '{campaign_id}' not found"
        }

    for scene in campaign["active_scenes"]:
        if scene["scene_id"] == scene_id:
            scene["summary"] = summary
            scene["updated_at"] = datetime.now().isoformat()

            campaign["timeline"].append({
                "timestamp": datetime.now().isoformat(),
                "type": "scene_summary_updated",
                "scene_id": scene_id,
                "event": f"Scene summary updated: {scene['title']}"
            })

            campaign["updated_at"] = datetime.now().isoformat()
            save_campaign(campaign)

            return scene

    return {
        "status": "error",
        "message": f"Active scene '{scene_id}' not found"
    }


@tool
def append_to_scene_summary(campaign_id: str, scene_id: str, addition: str) -> dict:
    """
    Append a new note to an active scene summary.

    Args:
        campaign_id: ID of the campaign.
        scene_id: ID of the scene.
        addition: Text to append to the scene summary.
    """
    campaign = find_campaign(campaign_id)

    if not campaign:
        return {
            "status": "error",
            "message": f"Campaign '{campaign_id}' not found"
        }

    for scene in campaign["active_scenes"]:
        if scene["scene_id"] == scene_id:
            current_summary = scene.get("summary", "")

            if current_summary:
                scene["summary"] = f"{current_summary}\n{addition}"
            else:
                scene["summary"] = addition

            scene["updated_at"] = datetime.now().isoformat()

            campaign["timeline"].append({
                "timestamp": datetime.now().isoformat(),
                "type": "scene_note_added",
                "scene_id": scene_id,
                "event": addition
            })

            campaign["updated_at"] = datetime.now().isoformat()
            save_campaign(campaign)

            return scene

    return {
        "status": "error",
        "message": f"Active scene '{scene_id}' not found"
    }


@tool
def move_character_to_scene(
    campaign_id: str,
    character_id: str,
    target_scene_id: str
) -> dict:
    """
    Move a character from their current active scene to another active scene.
    The character is removed from all other active scenes.

    Args:
        campaign_id: ID of the campaign.
        character_id: ID of the character to move.
        target_scene_id: ID of the destination scene.
    """
    campaign = find_campaign(campaign_id)

    if not campaign:
        return {
            "status": "error",
            "message": f"Campaign '{campaign_id}' not found"
        }

    target_scene = None

    for scene in campaign["active_scenes"]:
        if scene["scene_id"] == target_scene_id:
            target_scene = scene
            break

    if not target_scene:
        return {
            "status": "error",
            "message": f"Target scene '{target_scene_id}' not found"
        }

    previous_scene_ids = []

    for scene in campaign["active_scenes"]:
        if character_id in scene.get("participants", []):
            scene["participants"].remove(character_id)
            scene["updated_at"] = datetime.now().isoformat()
            previous_scene_ids.append(scene["scene_id"])

    if character_id not in target_scene["participants"]:
        target_scene["participants"].append(character_id)

    target_scene["updated_at"] = datetime.now().isoformat()

    campaign["timeline"].append({
        "timestamp": datetime.now().isoformat(),
        "type": "character_moved_scene",
        "character_id": character_id,
        "from_scene_ids": previous_scene_ids,
        "to_scene_id": target_scene_id,
        "event": f"Character {character_id} moved to scene {target_scene_id}"
    })

    campaign["updated_at"] = datetime.now().isoformat()
    save_campaign(campaign)

    return {
        "status": "ok",
        "character_id": character_id,
        "from_scene_ids": previous_scene_ids,
        "to_scene_id": target_scene_id,
        "target_scene": target_scene
    }


@tool
def add_character_to_scene(
    campaign_id: str,
    character_id: str,
    scene_id: str
) -> dict:
    """
    Add a character to an active scene without removing them from other scenes.
    Useful for visions, remote communication, or temporary overlaps.

    Args:
        campaign_id: ID of the campaign.
        character_id: ID of the character.
        scene_id: ID of the scene.
    """
    campaign = find_campaign(campaign_id)

    if not campaign:
        return {
            "status": "error",
            "message": f"Campaign '{campaign_id}' not found"
        }

    for scene in campaign["active_scenes"]:
        if scene["scene_id"] == scene_id:
            if character_id not in scene["participants"]:
                scene["participants"].append(character_id)

            scene["updated_at"] = datetime.now().isoformat()

            campaign["timeline"].append({
                "timestamp": datetime.now().isoformat(),
                "type": "character_added_to_scene",
                "scene_id": scene_id,
                "character_id": character_id,
                "event": f"Character {character_id} added to scene {scene_id}"
            })

            campaign["updated_at"] = datetime.now().isoformat()
            save_campaign(campaign)

            return scene

    return {
        "status": "error",
        "message": f"Active scene '{scene_id}' not found"
    }


@tool
def remove_character_from_scene(
    campaign_id: str,
    character_id: str,
    scene_id: str
) -> dict:
    """
    Remove a character from an active scene.

    Args:
        campaign_id: ID of the campaign.
        character_id: ID of the character.
        scene_id: ID of the scene.
    """
    campaign = find_campaign(campaign_id)

    if not campaign:
        return {
            "status": "error",
            "message": f"Campaign '{campaign_id}' not found"
        }

    for scene in campaign["active_scenes"]:
        if scene["scene_id"] == scene_id:
            if character_id in scene["participants"]:
                scene["participants"].remove(character_id)

            scene["updated_at"] = datetime.now().isoformat()

            campaign["timeline"].append({
                "timestamp": datetime.now().isoformat(),
                "type": "character_removed_from_scene",
                "scene_id": scene_id,
                "character_id": character_id,
                "event": f"Character {character_id} removed from scene {scene_id}"
            })

            campaign["updated_at"] = datetime.now().isoformat()
            save_campaign(campaign)

            return {
                "status": "ok",
                "scene": scene
            }

    return {
        "status": "error",
        "message": f"Active scene '{scene_id}' not found"
    }


@tool
def change_scene_mode(campaign_id: str, scene_id: str, mode: str) -> dict:
    """
    Change the mode of an active scene.

    Example modes:
    - exploration
    - combat
    - social
    - travel
    - downtime
    - puzzle
    - chase

    Args:
        campaign_id: ID of the campaign.
        scene_id: ID of the scene.
        mode: New scene mode.
    """
    campaign = find_campaign(campaign_id)

    if not campaign:
        return {
            "status": "error",
            "message": f"Campaign '{campaign_id}' not found"
        }

    for scene in campaign["active_scenes"]:
        if scene["scene_id"] == scene_id:
            old_mode = scene.get("mode")
            scene["mode"] = mode
            scene["updated_at"] = datetime.now().isoformat()

            campaign["timeline"].append({
                "timestamp": datetime.now().isoformat(),
                "type": "scene_mode_changed",
                "scene_id": scene_id,
                "old_mode": old_mode,
                "new_mode": mode,
                "event": f"Scene {scene_id} changed from {old_mode} to {mode}"
            })

            campaign["updated_at"] = datetime.now().isoformat()
            save_campaign(campaign)

            return scene

    return {
        "status": "error",
        "message": f"Active scene '{scene_id}' not found"
    }


@tool
def close_scene(campaign_id: str, scene_id: str, resolution: str) -> dict:
    """
    Close an active scene and move it to archived scenes.

    Args:
        campaign_id: ID of the campaign.
        scene_id: ID of the scene.
        resolution: Summary of how the scene ended.
    """
    campaign = find_campaign(campaign_id)

    if not campaign:
        return {
            "status": "error",
            "message": f"Campaign '{campaign_id}' not found"
        }

    scene_to_close = None

    for scene in campaign["active_scenes"]:
        if scene["scene_id"] == scene_id:
            scene_to_close = scene
            break

    if not scene_to_close:
        return {
            "status": "error",
            "message": f"Active scene '{scene_id}' not found"
        }

    campaign["active_scenes"].remove(scene_to_close)

    scene_to_close["status"] = "closed"
    scene_to_close["resolution"] = resolution
    scene_to_close["closed_at"] = datetime.now().isoformat()
    scene_to_close["updated_at"] = datetime.now().isoformat()

    campaign["archived_scenes"].append(scene_to_close)

    campaign["timeline"].append({
        "timestamp": datetime.now().isoformat(),
        "type": "scene_closed",
        "scene_id": scene_id,
        "event": f"Scene closed: {scene_to_close['title']}",
        "resolution": resolution,
        "participants": scene_to_close.get("participants", [])
    })

    campaign["updated_at"] = datetime.now().isoformat()
    save_campaign(campaign)

    return {
        "status": "ok",
        "closed_scene": scene_to_close
    }


@tool
def add_timeline_event(
    campaign_id: str,
    event: str,
    involved_character_ids: List[str] = None,
    scene_id: str = None
) -> dict:
    """
    Add a general event to the campaign timeline.

    Args:
        campaign_id: ID of the campaign.
        event: Event description.
        involved_character_ids: Character IDs involved in the event.
        scene_id: Optional scene ID linked to the event.
    """
    campaign = find_campaign(campaign_id)

    if not campaign:
        return {
            "status": "error",
            "message": f"Campaign '{campaign_id}' not found"
        }

    timeline_event = {
        "timestamp": datetime.now().isoformat(),
        "type": "general_event",
        "event": event,
        "involved_character_ids": involved_character_ids or [],
        "scene_id": scene_id
    }

    campaign["timeline"].append(timeline_event)
    campaign["updated_at"] = datetime.now().isoformat()

    save_campaign(campaign)

    return timeline_event


DESCRIPTION = """
Specialized D&D campaign state management agent responsible for maintaining persistent campaign continuity across multiple characters, scenes, quests, relationships, and timeline events.

This agent manages the structured state of an ongoing campaign. It does not act as the main narrator and does not replace the Game Master. Instead, it provides reliable campaign memory services to the Game Master orchestrator.

Core responsibilities:
- Create and retrieve campaigns
- Track active and archived scenes
- Manage split-party situations and parallel storylines
- Record scene-specific events
- Maintain a global campaign timeline
- Track which characters are present in which scenes
- Update scene summaries as events unfold
- Preserve historical context for closed scenes
- Support continuity across multiple turns of play

The Campaign Agent should focus on state consistency, structured updates, and reliable retrieval. Narrative decisions, dramatic descriptions, rules arbitration, combat resolution, and dice rolling should remain the responsibility of the Game Master orchestrator, Rules Agent, Character Agent, or Dice MCP tools.
"""

SYSTEM_PROMPT = """
You are the Campaign State Manager for a persistent Dungeons & Dragons campaign.

Your role is to manage structured campaign memory. You are not the main Game Master narrator. You do not invent major story outcomes unless explicitly asked to record or organize them. Your job is to store, retrieve, update, and summarize the current campaign state with accuracy and consistency.

You manage:
- campaigns
- active scenes
- archived scenes
- scene-specific event histories
- global campaign timeline
- character locations across scenes
- split-party situations
- scene summaries
- scene modes such as exploration, combat, social, travel, downtime, puzzle, or chase

Important principles:

1. Maintain continuity
Always preserve what has already happened. Do not overwrite historical events. Scene events and campaign timeline entries should be append-only unless a correction is explicitly requested.

2. Separate local scene history from global campaign history
Each scene may have its own event log. The campaign also has a global timeline. Scene events should describe what happened inside a specific scene. Campaign timeline events should describe important campaign-level milestones.

3. Keep active and archived scenes distinct
Active scenes represent what is currently playable. Archived scenes represent completed scenes. When a scene is closed, keep its summary, participants, events, resolution, and timestamps.

4. Track character placement carefully
A character should normally be present in only one active scene at a time. Use move operations when a character physically moves from one scene to another. Only allow the same character in multiple scenes for special cases such as visions, dreams, magical communication, remote observation, or flashbacks.

5. Support split-party play
When the party is split, preserve separate locations, participants, summaries, and events for each active scene. Never merge scenes unless the story state explicitly says the characters have reunited.

6. Prefer structured updates
When asked to change the campaign state, use the available tools. Return precise structured information about what changed.

7. Do not resolve D&D rules
If a request requires rules interpretation, attack rolls, saving throws, ability checks, spell mechanics, or combat mechanics, the Game Master should consult the Rules Agent or Dice tools. You may record the result afterward, but you should not invent mechanical results.

8. Do not manage character sheets directly
Character identity, class, race, stats, inventory, level, and experience belong to the Character Agent. You may reference character IDs and record campaign-specific state such as scene participation or narrative events.

9. Summaries should be concise
Scene summaries should be short, current-state descriptions, not full transcripts. Detailed history belongs in scene events.

10. Be careful with IDs
When a campaign_id, scene_id, or character_id is provided, preserve it exactly. Do not fabricate IDs unless creating a new campaign or scene through the appropriate tool.

When responding, favor JSON-compatible structured responses. Include:
- status
- relevant campaign_id
- relevant scene_id if applicable
- what changed
- current active scenes if useful
- any errors or missing data

Use clear, factual language. Do not add decorative narration unless explicitly requested.
"""

agent = Agent(
    # TODO: Configure the Character Agent with:
    # - model: optional
    # - tools: List the tools
    # - name: "Character Creator Agent"
    model=model,
    tools=[
        create_campaign,
        get_campaign_state,
        create_scene,
        get_active_scenes,
        get_scene,
        update_scene_summary,
        append_to_scene_summary,
        move_character_to_scene,
        add_character_to_scene,
        remove_character_from_scene,
        change_scene_mode,
        close_scene,
        add_timeline_event
    ],
    name="Character Creator Agent",
    description= DESCRIPTION,
    system_prompt= SYSTEM_PROMPT
)

# TODO: Create an A2AServer instance with:
# - agent: The agent instance created above
# - port: 8001 (Character Agent port)
# a2a_server = None
a2a_server = A2AServer(
    agent=agent,
    port=8002
)

if __name__ == "__main__":
    # TODO: Start the A2A server
    # pass
    a2a_server.serve()
