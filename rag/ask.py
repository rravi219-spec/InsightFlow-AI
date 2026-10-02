"""CLI: python -m rag.ask 'How is RFM calculated?'"""
import argparse
import json

from rag.answering import ask

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    args = parser.parse_args()
    print(json.dumps(ask(args.question), ensure_ascii=False, indent=2))
