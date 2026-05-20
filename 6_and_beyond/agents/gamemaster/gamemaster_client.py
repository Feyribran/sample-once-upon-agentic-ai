import requests
import json


GAME_MASTER_URL = "http://127.0.0.1:8009/inquire"


def ask_gamemaster(question: str) -> dict:
    payload = {
        "question": question
    }

    response = requests.post(
        GAME_MASTER_URL,
        json=payload,
        timeout=120
    )

    response.raise_for_status()
    return response.json()


def pretty_print_response(data: dict) -> None:
    print("\n--- GameMaster response ---")

    raw_response = data.get("response")

    if raw_response is None:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    # Le gamemaster peut parfois renvoyer une string contenant du JSON.
    try:
        parsed = json.loads(raw_response)
        print(json.dumps(parsed, indent=2, ensure_ascii=False))
    except Exception:
        print(raw_response)


def main():
    print("🎲 GameMaster Client")
    print("Tape 'exit' pour quitter.")
    print()

    while True:
        question = input("Toi > ").strip()

        if question.lower() in ["exit", "quit", "q"]:
            print("Fin de session.")
            break

        if not question:
            continue

        try:
            result = ask_gamemaster(question)
            pretty_print_response(result)
        except requests.exceptions.ConnectionError:
            print("\nImpossible de joindre le GameMaster.")
            print("Vérifie que gamemaster_orchestrator.py tourne sur http://127.0.0.1:8009")
        except requests.exceptions.HTTPError as error:
            print(f"\nErreur HTTP: {error}")
            print(error.response.text)
        except Exception as error:
            print(f"\nErreur: {error}")


if __name__ == "__main__":
    main()