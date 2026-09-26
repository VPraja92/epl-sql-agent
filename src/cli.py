"""
cli.py

Run this to chat with the EPL agent from your terminal:

    python src/cli.py

Type 'exit' or 'quit' to stop.
"""

from agent import EPLAgent


def main():
    agent = EPLAgent()
    print("EPL SQL Agent -- ask a question about the database ('exit' to quit)\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if user_input.lower() in {"exit", "quit"}:
            print("Goodbye.")
            break
        if not user_input:
            continue

        answer = agent.ask(user_input)
        print(f"\nAgent: {answer}\n")


if __name__ == "__main__":
    main()
