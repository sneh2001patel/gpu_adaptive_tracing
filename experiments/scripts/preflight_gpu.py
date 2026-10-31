#!/usr/bin/env python3
"""Passive deployment inventory by default; opt-in isolated NVML read probe."""
import argparse
import asyncio
import importlib.util
import json
import os
import platform
import shutil
import sys
from dataclasses import asdict
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.tracing.nvml_sampler import NvmlConfig, NvmlSampler
from experiments.tracing.producers import ProducerConfig
from experiments.tracing.timing import MonotonicClock
from experiments.tracing.windows import HealthyBaseline


def inventory():
    try:
        binding = version('nvidia-ml-py')
    except PackageNotFoundError:
        binding = None
    return dict(preflight_version='preflight_v1', mode='passive_inventory',
        environment=dict(platform=platform.system(), python=platform.python_version(),
            pynvml_module_present=importlib.util.find_spec('pynvml') is not None,
            nvidia_ml_py_version=binding, nsys_path=shutil.which('nsys'),
            cuda_visible_devices=os.environ.get('CUDA_VISIBLE_DEVICES')),
        telemetry=dict(status='not_checked', device_uuid=None),
        configuration=dict(status='not_supplied'),
        worker_device_mapping='unverified',
        real_profiler_backend='not_implemented', capture_coverage='unverified',
        live_experiment_ready=False,
        blockers=['Actual NVML read has not been verified on the target GPU',
                  'Serving worker/device mapping and healthy calibration require verification',
                  'Real profiler attachment, capture acknowledgement, readiness and coverage are unvalidated'],
        note='Package/binary discovery does not establish GPU or capture readiness. No serving endpoint is contacted.')


async def probe(config, *, sampler_factory=NvmlSampler):
    clock = MonotonicClock()
    sampler = sampler_factory(config, clock)
    try:
        async with sampler:
            value = await sampler()
        return dict(status='sample_received', gpu_util=value, metadata=sampler.metadata,
                    sampling_interval='unknown', timestamp_semantics='parent_receipt',
                    clock_domain=clock.domain, events=sampler.events,
                    cleanup=sampler.events[-1] if sampler.events else None)
    except Exception as exc:
        return dict(status='failed', error_type=type(exc).__name__, detail=str(exc))


async def preflight(*, device_uuid=None, probe_nvml=False, endpoint=None,
                    healthy_p95_ms=None, calibration_source=None):
    report = inventory()
    if device_uuid is not None:
        report['telemetry']['device_uuid'] = NvmlConfig(device_uuid).device_uuid
    supplied = (endpoint, healthy_p95_ms, calibration_source)
    if any(value is not None for value in supplied):
        if any(value is None for value in supplied):
            raise ValueError('Supply endpoint, healthy p95 and calibration source together')
        report['configuration'] = dict(status='syntax_valid_only',
            producer=asdict(ProducerConfig(endpoint)),
            baseline=asdict(HealthyBaseline(healthy_p95_ms, calibration_source)),
            calibration_validity='not_verified', endpoint_contacted=False)
    if probe_nvml:
        if device_uuid is None:
            raise ValueError('An NVML probe requires --device-uuid GPU-...')
        report['mode'] = 'active_nvml_probe'
        report['telemetry'] = dict(await probe(NvmlConfig(device_uuid)), device_uuid=device_uuid)
        if report['telemetry']['status'] == 'sample_received':
            report['blockers'][0] = 'NVML receipt succeeded; GPU/serving process attribution remains unverified'
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device-uuid')
    parser.add_argument('--probe-nvml', action='store_true')
    parser.add_argument('--endpoint')
    parser.add_argument('--healthy-p95-ms', type=float)
    parser.add_argument('--calibration-source')
    parser.add_argument('--output', type=Path, default=ROOT / 'experiments/examples/preflight/environment.json')
    args = parser.parse_args()
    output = args.output.resolve()
    output.relative_to((ROOT / 'experiments').resolve())
    try:
        report = asyncio.run(preflight(device_uuid=args.device_uuid, probe_nvml=args.probe_nvml,
            endpoint=args.endpoint, healthy_p95_ms=args.healthy_p95_ms, calibration_source=args.calibration_source))
    except ValueError as exc:
        parser.error(str(exc))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(f'{report["mode"]}: NVML {report["telemetry"]["status"]}; live experiment ready: false; {output}')
    return 2 if report['telemetry']['status'] == 'failed' else 0


if __name__ == '__main__':
    raise SystemExit(main())
