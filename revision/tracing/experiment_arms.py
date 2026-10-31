"""CPU-fixture arm/session lifecycle runner. No GPU launch or validation.

All arms use the exact same offered file/configuration and fresh owned process.
Capture-disabled controls genuinely lack capture capabilities at the target.
"""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import uuid

from revision.tracing.arm_session import CpuTargetSession, SessionConfig
from revision.tracing.target_capture import CpuTargetCaptureBackend
from revision.tracing.cpu_interval_collection import CpuIntervalCollector
from revision.tracing.measured_evidence import Acquisition,KernelObservation,MeasuredObservation
from revision.tracing.diagnosis import UncalibratedClassifier,VERSION as CLASSIFIER_VERSION
from revision.tracing.arrival_schedule import canonical
from revision.tracing.aggregation import p95
from revision.tracing.controller import StreamingController, ControllerConfig
from revision.tracing.policies import POLICIES, PolicyConfig
from revision.tracing.feature_collection import QueueGaugeCollector, collect_completion
from revision.tracing.schedule_playback import SchedulePlayback, PlaybackConfig
from revision.tracing.timing import MonotonicClock, TimingRecorder, seconds_to_ns
from revision.tracing.windows import CheapWindow, HealthyBaseline

ARMS=('no_profiler','cheap_only')+POLICIES+('full_horizon_reference',)


@dataclass(frozen=True)
class ArmPlan:
    name: str
    capture_mode: str
    cheap_sampling: bool
    controller_mode: str

    def __post_init__(self):
        if self.name not in ARMS:raise ValueError('Unknown arm; MU is not a separate policy')
        if type(self.cheap_sampling) is not bool:raise ValueError('Sampling mode must be boolean')
        expected=('disabled',False,'none') if self.name=='no_profiler' else (
            ('disabled',True,'monitor_only') if self.name=='cheap_only' else (
                ('continuous',True,'reference_only') if self.name=='full_horizon_reference' else ('bounded',True,'policy')))
        if (self.capture_mode,self.cheap_sampling,self.controller_mode)!=expected:
            raise ValueError('Arm instrumentation contradicts its name')

    @classmethod
    def for_name(cls,name):
        if name=='no_profiler':return cls(name,'disabled',False,'none')
        if name=='cheap_only':return cls(name,'disabled',True,'monitor_only')
        if name=='full_horizon_reference':return cls(name,'continuous',True,'reference_only')
        return cls(name,'bounded',True,'policy')


class CpuSamplerSession:
    """Fresh cheap-sampler ownership fixture; deliberately no NVML import."""
    def __init__(self):
        self.instance=uuid.uuid4().hex;self.closed=False;self.used=False;self.reads=0
    async def __aenter__(self):
        if self.used or self.closed:raise RuntimeError('Cannot reuse a sampler session')
        self.used=True;return self
    async def sample(self):
        if self.closed:raise RuntimeError('Sampler is closed')
        self.reads+=1;return 90
    async def aclose(self):self.closed=True
    def snapshot(self):return dict(source='cpu_fixture',instance=self.instance,closed=self.closed,reads=self.reads)


class CpuArmRunner:
    def __init__(self,output,arm,schedule,*,playback_config=None,session_config=None,sampler_factory=CpuSamplerSession,
                 target_fault='normal',policy_config=None):
        self.output=Path(output).resolve();self.output.mkdir(parents=True,exist_ok=False)
        self.plan=ArmPlan.for_name(arm);self.schedule=schedule
        self.playback_config=playback_config or PlaybackConfig()
        self.session_config=session_config or SessionConfig()
        self.policy_config=policy_config or PolicyConfig(max_bursts=3)
        self.clock=MonotonicClock();self.recorder=TimingRecorder(self.clock,provenance='synthetic_simulation')
        self.session=CpuTargetSession(self.output/'target',self.clock,self.plan.capture_mode,config=self.session_config,fault=target_fault,interval_recording=self.plan.cheap_sampling)
        self.sampler_factory=sampler_factory;self.sampler=None;self.backend=None;self.controller=None;self.driver=None
        self.warmup=[];self.quiet_after_workload=None;self.playback_end_status=None;self.status='not_started';self.errors=[]
        self.used=False;self.cleanup_task=None;self.monitor_windows=0;self.phase_names=[]
        self.interval_collector=None;self.measured_observations={};self.cheap_observations=[];self.measured_predictions=[]
        self.classifier=UncalibratedClassifier();self.evaluation_export=None
        from revision.scripts.play_arrivals import write_sources
        write_sources(self.output)
        self.contract=dict(schedule_file_sha256=schedule.file_sha256,schedule_content_sha256=schedule.content_sha256,
            duration_ns=schedule.duration_ns,playback_config=asdict(self.playback_config),
            target_work_s=self.session_config.work_s,target_report_s=self.session_config.report_s,
            shared_policy_config=asdict(self.policy_config),requested_burst_s=.01,
            warmup_count=2,warmup_request=self.warmup_payload(),
            cheap_interval_source='cpu_admission_history_v1',phase_attribution='not_instrumented')
        self.contract_hash=hashlib.sha256(canonical(self.contract)).hexdigest()

    def warmup_payload(self):
        model=self.schedule.requests[0].payload['model'] if self.schedule.requests else 'fixture'
        return dict(model=model,prompt='Common warmup fixture',max_tokens=1,stream=False,temperature=0)

    @asynccontextmanager
    async def phase(self,name):
        self.phase_names.append(name);self.recorder.begin(name,'arm')
        try:yield
        except BaseException:
            self.recorder.end(name,'arm',status='failed');raise
        else:self.recorder.end(name,'arm')

    def on_window(self,identity,window):
        if self.plan.cheap_sampling:
            observation=MeasuredObservation(identity,'synthetic_simulation',
                Acquisition(window.start_ns,window.end_ns,window.closed_at_ns,self.clock.domain),window.metrics,None)
            self.cheap_observations.append(asdict(observation))
        if self.controller is None:
            if self.plan.cheap_sampling:self.monitor_windows+=1
            return
        if self.controller.finished:return
        if self.driver.horizon_ns is not None and self.clock.now_ns()>=self.driver.horizon_ns:
            self.controller.finish();return
        # Activation/recovery observes measured successful-completion latency;
        # error/unfinished counts remain explicit in the raw driver ledger.
        metrics={m.name:m for m in window.metrics};latency=metrics['request_p95_ms'];gpu=metrics['gpu_util_mean']
        self.controller.on_window(CheapWindow(identity,window.start_ns,window.end_ns,window.closed_at_ns,self.clock.domain,
            latency.value,gpu.value,latency.valid_samples,throughput_rps=metrics['completed_rps'].value,
            gpu_sample_count=sum(r.gpu_util is not None for r in window.gpu)))

    def observe_capture(self,identity):
        ready=self.backend.evidence(identity)
        if ready.evidence_id in self.measured_observations:return self.measured_observations[ready.evidence_id]
        payload=ready.payload;bounds=self.backend.attempts[identity]['acquisition']
        if payload.get('source')!='synthetic_fixture' or payload.get('device_uuid')!='GPU-cpu-fixture' or payload.get('captured_worker_pids')!=[self.session.process.pid]:
            raise ValueError('Unexpected measured fixture capture identity')
        acquisition=Acquisition(bounds['start_ns'],bounds['end_ns'],ready.ready_at_ns,self.clock.domain)
        kernel=KernelObservation(identity,ready.evidence_id,payload['device_uuid'],tuple(payload['captured_worker_pids']),
            payload['kernel_count'],payload['kernel_time_sum_s'],payload['coverage'],acquisition)
        # Triggering cheap windows precede this range. Retain them separately;
        # never relabel their statistics as measurements of a later capture.
        observation=MeasuredObservation(ready.evidence_id,'synthetic_simulation',acquisition,(),kernel)
        self.measured_observations[ready.evidence_id]=observation
        return observation

    def classify_capture(self,payload):
        observation=self.observe_capture(payload['capture_id'])
        result=self.classifier.classify(observation,now_ns=self.clock.now_ns(),clock_domain=self.clock.domain)
        self.measured_predictions.append(asdict(result));return result.policy_label

    def persist_evaluation(self):
        from revision.evaluation.controller_export import export_initial_stops
        folder=self.output/'evaluation';folder.mkdir(exist_ok=False)
        if self.interval_collector is not None:
            (self.output/'interval_source.json').write_text(json.dumps(self.interval_collector.snapshot(),indent=2)+'\n')
        (self.output/'cheap_observations.json').write_text(json.dumps(self.cheap_observations,indent=2)+'\n')
        (self.output/'measured_observations.json').write_text(json.dumps({k:asdict(v) for k,v in self.measured_observations.items()},indent=2)+'\n')
        (self.output/'measured_predictions.json').write_text(json.dumps(self.measured_predictions,indent=2)+'\n')
        if self.controller is None:
            self.evaluation_export=dict(applicable=False,reason='arm_has_no_policy_controller',initial_stops=None)
        else:
            result=export_initial_stops('cpu-'+self.session.instance+'-'+self.plan.name,
                self.controller.snapshot(),self.measured_observations,classifier_version=CLASSIFIER_VERSION)
            for filename,key in [('predictions.json','predictions'),('controller_snapshot.json','controller_snapshot'),('export_audit.json','export_audit')]:
                (folder/filename).write_text(json.dumps(result[key],indent=2,allow_nan=False)+'\n')
            self.evaluation_export=dict(applicable=True,initial_stops=len(result['predictions']),
                mapping='unmapped_no_cause_assertions_v1',run_id=result['controller_snapshot']['run_id'])
        (folder/'status.json').write_text(json.dumps(self.evaluation_export,indent=2)+'\n')

    def service(self):
        if self.controller is not None:
            # No post-horizon capture/diagnosis decisions during client drain.
            if self.driver.horizon_ns is not None and self.clock.now_ns()>=self.driver.horizon_ns:self.controller.finish()
            else:self.controller.tick()
        elif self.backend is not None and self.plan.capture_mode=='continuous':
            self.backend.poll('full-reference')
            if self.driver.horizon_ns is not None and self.clock.now_ns()>=self.driver.horizon_ns and self.backend.state('full-reference')=='capturing':
                self.backend.stop('full-reference')

    async def body(self):
        async with self.phase('target_startup'):await self.session.start()
        async with self.phase('initial_reset'):await self.session.reset()
        async with self.phase('warmup'):
            for i in range(2):
                record=await collect_completion(self.clock,f'warmup-{i}',self.session.endpoint+'/v1/completions',
                    self.warmup_payload(),timeout_s=self.session_config.command_timeout_s)
                if not record.completion.success:raise RuntimeError('Warmup request failed')
                self.warmup.append(asdict(record))
        async with self.phase('post_warmup_reset'):await self.session.reset()
        if self.plan.cheap_sampling:
            self.sampler=self.sampler_factory();await self.sampler.__aenter__()
            self.interval_collector=CpuIntervalCollector(self.session);await self.interval_collector.bind()
        if self.plan.capture_mode!='disabled':self.backend=CpuTargetCaptureBackend(self.session,self.recorder)
        if self.plan.controller_mode=='policy':
            baseline=HealthyBaseline(p95([(r['completion']['end_ns']-r['completion']['start_ns'])/1e6 for r in self.warmup]),
                str(self.output/'warmup_requests.json'))
            self.controller=StreamingController(self.backend,baseline,self.classify_capture,
                lambda identity,window:self.backend.start(identity,window),
                ControllerConfig(policy=self.plan.name,policy_config=self.policy_config,burst_s=.01,
                    startup_timeout_s=1,evidence_timeout_s=1,cooldown_s=.02,reactivation_enabled=False))
        if self.plan.capture_mode=='continuous':
            async with self.phase('reference_start'):
                self.backend.start('full-reference');await self.backend.wait_for('full-reference','capturing')
        self.driver=SchedulePlayback(self.schedule,self.clock,self.session.endpoint+'/v1/completions',provenance='synthetic_simulation',
            config=self.playback_config,server_collector=QueueGaugeCollector(self.session.endpoint+'/metrics','fixture_queue') if self.plan.cheap_sampling else None,
            gpu_sampler=None if self.sampler is None else self.sampler.sample,on_window=self.on_window,service_evidence=self.service,
            interval_collector=self.interval_collector)
        async with self.phase('workload_and_drain'):await self.driver.run()
        if self.controller is not None:self.controller.finish()
        if self.plan.capture_mode=='continuous':
            async with self.phase('reference_finalize'):
                if self.backend.state('full-reference')=='capturing':self.backend.stop('full-reference')
                await self.backend.wait_for('full-reference','ready')
                self.observe_capture('full-reference')
        reply=await self.session.status()
        self.playback_end_status=dict(received_at_ns=self.clock.now_ns(),status=reply)

    async def cleanup(self):
        async def attempt(name,callback):
            try:
                async with self.phase(name):await callback()
            except Exception as exc:self.errors.append(dict(phase=name,error=type(exc).__name__,detail=str(exc)))
        if self.controller is not None:
            try:self.controller.finish()
            except Exception as exc:self.errors.append(dict(phase='controller_finish',error=type(exc).__name__))
        if self.backend is not None:await attempt('capture_cleanup',self.backend.aclose)
        if self.sampler is not None:await attempt('sampler_cleanup',self.sampler.aclose)
        if self.session.endpoint is not None and self.session.process.poll() is None:
            async def barrier():self.quiet_after_workload=await self.session.wait_quiet('post_workload')
            await attempt('post_workload_quiescence',barrier)
            if self.quiet_after_workload is not None:await attempt('final_reset',self.session.reset)
        await attempt('owned_target_cleanup',self.session.aclose)

    async def run(self):
        if self.used:raise RuntimeError('Arm runner is single-use')
        self.used=True;self.status='running';primary=None
        self.recorder.begin('arm_execution_wall','arm')
        try:await self.body()
        except BaseException as exc:
            primary=exc;self.errors.append(dict(phase='arm_body',error=type(exc).__name__,detail=str(exc)))
        finally:
            self.cleanup_task=asyncio.create_task(self.cleanup())
            while not self.cleanup_task.done():
                try:await asyncio.shield(self.cleanup_task)
                except asyncio.CancelledError as exc:
                    if primary is None:primary=exc
            try:self.cleanup_task.result()
            except BaseException as exc:
                self.errors.append(dict(phase='cleanup_task',error=type(exc).__name__,detail=str(exc)))
                if primary is None:primary=exc
            try:self.persist_evaluation()
            except Exception as exc:
                self.errors.append(dict(phase='evaluation_persistence',error=type(exc).__name__,detail=str(exc)))
                if primary is None:primary=exc
            self.status='aborted' if isinstance(primary,asyncio.CancelledError) else ('failed' if primary is not None or self.errors else 'completed')
            self.recorder.end('arm_execution_wall','arm',status='ok' if self.status=='completed' else 'failed')
            (self.output/'warmup_requests.json').write_text(json.dumps(self.warmup,indent=2)+'\n')
            (self.output/'results.json').write_text(json.dumps(self.snapshot(),indent=2,allow_nan=False)+'\n')
            (self.output/'timing_events.jsonl').write_text(self.recorder.jsonl())
            hashes={str(p.relative_to(self.output)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(self.output.rglob('*')) if p.is_file() and p.name!='artifact_manifest.json'}
            (self.output/'artifact_manifest.json').write_text(json.dumps(dict(version='cpu_arm_artifacts_v1',files=hashes),indent=2)+'\n')
        if primary is not None:raise primary
        if self.errors:raise RuntimeError('Arm lifecycle failed; inspect saved results')
        return self.snapshot()

    def snapshot(self):
        return dict(version='cpu_arm_lifecycle_v2',validation='cpu_fixture_only',gpu_used=False,valid_for_paper=False,
            status=self.status,arm=asdict(self.plan),comparison_contract=self.contract,comparison_contract_sha256=self.contract_hash,
            policy_config=asdict(self.policy_config),session_config=asdict(self.session_config),errors=list(self.errors),
            session=self.session.snapshot(),sampler=None if self.sampler is None else self.sampler.snapshot(),
            controller=None if self.controller is None else self.controller.snapshot(),
            capture_backend=None if self.backend is None else self.backend.snapshot(),monitor_windows=self.monitor_windows,
            post_playback_status=self.playback_end_status,post_workload_quiescent=self.quiet_after_workload,
            playback=None if self.driver is None else self.driver.snapshot(),
            phase_seconds={p:self.recorder.duration(p,'arm') for p in self.phase_names},
            capture_active_s=None,persisted_lifecycle_total_s=None,evaluation_export=self.evaluation_export,
            interval_source=None if self.interval_collector is None else self.interval_collector.snapshot(),
            measured_observation_count=len(self.measured_observations),cheap_observation_count=len(self.cheap_observations),
            note='Fresh CPU target per arm; repeated server-side quiet observations/reset acknowledgements are separate from client cleanup. Kernel report payloads are synthetic. Measured classifier abstains; cheap and capture observations retain separate intervals. Actual GPU metrics, phase attribution and calibrated T2 diagnosis are not integrated.')


def require_comparable(results):
    if not results:raise ValueError('No arm results')
    if any(hashlib.sha256(canonical(r['comparison_contract'])).hexdigest()!=r['comparison_contract_sha256'] for r in results):
        raise ValueError('Comparison contract fingerprint mismatch')
    if len({r['comparison_contract_sha256'] for r in results})!=1:raise ValueError('Offered schedule/horizon/playback/warmup differs across arms')
    if len({r['session']['instance'] for r in results})!=len(results):raise ValueError('Arm target instance reused')
    samplers=[r['sampler'] for r in results if r['sampler'] is not None]
    if any(not s['closed'] for s in samplers) or len({s['instance'] for s in samplers})!=len(samplers):
        raise ValueError('Sampler reused or not closed')
    if any(r['status']!='completed' or r['session']['cleanup'] is None or r['session']['cleanup']['group_alive'] for r in results):
        raise ValueError('Incomplete/failed arm lifecycle cannot pass comparability checks')
