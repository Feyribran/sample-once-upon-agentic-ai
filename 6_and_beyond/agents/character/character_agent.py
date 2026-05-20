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
class Stats:
    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int

@dataclass
class InventoryItem:
    item_name: str
    quantity: int

@dataclass
class Character:
    character_id: str
    name: str
    character_class: str  # "class" is reserved in Python too
    race: str
    gender: str
    level: int
    experience: int
    stats: Stats
    inventory: List[InventoryItem]
    created_at: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

XP_LEVEL_THRESHOLDS = [
    (0, 1),
    (300, 2),
    (900, 3),
    (2700, 4),
    (6500, 5),
    (14000, 6),
    (23000, 7),
    (34000, 8),
    (48000, 9),
    (64000, 10),
    (85000, 11),
    (100000, 12),
    (120000, 13),
    (140000, 14),
    (165000, 15),
    (195000, 16),
    (225000, 17),
    (265000, 18),
    (305000, 19),
    (355000, 20),
]

characters_db = TinyDB('characters.json', indent=4, separators=(',', ': '))
Character_Query = Query()

def find_character_by_id(character_id: str) -> dict | None:
    result = characters_db.search(Character_Query.character_id == character_id)

    if not result:
        return None

    return result[0]

def save_character(character: dict) -> dict:
    characters_db.update(
        character,
        Character_Query.character_id == character["character_id"]
    )

    return character

def calculate_level_from_xp(experience: int) -> int:
    level = 1

    for threshold, threshold_level in XP_LEVEL_THRESHOLDS:
        if experience >= threshold:
            level = threshold_level
        else:
            break

    return level

def update_inventory(character: dict, item_name: str, quantity: int) -> dict:
    character.setdefault("inventory", [])

    for item in character["inventory"]:
        if item["item_name"].lower() == item_name.lower():
            item["quantity"] += quantity
            return character

    character["inventory"].append({
        "item_name": item_name,
        "quantity": quantity
    })

    return character

@tool
def find_character_by_name(name: str) -> str:
    """
    Find a character by name
    
    Args:
        name: The character's name to search for
    """
    print(f"🔍 Searching for character with name: '{name}'")
    result = characters_db.search(Character_Query.name == name)
    
    if not result:
        print(f"❌ Character with name '{name}' not found")
        return f":x: Character with name '{name}' not found"
    
    character = result[0]
    print(f"✅ Found character: {character['name']} (ID: {character['character_id']}, {character['character_class']} {character['race']})")
    return character


@tool
def list_all_characters() -> str:
    """
    List all characters in the database
    """
    print("📋 Listing all characters in database")
    all_chars = characters_db.all()
    
    if not all_chars:
        print("❌ No characters found in database")
        return ":scroll: No characters found in the database"

    print(f"✅ Found {len(all_chars)} character(s) in database")
    for char in all_chars:
        print(f"  - {char['name']} ({char['character_class']} {char['race']})")
    
    return all_chars


@tool
def create_character(
    name: str,
    character_class: str,
    race: str,
    gender: str,
    stats_dict: Dict[str, int]
    ) -> str:
    """
    Character details respecting the GameCharacters object fields.
    Roll a dice to generate the stats_dic (ability scores). 
    When rolling ability scores, remember the traditional method: roll 4d6, drop the lowest die.
    
    Args:
        name: Character's name
        character_class: D&D class (Fighter, Wizard, etc.)
        race: D&D race (Human, Elf, etc.)
        gender: Character's gender
        stats_dict: Dictionary with strength, dexterity, constitution, intelligence, wisdom, charisma

    """
    # Generate unique character ID
    character_id = str(uuid.uuid4())
    print(character_id)
    # Create stats object
    stats = Stats(
        strength=stats_dict.get('strength', 10),
        dexterity=stats_dict.get('dexterity', 10),
        constitution=stats_dict.get('constitution', 10),
        intelligence=stats_dict.get('intelligence', 10),
        wisdom=stats_dict.get('wisdom', 10),
        charisma=stats_dict.get('charisma', 10)
    )

    print(stats)
    # Create character with updated CurrentStatus
    character = Character(
        character_id=character_id,
        name=name,
        character_class=character_class,
        race=race,
        gender=gender,
        level=1,
        experience=0,
        stats=stats,
        inventory=[
            InventoryItem("Starting Equipment Pack", 1),
            InventoryItem("Gold Pieces", 100)
        ]
    )
    print(character)
    
    characters_db.insert(asdict(character))
    print("Inserted")
    return character

@tool
def add_experience(character_id: str, amount: int, reason: str = "") -> dict:
    """
    Add experience points to a character and update level automatically.

    Args:
        character_id: ID of the character receiving experience.
        amount: Amount of experience points to add.
        reason: Optional reason, for example combat reward or quest completed.
    """
    character = find_character_by_id(character_id)

    if not character:
        return {
            "status": "error",
            "message": f"Character '{character_id}' not found"
        }

    old_experience = character.get("experience", 0)
    old_level = character.get("level", 1)

    new_experience = old_experience + amount
    new_level = calculate_level_from_xp(new_experience)

    character["experience"] = new_experience
    character["level"] = new_level

    save_character(character)

    return {
        "status": "ok",
        "action": "add_experience",
        "character_id": character_id,
        "name": character["name"],
        "experience_added": amount,
        "old_experience": old_experience,
        "new_experience": new_experience,
        "old_level": old_level,
        "new_level": new_level,
        "leveled_up": new_level > old_level,
        "reason": reason,
        "character": character
    }

@tool
def set_character_level(character_id: str, level: int, reason: str = "") -> dict:
    """
    Set a character level manually.

    Useful for milestone leveling.

    Args:
        character_id: ID of the character.
        level: New character level.
        reason: Optional reason for the level change.
    """
    character = find_character_by_id(character_id)

    if not character:
        return {
            "status": "error",
            "message": f"Character '{character_id}' not found"
        }

    old_level = character.get("level", 1)
    character["level"] = level

    save_character(character)

    return {
        "status": "ok",
        "action": "set_character_level",
        "character_id": character_id,
        "name": character["name"],
        "old_level": old_level,
        "new_level": level,
        "leveled_up": level > old_level,
        "reason": reason,
        "character": character
    }

@tool
def add_inventory_item(
    character_id: str,
    item_name: str,
    quantity: int = 1,
    reason: str = ""
) -> dict:
    """
    Add an item to a character inventory.

    Args:
        character_id: ID of the character.
        item_name: Name of the item to add.
        quantity: Quantity to add.
        reason: Optional reason, for example loot, reward, purchase.
    """
    character = find_character_by_id(character_id)

    if not character:
        return {
            "status": "error",
            "message": f"Character '{character_id}' not found"
        }

    if quantity <= 0:
        return {
            "status": "error",
            "message": "Quantity must be greater than 0"
        }

    update_inventory(character, item_name, quantity)
    save_character(character)

    return {
        "status": "ok",
        "action": "add_inventory_item",
        "character_id": character_id,
        "name": character["name"],
        "item_name": item_name,
        "quantity_added": quantity,
        "reason": reason,
        "inventory": character["inventory"]
    }

@tool
def remove_inventory_item(
    character_id: str,
    item_name: str,
    quantity: int = 1,
    reason: str = ""
) -> dict:
    """
    Remove an item from a character inventory.

    Args:
        character_id: ID of the character.
        item_name: Name of the item to remove.
        quantity: Quantity to remove.
        reason: Optional reason, for example item used, sold, lost.
    """
    character = find_character_by_id(character_id)

    if not character:
        return {
            "status": "error",
            "message": f"Character '{character_id}' not found"
        }

    if quantity <= 0:
        return {
            "status": "error",
            "message": "Quantity must be greater than 0"
        }

    character.setdefault("inventory", [])

    for item in character["inventory"]:
        if item["item_name"].lower() == item_name.lower():
            if item["quantity"] < quantity:
                return {
                    "status": "error",
                    "message": f"Not enough '{item_name}' in inventory",
                    "available_quantity": item["quantity"],
                    "requested_quantity": quantity
                }

            item["quantity"] -= quantity

            if item["quantity"] == 0:
                character["inventory"].remove(item)

            save_character(character)

            return {
                "status": "ok",
                "action": "remove_inventory_item",
                "character_id": character_id,
                "name": character["name"],
                "item_name": item_name,
                "quantity_removed": quantity,
                "reason": reason,
                "inventory": character["inventory"]
            }

    return {
        "status": "error",
        "message": f"Item '{item_name}' not found in inventory"
    }

@tool
def award_combat_rewards(
    character_ids: List[str],
    experience_each: int = 0,
    # gold_each: int = 0,
    items_each: List[Dict] = None,
    reason: str = "Combat completed"
) -> dict:
    """
    Award combat rewards to multiple characters.

    Args:
        character_ids: List of character IDs receiving rewards.
        experience_each: Experience points awarded to each character.
        gold_each: Gold pieces awarded to each character.
        items_each: Items awarded to each character.
            Expected format:
            [
                {"item_name": "Potion of Healing", "quantity": 1},
                {"item_name": "Goblin Dagger", "quantity": 1}
            ]
        reason: Reason for the rewards.
    """
    items_each = items_each or []

    updated_characters = []
    errors = []

    for character_id in character_ids:
        character = find_character_by_id(character_id)

        if not character:
            errors.append({
                "character_id": character_id,
                "message": f"Character '{character_id}' not found"
            })
            continue

        old_experience = character.get("experience", 0)
        old_level = character.get("level", 1)

        new_experience = old_experience + experience_each
        new_level = calculate_level_from_xp(new_experience)

        character["experience"] = new_experience
        character["level"] = new_level

        # if gold_each > 0:
        #     add_or_update_inventory_item(character, "Gold Pieces", gold_each)

        for item in items_each:
            update_inventory(
                character,
                item["item_name"],
                item.get("quantity", 1)
            )

        save_character(character)

        updated_characters.append({
            "character_id": character_id,
            "name": character["name"],
            "experience_added": experience_each,
            "old_experience": old_experience,
            "new_experience": new_experience,
            "old_level": old_level,
            "new_level": new_level,
            "leveled_up": new_level > old_level,
            # "gold_added": gold_each,
            "items_added": items_each,
            "character": character
        })

    return {
        "status": "ok" if not errors else "partial_success",
        "action": "award_combat_rewards",
        "reason": reason,
        "updated_characters": updated_characters,
        "errors": errors
    }

DESCRIPTION="""
Specialized D&D character management agent that handles character creation, storage, and retrieval. 
Creates new characters with proper ability score generation (4d6 drop lowest), manages character data in persistent storage, 
and provides character lookup services. Maintains complete character profiles including stats, inventory, and progression data for D&D campaigns.
"""

SYSTEM_PROMPT = """
You are a D&D character management specialist.

You manage persistent character sheets:
- character creation
- character lookup
- experience points
- level progression
- inventory updates
- combat and quest rewards

Important rules:
1. Character sheets are persistent.
Always use tools when creating, finding, or updating characters.
The create_character tool requires this exact stats_dict shape:

{
  "strength": int,
  "dexterity": int,
  "constitution": int,
  "intelligence": int,
  "wisdom": int,
  "charisma": int
}

Never call create_character without stats_dict.

2. Use character_id for updates.
When updating experience, level, or inventory, prefer character_id over name.

3. Combat rewards should use award_combat_rewards.
When a combat ends and one or multiple characters receive XP or loot, use award_combat_rewards.

4. Inventory should stack identical items.
If an item already exists in inventory, increase its quantity instead of adding a duplicate.

5. Experience may cause level up.
When adding XP, update the level using the XP threshold table.

6. Do not manage temporary combat state.
Current HP during a fight, initiative, turn order, and combat status belong to the Combat Agent.

7. Return structured JSON-compatible responses.
Always include status, action, character_id when relevant, and what changed.
"""

agent = Agent(
    model=model,
    tools=[
        find_character_by_name,
        list_all_characters,
        create_character,
        add_experience,
        set_character_level,
        add_inventory_item,
        remove_inventory_item,
        award_combat_rewards,
    ],
    name="Character Creator Agent",
    description= DESCRIPTION,
    system_prompt= SYSTEM_PROMPT
)

a2a_server = A2AServer(
    agent=agent,
    port=8001
)

if __name__ == "__main__":
    a2a_server.serve()
