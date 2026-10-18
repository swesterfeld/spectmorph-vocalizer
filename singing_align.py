#!/usr/bin/env python3
"""Experimental duration-aware phoneme alignment for isolated sung items."""

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
import sys

import numpy as np

MODEL = 'facebook/wav2vec2-xlsr-53-espeak-cv-ft'
VOWELS = set('aAeEiIoOuUyY269@')
IPA = dict(zip('p b t d k g m n N f v s z S Z C j x h l ? @ 6 I U E O 2 9'.split(),
               'p b t d k ɡ m n ŋ f v s z ʃ ʒ ç j x h l ʔ ə ɐ ɪ ʊ ɛ ɔ ø œ'.split()))
IPA.update({c: c for c in 'aieouy'})
IPA['Y'] = 'ʏ'
IPA.update({'r': 'r', 'R': 'ʁ', 'ts': 'ts', 'tS': 'tʃ', 'dZ': 'dʒ',
            'pf': 'pf', 'aI': 'aɪ', 'aU': 'aʊ', 'OY': 'ɔø',
            'a_I': 'aɪ', 'a_U': 'aʊ', 'O_Y': 'ɔø'})


@dataclass
class Item:
    name: str
    phones: list[str]


@dataclass
class Phase:
    label: str
    source: str
    kind: str
    alternatives: list[str]
    nucleus: bool
    seconds: float


def expand_phones(phones, overrides, nucleus_seconds=1., consonant_seconds=.1,
                  closure_fraction=.6, transition_seconds=.1, tail_seconds=.1):
    """Expand transcript phones into independently aligned output intervals."""
    phases = []
    for phone in phones:
        base = phone.removesuffix('_}')
        if base in {'p', 'b', 't', 'd', 'k', 'g', '?'}:
            choices, _ = phone_spec(base, overrides)
            phases.append(Phase('.' + base, phone, 'closure', choices, False,
                                consonant_seconds * closure_fraction))
            # The label convention requires both phases even for unreleased stops.
            phases.append(Phase(phone, phone, 'release', choices, False,
                                consonant_seconds * (1 - closure_fraction)))
            continue
        pair = phone.replace('_', '').removesuffix(':')
        if len(pair) == 2 and all(c in VOWELS for c in pair) and pair[0] != pair[1]:
            left, right = pair
            first, _ = phone_spec(left, overrides)
            last, _ = phone_spec(right, overrides)
            if phone in overrides or phone.removesuffix(':') in IPA:
                transition, _ = phone_spec(phone, overrides)
            elif pair in IPA:
                transition, _ = phone_spec(pair, overrides)
            else:
                # No dedicated model token: use both component classes as a proxy.
                transition = list(dict.fromkeys(first + last))
            phases.extend([
                Phase(left, phone, 'nucleus', first, True, nucleus_seconds),
                Phase(pair, phone, 'transition', transition, False, transition_seconds),
                Phase(right, phone, 'tail', last, False, tail_seconds)])
            continue
        choices, nucleus = phone_spec(phone, overrides)
        phases.append(Phase(phone, phone, 'phone', choices, nucleus,
                            nucleus_seconds if nucleus else consonant_seconds))
    return phases


def phase_scores(emissions, samples, phases):
    """Low-energy closure / higher-energy release proxy, not a burst classifier."""
    frames = len(emissions)
    if frames == 0 or len(samples) < frames:
        raise ValueError('Not enough samples for phase alignment')
    edges = np.linspace(0, len(samples), frames + 1).astype(int)
    energy = np.array([np.mean(samples[a:b].astype(np.float64) ** 2)
                       for a, b in zip(edges, edges[1:])])
    db = 10 * np.log10(np.maximum(energy, 1e-12))
    # Relative to the item's loud frames; voiced closures may have residual energy.
    quiet_logit = (np.percentile(db, 90) - 18. - db) / 6.
    quiet = -np.logaddexp(0., -quiet_logit)
    loud = -np.logaddexp(0., quiet_logit)
    result = emissions.copy()
    for column, phase in enumerate(phases):
        if phase.kind == 'closure':
            result[:, column] = quiet
        elif phase.kind == 'release' and not phase.source.endswith('_}'):
            result[:, column] += loud
    return result


def inter_item_labels(groups):
    """Insert a silence interval between every pair of item label groups."""
    labels = []
    for group in groups:
        if not group:
            raise ValueError('An item has no labels')
        if labels:
            start, end = labels[-1][1], group[0][0]
            if end < start:
                raise ValueError('Item labels overlap')
            # A zero-length gap is an Audacity point label, never invented silence.
            labels.append((start, end, '_'))
        labels.extend(group)
    return labels


def read_items(path):
    """One item per line: SAMPA, name<TAB>SAMPA, or name: SAMPA."""
    items = []
    for number, line in enumerate(Path(path).read_text(encoding='utf-8-sig').splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '\t' in line:
            name, transcription = line.split('\t', 1)
        elif ': ' in line:
            name, transcription = line.split(': ', 1)
        else:
            name, transcription = str(len(items) + 1), line
        phones = transcription.split()
        if not name.strip() or not phones:
            raise ValueError(f'{path}:{number}: empty item or transcription')
        items.append(Item(name.strip(), phones))
    if not items:
        raise ValueError('The transcription list is empty')
    return items


def phone_spec(phone, overrides):
    """Return acoustic alternatives and explicit nucleus status; never guess syllabicity."""
    if phone in overrides:
        spec = overrides[phone]
        if (not isinstance(spec, dict) or not isinstance(spec.get('nucleus'), bool)
                or not isinstance(spec.get('ipa'), list) or not spec['ipa']
                or not all(isinstance(x, str) and x for x in spec['ipa'])):
            raise ValueError(f'Invalid mapping for {phone}: need ipa list and nucleus boolean')
        return spec['ipa'], spec['nucleus']
    base = phone
    syllabic = base.endswith('=')
    if syllabic:
        base = base[:-1]
    if len(base) == 3 and base[1] == '_' and base[0] == base[2]:
        base, syllabic = base[0], True
    base = base.removesuffix('_}')  # Unreleased stop: same acoustic class.
    long = base.endswith(':')
    base = base.removesuffix(':')
    if base not in IPA:
        raise ValueError(f'Unsupported SAMPA symbol {phone!r}; provide --mapping')
    ipa = IPA[base]
    choices = [ipa]
    if syllabic:
        choices = [ipa + '\u0329', ipa]
    elif base[0] in VOWELS:
        choices = [ipa + 'ː', ipa] if long else [ipa, ipa + 'ː']
    if base == 'Y':
        choices.append('y')  # The default model lacks the near-close rounded vowel.
    return choices, syllabic or base[0] in VOWELS


def detect_regions(levels, hop, duration, threshold_db=-45, min_pause=.5, pad=.04):
    active = np.flatnonzero(np.asarray(levels) > threshold_db)
    if not len(active):
        return []
    breaks = np.flatnonzero((np.diff(active) - 1) * hop >= min_pause)
    starts = np.r_[active[0], active[breaks + 1]]
    ends = np.r_[active[breaks], active[-1]]
    return [(max(0., s * hop - pad), min(duration, (e + 1) * hop + pad))
            for s, e in zip(starts, ends)]


def scan_audio(path, threshold_db, min_pause):
    import soundfile as sf
    levels = []
    with sf.SoundFile(path) as audio:
        rate, duration = audio.samplerate, len(audio) / audio.samplerate
        window = max(1, round(rate * .01))
        # Read ten seconds at a time, retaining only RMS values for a nine-hour file.
        while True:
            block = audio.read(window * 1000, dtype='float32', always_2d=True)
            if not len(block):
                break
            for start in range(0, len(block), window):
                frame = block[start:start + window].astype(np.float64)
                rms = np.sqrt(np.mean(frame ** 2, axis=0)).max()
                levels.append(20 * np.log10(max(rms, 1e-12)))
    return detect_regions(levels, window / rate, duration, threshold_db, min_pause), duration


def read_regions(path, duration):
    result = []
    for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
        if not line.strip():
            continue
        fields = line.split('\t')
        if len(fields) >= 3 and fields[2].strip() == '_':
            continue  # Exported item tracks also contain inter-item silence.
        if len(fields) < 2:
            raise ValueError('Segments must be Audacity interval labels (start<TAB>end<TAB>name)')
        start, end = map(float, fields[:2])
        if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end <= duration):
            raise ValueError(f'Invalid interval: {line}')
        if result and start < result[-1][1]:
            raise ValueError('Segments must be ordered and non-overlapping')
        result.append((start, end))
    return result


def write_labels(path, labels, *, points=False):
    """Audacity represents a point label with equal start and end timestamps."""
    Path(path).write_text(''.join(f'{start:.6f}\t{(start if points else end):.6f}\t{name}\n'
                                for start, end, name in labels), encoding='utf-8')


def align_durations(emissions, step, nuclei, nucleus_seconds=1., consonant_seconds=.1,
                    duration_weight=3., means=None):
    """Semi-Markov Viterbi: each phone occupies one contiguous, nonempty interval.

    emissions[T, P] are per-frame log acoustic scores. Bounds are deliberately
    broad; Gaussian duration priors favour the recording protocol, not fixed slots.
    """
    frames, phones = emissions.shape
    if phones != len(nuclei) or phones == 0 or frames < phones:
        raise ValueError('Not enough audio frames for the transcription')
    if not np.all(np.isfinite(emissions)):
        raise ValueError('Non-finite acoustic scores')
    if means is not None and (len(means) != phones or
                              any(not math.isfinite(x) or x <= 0 for x in means)):
        raise ValueError('Each phase needs a positive finite duration')
    previous = np.full(frames + 1, -np.inf)
    previous[0] = 0.
    back = np.zeros((phones, frames + 1), dtype=np.int32)
    endpoints = np.arange(frames + 1)
    for phone, nucleus in enumerate(nuclei):
        mean = means[phone] if means is not None else (nucleus_seconds if nucleus else consonant_seconds)
        sigma = mean * (.45 if nucleus else .8)
        minimum = max(1, math.ceil((.15 * mean if nucleus else .01) / step))
        maximum = min(frames, max(minimum, math.ceil((3 * mean if nucleus else 6 * mean) / step)))
        cumulative = np.r_[0., np.cumsum(emissions[:, phone])]
        current = np.full(frames + 1, -np.inf)
        for length in range(minimum, maximum + 1):
            penalty = duration_weight * .5 * ((length * step - mean) / sigma) ** 2
            candidate = previous[:-length] + cumulative[length:] - cumulative[:-length] - penalty
            better = candidate > current[length:]
            indices = endpoints[length:][better]
            current[indices] = candidate[better]
            back[phone, indices] = length
        previous = current
    if not np.isfinite(previous[-1]):
        raise ValueError('No duration-compatible alignment; check segments, syllabicity and duration options')
    end, spans = frames, []
    for phone in reversed(range(phones)):
        start = end - int(back[phone, end])
        spans.append((start, end))
        end = start
    return list(reversed(spans))


class AcousticModel:
    def __init__(self, name, device):
        import torch
        from transformers import AutoFeatureExtractor, AutoModelForCTC, AutoTokenizer
        self.torch, self.device = torch, device
        self.extractor = AutoFeatureExtractor.from_pretrained(name)
        self.vocab = AutoTokenizer.from_pretrained(name, do_phonemize=False).get_vocab()
        self.model = AutoModelForCTC.from_pretrained(name).to(device).eval()
        self.blank = self.model.config.pad_token_id
        if self.extractor.sampling_rate != 16000:
            raise ValueError('This prototype requires a 16 kHz acoustic model')

    def token_ids(self, alternatives):
        ids = [self.vocab[x] for x in alternatives if x in self.vocab]
        if not ids:
            raise ValueError(f'Model has none of the required IPA tokens: {alternatives}')
        return sorted(set(ids))

    def scores(self, samples, ids):
        inputs = self.extractor(samples, sampling_rate=16000, return_tensors='pt')
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with self.torch.inference_mode():
            logits = self.model(**inputs).logits[0]
            logp = logits.log_softmax(-1).cpu().numpy()
        # CTC blank means "no new token", not silence. Permit it inside held
        # phones; duration priors distribute uninformative blank frames.
        scores = np.column_stack([
            np.logaddexp.reduce(logp[:, token_ids + [self.blank]], axis=1)
            for token_ids in ids])
        return scores


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('audio', type=Path)
    p.add_argument('transcriptions', type=Path)
    p.add_argument('--output-prefix', type=Path, default=Path('alignment'))
    p.add_argument('--segments', type=Path, help='Manually checked Audacity item intervals')
    p.add_argument('--segments-only', action='store_true', help='Detect item intervals without downloading a model')
    p.add_argument('--threshold-db', type=float, default=-45., help='RMS threshold in dBFS (default: -45)')
    p.add_argument('--min-pause', type=float, default=.5)
    p.add_argument('--nucleus-seconds', type=float, default=1.)
    p.add_argument('--consonant-seconds', type=float, default=.1)
    p.add_argument('--duration-weight', type=float, default=3.)
    p.add_argument('--closure-fraction', type=float, default=.6,
                   help='Expected closure fraction of a released stop (default: 0.6)')
    p.add_argument('--transition-seconds', type=float, default=.1,
                   help='Expected diphthong transition duration')
    p.add_argument('--tail-seconds', type=float, default=.1,
                   help='Expected nonsyllabic diphthong tail duration')
    p.add_argument('--max-item-seconds', type=float, default=30., help='Memory guard for model inference')
    p.add_argument('--mapping', type=Path, help='JSON: SAMPA -> {ipa: [model tokens], nucleus: boolean}')
    p.add_argument('--model', default=MODEL)
    p.add_argument('--device', default='cpu')
    return p


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    for name in ['min_pause', 'nucleus_seconds', 'consonant_seconds', 'duration_weight',
                 'max_item_seconds', 'transition_seconds', 'tail_seconds', 'closure_fraction']:
        if not math.isfinite(getattr(args, name)) or getattr(args, name) <= 0:
            p.error(f'--{name.replace("_", "-")} must be finite and positive')
    if args.closure_fraction >= 1:
        p.error('--closure-fraction must be between 0 and 1')
    if args.min_pause <= .08 or not math.isfinite(args.threshold_db):
        p.error('--min-pause must exceed 0.08 seconds and --threshold-db must be finite')
    try:
        import soundfile as sf
        from scipy.signal import resample_poly
        items = read_items(args.transcriptions)
        overrides = json.loads(args.mapping.read_text(encoding='utf-8')) if args.mapping else {}
        if not isinstance(overrides, dict):
            raise ValueError('Mapping must be a JSON object')
        if args.segments:
            info = sf.info(args.audio)
            regions = read_regions(args.segments, info.frames / info.samplerate)
        else:
            regions, _ = scan_audio(args.audio, args.threshold_db, args.min_pause)
        prefix = args.output_prefix
        prefix.parent.mkdir(parents=True, exist_ok=True)
        candidates_path = Path(str(prefix) + '.candidates.txt')
        if args.segments and candidates_path.resolve() == args.segments.resolve():
            raise ValueError('Output candidates would overwrite the supplied segments; choose another prefix')
        write_labels(candidates_path, [(s, e, str(i + 1)) for i, (s, e) in enumerate(regions)])
        if len(regions) != len(items):
            raise ValueError(f'{len(regions)} audio regions, but {len(items)} items. '
                             f'Check {candidates_path} in Audacity, then use --segments; no item mapping written.')
        if args.segments_only:
            print(f'{len(regions)} candidate regions: {candidates_path}. Check their correspondence manually.')
            return 0
        specs = [expand_phones(item.phones, overrides, args.nucleus_seconds,
                               args.consonant_seconds, args.closure_fraction,
                               args.transition_seconds, args.tail_seconds) for item in items]
        if any(e - s > args.max_item_seconds for s, e in regions):
            raise ValueError('An item exceeds --max-item-seconds; check segmentation or explicitly increase the limit')
        model = AcousticModel(args.model, args.device)
        all_ids = [[model.token_ids(phase.alternatives) for phase in item] for item in specs]
        groups, report = [], []
        with sf.SoundFile(args.audio) as audio:
            for index, (item, (start, end), spec, ids) in enumerate(zip(items, regions, specs, all_ids)):
                print(f'{index + 1}/{len(items)}: {item.name}', file=sys.stderr, flush=True)
                first, last = round(start * audio.samplerate), round(end * audio.samplerate)
                audio.seek(first)
                samples = audio.read(last - first, dtype='float32', always_2d=True)
                # Select strongest channel to avoid phase cancellation in stereo.
                channel = np.argmax(np.mean(samples.astype(np.float64) ** 2, axis=0))
                divisor = math.gcd(audio.samplerate, 16000)
                mono = resample_poly(samples[:, channel], 16000 // divisor, audio.samplerate // divisor)
                emissions = model.scores(mono, ids)
                emissions = phase_scores(emissions, mono, spec)
                step = (last - first) / audio.samplerate / len(emissions)
                spans = align_durations(emissions, step, [phase.nucleus for phase in spec],
                                        duration_weight=args.duration_weight,
                                        means=[phase.seconds for phase in spec])
                group = []
                for phase, (a, b) in zip(spec, spans):
                    s, e = first / audio.samplerate + a * step, first / audio.samplerate + b * step
                    group.append((s, e, phase.label))
                    expected = phase.seconds
                    report.append(dict(item=index + 1, name=item.name, phone=phase.label, start=s, end=e,
                                       source_phone=phase.source, phase=phase.kind, expected_seconds=expected,
                                       nucleus=phase.nucleus, duration_warning=not .5 * expected <= e - s <= 2 * expected))
                groups.append(group)
        labels = inter_item_labels(groups)
        write_labels(str(prefix) + '.phones.txt', labels, points=True)
        write_labels(str(prefix) + '.items.txt', inter_item_labels(
            [[(s, e, item.name)] for item, (s, e) in zip(items, regions)]))
        Path(str(prefix) + '.report.json').write_text(json.dumps(dict(
            model=args.model, experimental=True, settings={k: str(v) if isinstance(v, Path) else v
                                                          for k, v in vars(args).items()},
            phones=report, silences=[dict(start=s, end=e, phone='_')
                                    for s, e, name in labels if name == '_']),
            ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f'Wrote {prefix}.phones.txt, {prefix}.items.txt and {prefix}.report.json')
        return 0
    except (ValueError, OSError, ImportError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
