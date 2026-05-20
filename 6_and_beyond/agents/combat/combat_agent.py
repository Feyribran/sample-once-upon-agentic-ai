import uuid
from datetime import datetime
from typing import List, Dict, Optional
from tinydb import TinyDB, Query
from strands import Agent, tool
from strands.multiagent.a2a import A2AServer

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


combats_db = TinyDB("combats.json", indent=4, separators=(",", ": "))
CombatQuery = Query()


def now_iso() -> str:
    return datetime.now().isoformat()


def find_combat(combat_id: str) -> Optional[dict]:
    result = combats_db.search(CombatQuery.combat_id == combat_id)
    if not result:
        return None
    return result[0]


def save_combat(combat: dict) -> dict:
    existing = combats_db.search(CombatQuery.combat_id == combat["combat_id"])

    if existing:
        combats_db.update(combat, CombatQuery.combat_id == combat["combat_id"])
    else:
        combats_db.insert(combat)

    return combat


def sort_by_initiative(participants: List[dict]) -> List[dict]:
    return sorted(
        participants,
        key=lambda participant: participant.get("initiative", 0),
        reverse=True
    )


def get_living_participants(combat: dict) -> List[dict]:
    return [
        participant
        for participant in combat["participants"]
        if participant.get("current_hp", 0) > 0
    ]


@tool
def start_combat(name: str, participants: List[Dict]) -> dict:
    """
    Start a new combat encounter.

    Expected participants format:
    [
        {
            "participant_id": "character-or-npc-id",
            "name": "Thorin",
            "type": "player",
            "armor_class": 16,
            "max_hp": 12,
            "current_hp": 12,
            "initiative": 18,
            "status_effects": []
        }
    ]

    Args:
        name: Combat encounter name.
        participants: List of combat participants with initiative already provided.
    """
    combat_id = str(uuid.uuid4())
    timestamp = now_iso()

    normalized_participants = []

    for participant in participants:
        normalized_participants.append({
            "participant_id": participant["participant_id"],
            "name": participant["name"],
            "type": participant.get("type", "npc"),
            "armor_class": participant.get("armor_class", 10),
            "max_hp": participant.get("max_hp", 1),
            "current_hp": participant.get("current_hp", participant.get("max_hp", 1)),
            "initiative": participant.get("initiative", 0),
            "status_effects": participant.get("status_effects", [])
        })

    combat = {
        "combat_id": combat_id,
        "name": name,
        "round": 1,
        "turn_index": 0,
        "status": "active",
        "participants": sort_by_initiative(normalized_participants),
        "event_log": [
            {
                "timestamp": timestamp,
                "type": "combat_started",
                "event": f"Combat started: {name}"
            }
        ],
        "created_at": timestamp,
        "updated_at": timestamp
    }

    save_combat(combat)

    return {
        "status": "ok",
        "action": "start_combat",
        "combat_id": combat_id,
        "combat": combat
    }


@tool
def get_combat_state(combat_id: str) -> dict:
    """
    Get the complete state of a combat.

    Args:
        combat_id: ID of the combat.
    """
    combat = find_combat(combat_id)

    if not combat:
        return {
            "status": "error",
            "message": f"Combat '{combat_id}' not found"
        }

    return {
        "status": "ok",
        "combat": combat
    }


@tool
def get_current_turn(combat_id: str) -> dict:
    """
    Get the participant whose turn it currently is.

    Args:
        combat_id: ID of the combat.
    """
    combat = find_combat(combat_id)

    if not combat:
        return {
            "status": "error",
            "message": f"Combat '{combat_id}' not found"
        }

    living_participants = get_living_participants(combat)

    if not living_participants:
        return {
            "status": "ended",
            "message": "No living participants remain"
        }

    turn_index = combat["turn_index"] % len(combat["participants"])
    current_participant = combat["participants"][turn_index]

    return {
        "status": "ok",
        "combat_id": combat_id,
        "round": combat["round"],
        "turn_index": combat["turn_index"],
        "current_turn": current_participant
    }


@tool
def advance_turn(combat_id: str) -> dict:
    """
    Advance combat to the next living participant.

    Args:
        combat_id: ID of the combat.
    """
    combat = find_combat(combat_id)

    if not combat:
        return {
            "status": "error",
            "message": f"Combat '{combat_id}' not found"
        }

    if combat["status"] != "active":
        return {
            "status": "error",
            "message": f"Combat '{combat_id}' is not active"
        }

    participant_count = len(combat["participants"])

    if participant_count == 0:
        return {
            "status": "error",
            "message": "Combat has no participants"
        }

    attempts = 0

    while attempts < participant_count:
        combat["turn_index"] += 1

        if combat["turn_index"] >= participant_count:
            combat["turn_index"] = 0
            combat["round"] += 1

        current = combat["participants"][combat["turn_index"]]

        if current.get("current_hp", 0) > 0:
            break

        attempts += 1

    timestamp = now_iso()
    combat["updated_at"] = timestamp

    current_turn = combat["participants"][combat["turn_index"]]

    combat["event_log"].append({
        "timestamp": timestamp,
        "type": "turn_advanced",
        "event": f"Turn advanced to {current_turn['name']}",
        "round": combat["round"],
        "participant_id": current_turn["participant_id"]
    })

    save_combat(combat)

    return {
        "status": "ok",
        "combat_id": combat_id,
        "round": combat["round"],
        "turn_index": combat["turn_index"],
        "current_turn": current_turn
    }


@tool
def apply_damage(combat_id: str, target_id: str, damage: int, reason: str = "") -> dict:
    """
    Apply damage to a combat participant.

    Args:
        combat_id: ID of the combat.
        target_id: Participant ID receiving damage.
        damage: Damage amount.
        reason: Optional reason for the damage.
    """
    combat = find_combat(combat_id)

    if not combat:
        return {
            "status": "error",
            "message": f"Combat '{combat_id}' not found"
        }

    for participant in combat["participants"]:
        if participant["participant_id"] == target_id:
            old_hp = participant["current_hp"]
            participant["current_hp"] = max(0, old_hp - damage)

            timestamp = now_iso()
            combat["updated_at"] = timestamp

            event = {
                "timestamp": timestamp,
                "type": "damage_applied",
                "target_id": target_id,
                "target_name": participant["name"],
                "damage": damage,
                "old_hp": old_hp,
                "new_hp": participant["current_hp"],
                "reason": reason,
                "event": f"{participant['name']} takes {damage} damage"
            }

            if participant["current_hp"] == 0:
                event["defeated"] = True
                event["event"] = f"{participant['name']} takes {damage} damage and is defeated"

            combat["event_log"].append(event)
            save_combat(combat)

            return {
                "status": "ok",
                "combat_id": combat_id,
                "target": participant,
                "event": event
            }

    return {
        "status": "error",
        "message": f"Target '{target_id}' not found in combat"
    }


@tool
def heal_participant(combat_id: str, target_id: str, amount: int, reason: str = "") -> dict:
    """
    Heal a combat participant.

    Args:
        combat_id: ID of the combat.
        target_id: Participant ID receiving healing.
        amount: Healing amount.
        reason: Optional reason for the healing.
    """
    combat = find_combat(combat_id)

    if not combat:
        return {
            "status": "error",
            "message": f"Combat '{combat_id}' not found"
        }

    for participant in combat["participants"]:
        if participant["participant_id"] == target_id:
            old_hp = participant["current_hp"]
            participant["current_hp"] = min(
                participant["max_hp"],
                old_hp + amount
            )

            timestamp = now_iso()
            combat["updated_at"] = timestamp

            event = {
                "timestamp": timestamp,
                "type": "healing_applied",
                "target_id": target_id,
                "target_name": participant["name"],
                "amount": amount,
                "old_hp": old_hp,
                "new_hp": participant["current_hp"],
                "reason": reason,
                "event": f"{participant['name']} recovers {amount} HP"
            }

            combat["event_log"].append(event)
            save_combat(combat)

            return {
                "status": "ok",
                "combat_id": combat_id,
                "target": participant,
                "event": event
            }

    return {
        "status": "error",
        "message": f"Target '{target_id}' not found in combat"
    }


@tool
def apply_status_effect(combat_id: str, target_id: str, status_effect: str, reason: str = "") -> dict:
    """
    Apply a status effect to a combat participant.

    Args:
        combat_id: ID of the combat.
        target_id: Participant ID receiving the status effect.
        status_effect: Status effect name, for example poisoned, prone, restrained, frightened.
        reason: Optional reason for the effect.
    """
    combat = find_combat(combat_id)

    if not combat:
        return {
            "status": "error",
            "message": f"Combat '{combat_id}' not found"
        }

    for participant in combat["participants"]:
        if participant["participant_id"] == target_id:
            if status_effect not in participant["status_effects"]:
                participant["status_effects"].append(status_effect)

            timestamp = now_iso()
            combat["updated_at"] = timestamp

            event = {
                "timestamp": timestamp,
                "type": "status_effect_applied",
                "target_id": target_id,
                "target_name": participant["name"],
                "status_effect": status_effect,
                "reason": reason,
                "event": f"{participant['name']} is now affected by {status_effect}"
            }

            combat["event_log"].append(event)
            save_combat(combat)

            return {
                "status": "ok",
                "combat_id": combat_id,
                "target": participant,
                "event": event
            }

    return {
        "status": "error",
        "message": f"Target '{target_id}' not found in combat"
    }


@tool
def remove_status_effect(combat_id: str, target_id: str, status_effect: str) -> dict:
    """
    Remove a status effect from a combat participant.

    Args:
        combat_id: ID of the combat.
        target_id: Participant ID.
        status_effect: Status effect name to remove.
    """
    combat = find_combat(combat_id)

    if not combat:
        return {
            "status": "error",
            "message": f"Combat '{combat_id}' not found"
        }

    for participant in combat["participants"]:
        if participant["participant_id"] == target_id:
            if status_effect in participant["status_effects"]:
                participant["status_effects"].remove(status_effect)

            timestamp = now_iso()
            combat["updated_at"] = timestamp

            event = {
                "timestamp": timestamp,
                "type": "status_effect_removed",
                "target_id": target_id,
                "target_name": participant["name"],
                "status_effect": status_effect,
                "event": f"{status_effect} removed from {participant['name']}"
            }

            combat["event_log"].append(event)
            save_combat(combat)

            return {
                "status": "ok",
                "combat_id": combat_id,
                "target": participant,
                "event": event
            }

    return {
        "status": "error",
        "message": f"Target '{target_id}' not found in combat"
    }


@tool
def end_combat(combat_id: str, outcome: str) -> dict:
    """
    End a combat encounter.

    Args:
        combat_id: ID of the combat.
        outcome: Summary of how the combat ended.
    """
    combat = find_combat(combat_id)

    if not combat:
        return {
            "status": "error",
            "message": f"Combat '{combat_id}' not found"
        }

    timestamp = now_iso()
    combat["status"] = "ended"
    combat["ended_at"] = timestamp
    combat["updated_at"] = timestamp

    combat["event_log"].append({
        "timestamp": timestamp,
        "type": "combat_ended",
        "event": outcome
    })

    save_combat(combat)

    return {
        "status": "ok",
        "combat_id": combat_id,
        "combat": combat
    }

DESCRIPTION = """
Specialized D&D combat state management agent responsible for tracking turn-based combat encounters.

This agent manages the mechanical state of combat:
- combat participants
- initiative order
- rounds and turns
- hit points
- damage and healing
- status effects
- defeated participants
- combat event log

The Combat Agent does not act as the main narrator. It does not invent dramatic descriptions or story consequences. It provides reliable combat state updates for the Game Master orchestrator.

Rules interpretation should be handled by the Rules Agent. Dice rolling should be handled by the Dice MCP tool. Character sheet retrieval should be handled by the Character Agent.
"""

SYSTEM_PROMPT = """
You are the Combat State Manager for a Dungeons & Dragons game.

Your role is to manage structured turn-based combat state. You are not the main Game Master narrator. You do not create dramatic narration unless explicitly asked. You track mechanics precisely.

You manage:
- combat encounters
- participants
- initiative order
- current round
- current turn
- hit points
- damage
- healing
- status effects
- defeated participants
- combat event logs

Important rules:

1. Always preserve combat state.
Do not overwrite the event log. Append new events when something happens.

2. Participants must have stable IDs.
Use participant_id exactly as provided. Do not invent character IDs for player characters.

3. Initiative order determines turn order.
Participants should be sorted by initiative from highest to lowest when combat starts.

4. Track rounds and turns precisely.
When the turn index loops back to the first participant, increment the round number.

5. Skip defeated participants.
A participant with current_hp equal to 0 should not receive a normal turn.

6. Never reduce HP below 0.
Damage can reduce current_hp to 0, but not below 0. If damage are superior to the current_hp, always consider the current_hp value instead.

7. Never heal above max_hp.
Healing cannot increase current_hp beyond max_hp.

8. Do not roll dice yourself.
If initiative, attack rolls, saving throws, or damage rolls are needed, the Game Master should use the Dice MCP tool and then provide the results to you.

9. Do not interpret complex D&D rules.
If the request requires rules interpretation, the Game Master should consult the Rules Agent. You may record the result afterward.

10. Return structured JSON-compatible responses.
Always include status, combat_id when applicable, and the updated combat or participant state.

Use clear, factual language. Avoid decorative narration.
"""

agent = Agent(
    name="Combat Agent",
    model=model,
    description=DESCRIPTION,
    system_prompt=SYSTEM_PROMPT,
    tools=[
        start_combat,
        get_combat_state,
        get_current_turn,
        advance_turn,
        apply_damage,
        heal_participant,
        apply_status_effect,
        remove_status_effect,
        end_combat,
    ],
)

a2a_server = A2AServer(
    agent=agent,
    port=8003
)

if __name__ == "__main__":
    a2a_server.serve()