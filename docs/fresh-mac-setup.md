# Set Up Threadwise on a Fresh Mac

Status: Current portability guide
Current as of: 2026-08-14

This guide gets the same Threadwise code running on another Mac without putting private email, passwords, OAuth tokens, or API keys in GitHub.

## Before You Start

Install:

- Brave Browser
- Xcode Command Line Tools: `xcode-select --install`
- Python 3.12 or newer: `python3 --version`
- Node.js if you want to run the JavaScript checks: `node --version`
- Proton Mail Bridge only if this Mac will use the Proton workflow

Docker is optional and is needed only for the containerized synthetic demo.

## 1. Download the Code

In Terminal, choose a private development folder and run:

```bash
mkdir -p ~/Developer
cd ~/Developer
git clone https://github.com/czzzry/threadwise.git
cd threadwise
git switch main
git pull --ff-only
```

Whenever work is pushed from another computer, update this Mac with:

```bash
cd ~/Developer/threadwise
git pull --ff-only
```

## 2. Prove the Safe Simulator Works

This uses only synthetic example messages. It does not connect to Gmail or change any inbox.

```bash
python3 scripts/run_gmail_companion_simulator.py
```

Open [http://127.0.0.1:8031/simulator](http://127.0.0.1:8031/simulator). Stop the simulator with `Control-C` in Terminal.

## 3. Add Private Settings Locally

Create a private settings file from the safe template:

```bash
cp .env.example .env
```

Open `.env` in a local text editor and add the API key and model names you intend to use. Threadwise recognizes:

- `EMAIL_AGENT_OPENAI_API_KEY` (preferred) or `OPENAI_API_KEY` (fallback)
- `THREADWISE_CLASSIFICATION_MODEL` for explicitly enabling model-assisted initial labeling
- `THREADWISE_TEACHING_MODEL` for correction and teaching interpretation

Leaving `THREADWISE_CLASSIFICATION_MODEL` blank keeps initial classification deterministic. No paid initial-classification model is selected implicitly.

The `.env` file is ignored by Git. Never paste its values into an issue, pull request, screenshot, chat, test fixture, or committed file.

## 4. Connect Providers Privately

### Gmail

GitHub does not carry Gmail access. On the Mac, place the Google OAuth desktop-app download at:

```text
data/gmail_credentials/client_secret.json
```

Threadwise stores the resulting per-account token at:

```text
data/gmail_credentials/gmail_tokens/<gmail-account-id>.json
```

Both locations are ignored by Git. The safest fresh-Mac route is to download the OAuth client file through your Google Cloud project and authorize the Mac again, which creates a new local token. If you instead transfer an existing secret or token, use an encrypted, direct transfer and never Git, email, or a shared cloud folder.

To perform a deliberately bounded, read-only authorization check, replace the placeholder with the same local account ID you plan to use:

```bash
python3 scripts/manual_gmail_fetch.py --account-id <gmail-account-id> --batch-size 1
```

This opens Google's local authorization flow and reads at most one message into private local storage. Do this only when you are ready to let this Mac access that Gmail account. Do not use a write-enabled workflow merely to test setup.

If Python reports a certificate-verification problem, run the `Install Certificates.command` supplied with your Python installation, then retry.

### Proton Mail (optional)

Sign in to Proton Mail Bridge locally and copy the Bridge-provided IMAP connection values into this ignored file:

```text
data/protonmail_credentials/protonmail_bridge/founder-proton.json
```

The existing companion and installed daily schedule use the local account ID `founder-proton`. The file shape is:

```json
{
  "host": "<Bridge IMAP host>",
  "port": "<Bridge IMAP port>",
  "username": "<Bridge IMAP username>",
  "password": "<Bridge IMAP password>"
}
```

Use the exact host, port, username, and password shown by Bridge; the Bridge password is not the Proton account password. If Bridge specifies STARTTLS, also add `"ssl": false` and `"security": "STARTTLS"`; otherwise `ssl` defaults to `true`. This file is ignored by Git and must never be committed or pasted into a shared channel.

With Bridge running, a bounded read-only check is:

```bash
python3 scripts/live_protonmail_fetch.py --account-id founder-proton --batch-size 1
```

## 5. Start the Companion Manually

From the repo root:

```bash
python3 scripts/run_gmail_companion.py
```

The companion runs locally at [http://127.0.0.1:8021](http://127.0.0.1:8021). Keep that Terminal window open while testing; stop it with `Control-C`.

The production companion can expose bounded label actions. During a setup check, use only the agreed read-only Gmail check and review surfaces; do not approve a label correction or any other provider write unless that exact live action has been separately approved. Threadwise does not expose archive, delete, Trash, Spam, unsubscribe, or send actions.

## 6. Load the Brave Extension

1. Open `brave://extensions` in Brave.
2. Turn on **Developer mode**.
3. Click **Load unpacked**.
4. Select `extensions/gmail_companion` inside this clone.
5. Open or refresh Gmail or Proton Mail. Threadwise should connect to the local companion on port `8021`.

After pulling extension changes, return to `brave://extensions`, click **Reload** on Threadwise, and refresh the provider tab. If the clone moves to another folder, remove the old unpacked extension entry and load it again from the new path.

## 7. Install Startup and Menu-Bar Control

First stop the manually started companion. Then run:

```bash
python3 scripts/manage_threadwise_startup.py install
python3 scripts/install_threadwise_control.py
python3 scripts/manage_threadwise_startup.py status
```

This creates a user-level background service plus `~/Applications/Threadwise Control.app`. The startup installer also registers the existing Proton daily schedule; Proton remains inactive in practice unless its private Bridge configuration is present, but install Proton Mail Bridge and review that workflow before relying on it.

The generated service and menu app store absolute paths. If you move the clone, change Python installations, or create a new clone, run both install commands again from the new repo root. This refreshes:

- `~/Library/LaunchAgents/com.threadwise.companion.plist`
- `~/Library/LaunchAgents/com.threadwise.proton-daily.plist`
- `~/Library/LaunchAgents/com.threadwise.control.plist`
- `~/Applications/Threadwise Control.app`

Then reload the Brave extension from the new `extensions/gmail_companion` folder.

## 8. Run the Checks

From the repo root:

```bash
python3 -m unittest discover -s tests
node --test tests/test_public_demo_model.mjs
python3 scripts/check_public_data_hygiene.py
```

The public-data check should pass before every push. It scans committed and untracked public files for common private-data residue.

## What GitHub Does Not Transfer

GitHub transfers the source code, tests, documentation, extension, and commit history. It intentionally does not transfer:

- `.env` or API keys
- Gmail OAuth client secrets or Gmail tokens
- private Gmail, Proton, or Outlook message data and run artifacts under `data/`
- Proton Mail Bridge credentials or its signed-in application state
- browser profiles, Gmail login sessions, or the locally loaded unpacked extension
- installed LaunchAgents, logs, or `Threadwise Control.app`
- machine-specific Python or Node installations

Keep those items local. Re-authorize services and reinstall the local startup pieces on each Mac rather than weakening the repository's privacy boundary.

## Safe Update Routine

After a new Threadwise push:

```bash
cd ~/Developer/threadwise
git pull --ff-only
python3 -m unittest discover -s tests
python3 scripts/check_public_data_hygiene.py
```

Reload the Brave extension if extension files changed. Re-run both installers only if the repo path, Python path, startup code, or menu-bar code changed.
