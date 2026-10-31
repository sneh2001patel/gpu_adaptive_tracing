"""Transparent threshold rule for the empirical study (EXTERNAL_INSTRUMENT_AND_DIAGNOSIS_RULE.md §3).

Every threshold lives in RuleThresholds, which carries a version and hash. An unset threshold is None and the
dependent condition evaluates to unknown, never to false: the rule cannot be run on evaluation data until
calibration fills and freezes the config. Inputs are measured values only; no workload or case name enters.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass

RULE_VERSION = 'study_rule_v2_draft'  # v2 (step 053): in-flight latency, pending-work guard, per-token family time
CATEGORIES = ('queue_pressure', 'kv_pressure', 'host_bound', 'kernel_hotspot', 'healthy', 'unknown')


@dataclass(frozen=True)
class RuleThresholds:
    latency_ratio: float | None = None       # theta_L: p95 in-flight request age / healthy baseline of the same measure
    waiting_requests: float | None = None    # theta_w
    kv_usage: float | None = None            # theta_u, 0-1
    preemptions_per_s: float | None = None   # theta_p
    gpu_util: float | None = None            # theta_g, 0-1 (NVML)
    busy_fraction: float | None = None       # theta_b, 0-1 (Nsight)
    kernel_time_ratio: float | None = None   # theta_r: GPU ns per processed token of a kernel family / baseline
    version: str = RULE_VERSION

    def digest(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()

    def frozen(self):
        return all(v is not None for k, v in asdict(self).items() if k != 'version')


@dataclass(frozen=True)
class CheapWindow:
    latency_ratio: float | None
    waiting_requests: float | None
    kv_usage: float | None
    preemptions_per_s: float | None   # None when the release does not expose preemptions
    gpu_util: float | None
    running_requests: float | None = None


@dataclass(frozen=True)
class HeavyBurst:
    evidence_id: str
    busy_fraction: float
    family_ns_per_token: dict | None  # kernel family -> GPU ns per token processed during the capture; None if
                                      # the token count is unavailable
    baseline_ns_per_token: dict | None  # same measure, healthy baseline capture of the same deployment
    family_top_kernel: dict | None = None  # family -> kernel with the most time in that family (reported only)


@dataclass(frozen=True)
class RuleDiagnosis:
    causes: tuple                     # sorted subset of CATEGORIES (kernel_hotspot carries its family in `kernel`)
    kernel: str | None                # kernel family for kernel_hotspot (stable across bursts)

    reasons: tuple
    evidence_id: str | None
    thresholds_digest: str
    rule_version: str = RULE_VERSION
    top_kernel: str | None = None     # reported, not part of the label

    @property
    def label(self):
        """Canonical single string for stability comparison; None for unknown. 'healthy' is returned but is not
        a concrete label for the stopping policies (policies.is_concrete_label)."""
        if self.causes in ((), ('unknown',)):
            return None
        parts = [f'kernel_hotspot:{self.kernel}' if c == 'kernel_hotspot' else c for c in self.causes]
        return '+'.join(parts)


def _ge(value, threshold):
    """Three-valued comparison: None when either side is missing."""
    return None if value is None or threshold is None else value >= threshold


def diagnose(cheap: CheapWindow, thresholds: RuleThresholds, heavy: HeavyBurst | None = None,
             *, assume_elevated: bool = False) -> RuleDiagnosis:
    """assume_elevated: inside an active episode, assess the cause conditions for the incident under
    investigation without re-gating on the current window's latency. Recovery is judged separately by the
    stopping policy, so a stable cause and recovered counters can co-occur (hybrid stop)."""
    t, reasons = thresholds, []
    elevated = True if assume_elevated else _ge(cheap.latency_ratio, t.latency_ratio)
    if elevated is None:
        return RuleDiagnosis(('unknown',), None, ('missing:latency_ratio_or_threshold',),
                             heavy.evidence_id if heavy else None, t.digest())
    if not elevated:
        return RuleDiagnosis(('healthy',), None, ('latency_not_elevated',),
                             heavy.evidence_id if heavy else None, t.digest())
    causes, kernel = set(), None

    preempting = _ge(cheap.preemptions_per_s, t.preemptions_per_s)
    kv_full = _ge(cheap.kv_usage, t.kv_usage)
    queued = None if cheap.waiting_requests is None else cheap.waiting_requests >= 1
    kv_alt = None if kv_full is None or queued is None else (kv_full and queued)
    kv = True if (preempting or kv_alt) else (None if preempting is None and kv_alt is None else False)
    if kv:
        causes.add('kv_pressure')
    elif kv is None:
        reasons.append('unknown:kv_pressure')

    gpu_busy_cheap = _ge(cheap.gpu_util, t.gpu_util)
    # host_bound needs pending work: an idle GPU with nothing to serve is not host-bound (step 052, flaw 1).
    counts = [c for c in (cheap.waiting_requests, cheap.running_requests) if c is not None]
    pending = None if not counts else any(c >= 1 for c in counts)
    top_kernel = None
    if heavy is not None:
        busy = _ge(heavy.busy_fraction, t.busy_fraction)
        if busy is False:
            if pending:
                causes.add('host_bound')
                reasons.append('heavy:busy_fraction_below_threshold')
            else:
                reasons.append('unknown:host_bound_without_pending_work' if pending is None else 'idle_without_pending_work')
        elif busy is None:
            reasons.append('unknown:busy_fraction')
        else:
            ratio, family = _largest_time_ratio(heavy.family_ns_per_token, heavy.baseline_ns_per_token)
            hot = _ge(ratio, t.kernel_time_ratio)
            if hot:
                causes.add('kernel_hotspot')
                kernel = family
                top_kernel = (heavy.family_top_kernel or {}).get(family)
            elif hot is None:
                reasons.append('unknown:kernel_time_per_token')
    elif gpu_busy_cheap is False:
        if pending:
            causes.add('host_bound')
            reasons.append('cheap:gpu_util_below_threshold')
        else:
            reasons.append('unknown:host_bound_without_pending_work' if pending is None else 'idle_without_pending_work')
    elif gpu_busy_cheap is None:
        reasons.append('unknown:gpu_util')

    if not kv and 'host_bound' not in causes:
        many = _ge(cheap.waiting_requests, t.waiting_requests)
        if many and gpu_busy_cheap:
            causes.add('queue_pressure')
        elif many is None or gpu_busy_cheap is None:
            reasons.append('unknown:queue_pressure')

    if not causes:
        causes, reasons = {'unknown'}, reasons + ['elevated_latency_without_firing_condition']
    return RuleDiagnosis(tuple(sorted(causes)), kernel, tuple(reasons),
                         heavy.evidence_id if heavy else None, t.digest(), top_kernel=top_kernel)


def _largest_time_ratio(per_token, baseline):
    """Largest per-token GPU time ratio over families present in both; families absent from the baseline are skipped."""
    if not per_token or not baseline:
        return None, None
    ratios = {f: per_token[f] / baseline[f] for f in per_token if baseline.get(f)}
    if not ratios:
        return None, None
    family = max(ratios, key=ratios.get)
    return ratios[family], family


# Kernel families, matched on the kernel identity (kernel_identity). Order matters: first match wins.
FAMILIES = (
    ('attention', re.compile(r'flash|attn|attention|paged|fmha|xformers|mha|reshape_and_cache', re.I)),
    ('gemm', re.compile(r'gemm|cutlass|cublas|scaled_mm|matmul|xmma|wgmma|marlin|sm\d+_.*mma', re.I)),
    ('norm', re.compile(r'norm', re.I)),
)


def kernel_family(identity: str) -> str:
    for family, pattern in FAMILIES:
        if pattern.search(identity):
            return family
    return 'other'


def family_time_per_token(kernel_totals, tokens):
    """kernel_totals: (identity, ns) pairs; tokens: tokens processed during the capture (prompt + generated).

    Returns (family -> ns per token, family -> top kernel identity), or (None, top) when tokens is missing or 0.
    """
    totals, top = {}, {}
    for name, ns in kernel_totals:
        f = kernel_family(name)
        totals[f] = totals.get(f, 0) + ns
        if ns > top.get(f, (None, -1))[1]:
            top[f] = (name, ns)
    tops = {f: v[0] for f, v in top.items()}
    if not tokens:
        return None, tops
    return {f: ns / tokens for f, ns in totals.items()}, tops


_IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_:]*')


def kernel_identity(demangled: str, short: str | None) -> str:
    """Identity from Nsight's shortName (bare function name) plus a plain-identifier first template argument.

    Preferred over parsing the demangled name, whose templated return types (e.g. std::enable_if<...>::type)
    defeat left-to-right parsing. Falls back to normalize_kernel_name when no shortName is available.
    """
    if not short:
        return normalize_kernel_name(demangled)
    pos = demangled.rfind(short + '<')
    if pos < 0:
        return short
    arg = normalize_kernel_name('f' + demangled[pos + len(short):])
    return f'{short}{arg[1:]}' if arg.startswith('f<') else short


def normalize_kernel_name(name: str) -> str:
    """Comparable kernel identity across captures.

    Keeps the function name and, when the first template argument is a plain identifier (CUTLASS-style wrappers
    put the kernel configuration there, e.g. cutlass::Kernel<cutlass_80_..._gemm_..._tn_align8>), that argument.
    Drops the return type, other template arguments, parameter lists and lambdas, which vary per launch site.
    """
    text = name.replace('<unnamed>', 'anon').replace('(anonymous namespace)', 'anon').removeprefix('void ')
    base, depth = [], 0
    for ch in text:                      # pass 1: depth-0 characters up to the parameter list
        if ch == '(' and depth == 0:
            break
        depth += (ch == '<') - (ch == '>')
        if depth == 0 and ch != '>':
            base.append(ch)
    arg, depth = [], 0
    for ch in text:                      # pass 2: the first top-level template argument
        if ch == '<':
            depth += 1
            if depth == 1:
                continue
        elif ch == '>':
            depth -= 1
            if depth == 0:
                break
        elif ch == ',' and depth == 1:
            break
        if depth >= 1:
            arg.append(ch)
    base_name, first = ''.join(base).strip() or name, ''.join(arg).strip()
    return f'{base_name}<{first}>' if first and _IDENT.fullmatch(first) else base_name


def busy_fraction(intervals, window_start_ns, window_end_ns):
    """Fraction of the window covered by the union of (start, end) GPU activity intervals."""
    if window_end_ns <= window_start_ns:
        raise ValueError('Empty capture window')
    covered, cursor = 0, window_start_ns
    for start, end in sorted((max(s, window_start_ns), min(e, window_end_ns)) for s, e in intervals):
        if end <= cursor:
            continue
        covered += end - max(start, cursor)
        cursor = end
    return covered / (window_end_ns - window_start_ns)


def kernel_shares(kernels):
    """kernels: iterable of (name, total_ns). Shares per normalized name, summing to 1."""
    totals = {}
    for name, ns in kernels:
        key = normalize_kernel_name(name)
        totals[key] = totals.get(key, 0) + ns
    whole = sum(totals.values())
    if whole <= 0:
        raise ValueError('No kernel time')
    return {k: v / whole for k, v in totals.items()}
