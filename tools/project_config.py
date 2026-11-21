"""Optional local tool paths with command-line overrides."""
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def local_settings():
    path = ROOT/'project.local.json'
    if not path.exists():
        return {}
    settings = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(settings, dict):
        raise ValueError(f'Expected an object in {path}')
    return settings


def launcher_command(executable, data_dir=None):
    command = [str(executable)]
    if data_dir:
        command.extend(['--data-dir', str(data_dir)])
    return command


def require_active_game(launcher, expected_game):
    """Check the stock source used by hud compose, which has no --game flag."""
    if not expected_game:
        raise ValueError("Set the F1 25 game folder in project.local.json before composing")
    expected = Path(expected_game).resolve()
    if expected.name.lower() == "f1_25.exe":
        expected = expected.parent
    listing = subprocess.check_output(launcher + ["game", "list"], text=True)
    active = re.findall(r"^\*\s+.+?\s+\d+(?:\.\d+)+\s+(.+?)\s*$", listing, re.MULTILINE)
    if len(active) != 1:
        raise RuntimeError("Could not identify SWOFTY's active game from 'game list'")
    actual = Path(active[0]).resolve()
    if actual != expected:
        raise RuntimeError(
            f"SWOFTY's active game is {actual}, but the project targets {expected}. "
            "Select the matching copy before composing."
        )
