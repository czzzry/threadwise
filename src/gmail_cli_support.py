from pathlib import Path

from src.live_gmail_client import GMAIL_READONLY_SCOPE, LiveGmailClient


def default_gmail_client_factory(
    account_id: str,
    credentials_dir: Path,
    client_secret_path: Path | None,
    required_scope: str = GMAIL_READONLY_SCOPE,
) -> object:
    return LiveGmailClient.from_local_oauth(
        account_id,
        credentials_dir,
        client_secret_path=client_secret_path,
        scope=required_scope,
    )
