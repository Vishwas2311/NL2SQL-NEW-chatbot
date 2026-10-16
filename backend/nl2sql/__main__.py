"""Native CLI startup without a frontend or container requirement."""

import argparse
import json
import logging
from pathlib import Path

import uvicorn

from nl2sql.api import create_app
from nl2sql.config import load_settings
from nl2sql.domain import Failure
from nl2sql.embeddings import build_embedding
from nl2sql.metadata_cli import MetadataOptions, add_metadata_parser, run_metadata
from nl2sql.model import build_model
from nl2sql.synthetic import initialize


def main() -> None:
    """Initialize isolated demo files or run a securely configured API process."""
    parser = argparse.ArgumentParser(description="EWS synthetic NL-to-SQL backend")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init-demo", "serve", "validate-config"):
        command = commands.add_parser(name)
        command.add_argument("--settings", type=Path, default=Path(".local/settings.json"))
        command.add_argument("--port", type=int, default=8000)
        command.add_argument("--metadata-root", type=Path)
        command.add_argument("--env-file", type=Path)
        command.add_argument(
            "--catalog", type=Path, default=Path("metadata/synthetic/catalog-v43.json")
        )
    add_metadata_parser(commands.add_parser("metadata", help="Governed schema metadata operations"))
    arguments = parser.parse_args()
    if arguments.command == "metadata":
        try:
            print(
                json.dumps(
                    run_metadata(MetadataOptions.model_validate(vars(arguments))), default=str
                )
            )
        except Failure as error:
            parser.exit(1, json.dumps({"code": error.code, "message": error.message}) + "\n")
        except ImportError:
            parser.exit(
                1,
                json.dumps(
                    {
                        "code": "OPTIONAL_DEPENDENCY",
                        "message": "Install the selected adapter's approved optional dependency.",
                    }
                )
                + "\n",
            )
        except (ValueError, OSError):
            parser.exit(
                1, "Administrative input or local storage is invalid; no credentials are logged.\n"
            )
        return
    if arguments.command == "init-demo":
        initialize(arguments.settings.parent, arguments.catalog)
        print(
            "Synthetic backend initialized. Credentials: "
            f"{arguments.settings.parent / 'demo-credentials.json'}"
        )
        return
    try:
        configuration = load_settings(arguments.settings, arguments.env_file)
    except (ValueError, OSError):
        parser.exit(1, "Configuration is invalid; values and credentials are omitted.\n")
    if arguments.command == "validate-config":
        try:
            build_model(configuration).close()
            encoder = build_embedding(configuration)
            if encoder is not None:
                encoder.close()
        except (Failure, ValueError, OSError):
            parser.exit(1, "Provider configuration is invalid; values are omitted.\n")
        print(
            json.dumps(
                {
                    "valid": True,
                    "model": configuration.model_mode,
                    "embedding": configuration.embedding_mode,
                }
            )
        )
        return
    if arguments.metadata_root is not None:
        configuration = configuration.model_copy(
            update={"metadata_root": arguments.metadata_root.resolve()}
        )
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    uvicorn.run(create_app(configuration), host="127.0.0.1", port=arguments.port)


if __name__ == "__main__":
    main()
