"""Optional local tool paths with command-line overrides."""
import json
from pathlib import Path

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
