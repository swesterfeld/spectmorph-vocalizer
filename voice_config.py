"""Read voice segment settings, including groups of local models."""
from pathlib import Path
import shlex


def read_voice_config(directory):
    directory = Path(directory)
    segments = {}
    owners = {}
    for config in directory.iterdir():
        if config.suffix != '.sh':
            continue
        properties = {}
        for number, line in enumerate(config.read_text().splitlines(), 1):
            words = shlex.split(line, comments=True)
            if not words:
                continue
            if len(words) != 1 or '=' not in words[0]:
                raise ValueError(f'{config}:{number}: expected KEY=value')
            key, value = words[0].split('=', 1)
            properties[key] = value
        if int(properties.get('VOICE_DISABLED', '0')):
            continue
        pattern = properties.get('VOICE_SEGMENT_GLOB')
        if pattern is None:
            names = [config.stem]
        else:
            if not pattern.endswith('.sm') or '/' in pattern or '\\' in pattern:
                raise ValueError(f'{config}: VOICE_SEGMENT_GLOB must match .sm filenames in the voice directory')
            models = sorted(path for path in directory.glob(pattern) if path.is_file())
            if not models:
                raise ValueError(f'{config}: no models match {pattern!r}')
            names = [model.stem for model in models]
            for name in names:
                for suffix in ('.txt', '.volume'):
                    companion = directory / (name + suffix)
                    if not companion.is_file():
                        raise ValueError(f'{config}: missing {companion}')
        for name in names:
            if name in segments:
                raise ValueError(f'Segment {name!r} is selected by both {owners[name]} and {config}')
            segments[name] = properties.copy()
            owners[name] = config
    return segments
