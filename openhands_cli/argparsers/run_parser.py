import argparse
from pathlib import Path


def add_run_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "run",
        help="Run one task unattended with JSONL output and durable artifacts",
        description=(
            "Run OpenHands without a terminal UI or interactive fallback. "
            "LLM_API_KEY and LLM_MODEL are required; LLM_BASE_URL is optional."
        ),
    )
    task_source = parser.add_mutually_exclusive_group(required=True)
    task_source.add_argument("-t", "--task", help="Task text to execute")
    task_source.add_argument(
        "-f",
        "--file",
        type=Path,
        help="UTF-8 file containing the task text",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        required=True,
        help="Existing writable workspace OpenHands may modify",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for events.jsonl and run.json",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Disable optional startup network fetches, including public skills",
    )
    parser.add_argument(
        "--no-public-skills",
        dest="load_public_skills",
        action="store_false",
        default=True,
        help="Do not fetch or load the OpenHands public skills repository",
    )
    parser.add_argument(
        "--no-user-skills",
        dest="load_user_skills",
        action="store_false",
        default=True,
        help="Do not load skills from user-level directories",
    )
    parser.add_argument(
        "--llm-timeout",
        type=int,
        default=300,
        help="Provider request timeout in seconds (default: 300)",
    )
    parser.add_argument(
        "--llm-retries",
        type=int,
        default=5,
        help="Provider request retry count (default: 5)",
    )
