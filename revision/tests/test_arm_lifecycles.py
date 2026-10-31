"""Real owned CPU targets; independently verify server reset/quiet/cleanup."""
import asyncio
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from revision.tracing.arm_session import CpuTargetSession, SessionConfig
from revision.tracing.experiment_arms import ArmPlan, CpuArmRunner, CpuSamplerSession, require_comparable
from revision.tracing.target_capture import CpuTargetCaptureBackend
from revision.tracing.feature_collection import collect_completion
from revision.tracing.timing import MonotonicClock, TimingRecorder
from revision.tracing.schedule_playback import PlaybackConfig
from revision.tracing.arrival_schedule import ArrivalSchedule


def schedule(duration=.3):
    return ArrivalSchedule.from_bytes(json.dumps(dict(version='offered_arrivals_v1',duration_ns=round(duration*1e9),requests=[
        dict(request_id=f'opaque-{i}',offset_ns=i*20000000,payload=dict(model='fixture',prompt='Actual fixture',max_tokens=32,stream=False))
        for i in range(max(1,int(duration/.02)-2))])).encode())


def playback(**changes):
    return PlaybackConfig(**(dict(window_s=.05,grace_s=.005,min_latency_samples=1,request_timeout_s=1,drain_s=.03,
        max_admission_lateness_s=.1,sample_interval_s=.01)|changes))


class ArmPlanTests(unittest.TestCase):
    def test_arm_modes_are_distinct_and_cannot_mislabel_capture_disabled_controls(self):
        self.assertEqual(ArmPlan.for_name('no_profiler').capture_mode,'disabled')
        self.assertFalse(ArmPlan.for_name('no_profiler').cheap_sampling)
        self.assertTrue(ArmPlan.for_name('cheap_only').cheap_sampling)
        self.assertEqual(ArmPlan.for_name('fixed_burst').capture_mode,'bounded')
        self.assertEqual(ArmPlan.for_name('full_horizon_reference').capture_mode,'continuous')
        with self.assertRaises(ValueError):ArmPlan('no_profiler','bounded',False,'none')
        with self.assertRaises(ValueError):ArmPlan.for_name('marginal_utility_stop')

    def test_quiescence_requires_repeated_valid_samples_and_bounded_cleanup(self):
        for changes in ({'quiet_observations':1},{'quiet_observations':True},{'quiet_hold_s':0},
                        {'quiescence_s':float('nan')},{'cleanup_timeout_s':.01,'cleanup_grace_s':.02}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):SessionConfig(**changes)


class SessionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.root=Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)

    def session(self,mode='disabled',fault='normal',**config):
        return CpuTargetSession(self.root/'target',MonotonicClock(),mode,config=SessionConfig(**config),fault=fault)

    async def test_reset_changes_generation_and_rejects_stale_or_missing_status(self):
        session=self.session()
        try:
            await session.start();old=await session.status();await session.reset()
            self.assertEqual(session.generation,1)
            with self.assertRaises(ValueError):session.validate(old)
            current=await session.status()
            for mutation in ({'nonce':'foreign'},{'running':True},{'inflight':10},{'generation':True}):
                with self.subTest(mutation=mutation),self.assertRaises(ValueError):session.validate(current|mutation)
            missing=dict(current);missing.pop('report_pending')
            with self.assertRaises(ValueError):session.validate(missing)
        finally:await session.aclose()
        self.assertFalse(session.group_alive())

    async def test_client_timeout_does_not_imply_server_quiescence(self):
        # Keep actual server work alive across slow host scheduling/status RPCs;
        # this fixture tests independent server completion, not a 150 ms race.
        session=self.session(work_s=1,quiescence_s=3)
        try:
            await session.start()
            result=await collect_completion(session.clock,'timed-out',session.endpoint+'/v1/completions',
                {'model':'fixture','prompt':'work','max_tokens':32},timeout_s=.01)
            self.assertFalse(result.completion.success)
            self.assertGreater((await session.status())['inflight'],0)
            await session.wait_quiet('after_client_timeout')
            checks=session.quiet_checks[-1]['checks']
            self.assertTrue(any(not c['quiet'] for c in checks))
            self.assertTrue(checks[-1]['quiet'])
            self.assertGreaterEqual(len(checks),2)
        finally:await session.aclose()

    async def test_reset_cannot_clear_busy_work_as_if_it_were_quiet(self):
        # Keep real work alive through status/RPC scheduling on a busy host;
        # retain the short quiet deadline and rejection/generation assertions.
        session=self.session(work_s=1,quiescence_s=.03)
        try:
            await session.start()
            await collect_completion(session.clock,'r',session.endpoint+'/v1/completions',{'max_tokens':32},timeout_s=.01)
            self.assertGreater((await session.status())['inflight'],0)
            with self.assertRaises(TimeoutError):await session.reset()
            self.assertEqual(session.generation,0)
            self.assertGreater((await session.status())['inflight'],0)
        finally:await session.aclose()

    async def test_capture_stop_does_not_stop_target_and_report_pending_is_not_quiet(self):
        session=self.session('bounded',report_s=.1)
        backend=None
        try:
            await session.start();recorder=TimingRecorder(session.clock,provenance='synthetic_simulation')
            backend=CpuTargetCaptureBackend(session,recorder);backend.start('capture-1')
            await backend.wait_for('capture-1','capturing')
            backend.stop('capture-1');await session.wait_quiet('after_capture_stop')
            self.assertTrue(any(c['status']['report_pending']>0 for c in session.quiet_checks[-1]['checks']))
            await backend.wait_for('capture-1','ready')
            result=await collect_completion(session.clock,'still-serving',session.endpoint+'/v1/completions',{'max_tokens':1})
            self.assertTrue(result.completion.success)
            self.assertIsNone(session.process.poll())
            self.assertIsNone(recorder.metrics('capture-1')['capture_active_s'])
        finally:
            if backend is not None:await backend.aclose()
            await session.aclose()

    async def test_disabled_target_rejects_capture_control(self):
        session=self.session()
        try:
            await session.start()
            with self.assertRaises(ValueError):CpuTargetCaptureBackend(session,TimingRecorder(session.clock,provenance='synthetic_simulation'))
            with self.assertRaises(RuntimeError):await session.command('/capture/start',{'capture_id':'forbidden'})
            self.assertEqual((await session.status())['capture_starts'],0)
        finally:await session.aclose()

    async def test_ignore_term_escalates_only_owned_group_and_reaps_it(self):
        session=self.session(fault='ignore_term',cleanup_grace_s=.03)
        await session.start();await session.aclose()
        self.assertTrue(session.cleanup['escalated'])
        self.assertFalse(session.group_alive())

    async def test_cancelling_cleanup_waiter_still_completes_cleanup(self):
        session=self.session(fault='ignore_term',cleanup_grace_s=.05)
        await session.start();task=asyncio.create_task(session.aclose())
        await asyncio.sleep(.005);task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertFalse(session.group_alive())
        self.assertIsNotNone(session.cleanup)

    async def test_transient_visibility_denial_is_unknown_until_absence_is_verified(self):
        session=self.session();await session.start();original=os.killpg;denied=False
        def once(pid,sig):
            nonlocal denied
            if pid==session.process.pid and sig==0 and not denied:
                denied=True;raise PermissionError('fixture transient visibility')
            return original(pid,sig)
        with patch('revision.tracing.arm_session.os.killpg',side_effect=once):await session.aclose()
        self.assertTrue(denied)
        self.assertFalse(session.cleanup['group_alive'])
        self.assertTrue(any(e['event']=='group_visibility_unknown' for e in session.events))


class ArmRunnerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.root=Path(self.temporary.name);self.addCleanup(self.temporary.cleanup)

    def runner(self,name,**changes):
        return CpuArmRunner(self.root/name,name,schedule(),playback_config=playback(),session_config=SessionConfig(work_s=.05),**changes)

    async def test_no_profiler_never_opens_sampler_or_capture_backend(self):
        def forbidden():raise AssertionError('No-profiler opened cheap sampler')
        runner=self.runner('no_profiler',sampler_factory=forbidden);result=await runner.run()
        self.assertIsNone(result['sampler']);self.assertIsNone(result['capture_backend'])
        self.assertEqual(result['post_playback_status']['status']['capture_starts'],0)
        self.assertEqual(result['session']['capture_mode'],'disabled')
        self.assertEqual(result['session']['generation'],3)
        self.assertFalse(result['session']['cleanup']['group_alive'])
        with self.assertRaises(RuntimeError):await runner.run()

    async def test_cheap_only_samples_but_cannot_capture_and_closes_sampler(self):
        result=await self.runner('cheap_only').run()
        self.assertGreater(result['sampler']['reads'],0);self.assertTrue(result['sampler']['closed'])
        self.assertIsNone(result['capture_backend']);self.assertIsNone(result['controller'])
        self.assertGreater(result['monitor_windows'],0)
        self.assertEqual(result['post_playback_status']['status']['capture_starts'],0)

    async def test_fixed_burst_stops_capture_and_workload_continues(self):
        # Leave enough real workload after capture readiness on a busy CPU host.
        runner=CpuArmRunner(self.root/'fixed_burst','fixed_burst',schedule(1),
            playback_config=playback(),session_config=SessionConfig(work_s=.05))
        result=await runner.run()
        attempts=result['capture_backend']['attempts'];self.assertEqual(len(attempts),1)
        self.assertEqual(next(iter(attempts.values()))['state'],'ready')
        decisions=[d for e in result['controller']['episodes'] for d in e['decisions']]
        self.assertEqual(decisions[0]['decision']['reason'],'fixed_burst_complete')
        self.assertTrue(any(r['terminal'] is not None and r['terminal']['completion']['end_ns']>decisions[0]['decision_ready_at_ns'] for r in result['playback']['ledger']))
        self.assertIsNone(decisions[0]['decision']['diagnosis_label'])

    async def test_all_other_policies_share_hard_budget_and_abstention(self):
        for name in ('repeated_fixed_burst','stability_stop','counter_recovery_stop','hybrid_stop'):
            with self.subTest(policy=name):
                result=await self.runner(name).run()
                attempts=result['capture_backend']['attempts']
                self.assertGreater(len(attempts),0);self.assertLessEqual(len(attempts),3)
                self.assertTrue(all(a['state'] in ('ready','failed') for a in attempts.values()))
                decisions=[d for e in result['controller']['episodes'] for d in e['decisions']]
                self.assertTrue(all(d['decision']['diagnosis_label'] is None for d in decisions))
                self.assertTrue(result['sampler']['closed']);self.assertFalse(result['session']['cleanup']['group_alive'])

    async def test_reference_capture_encloses_fixed_observation_and_finalizes_offline(self):
        runner=self.runner('full_horizon_reference');result=await runner.run()
        self.assertIsNone(result['controller'])
        events=runner.recorder.events
        started=next(e.timestamp_ns for e in events if e.name=='capture_control_window_started')
        stopped=next(e.timestamp_ns for e in events if e.name=='capture_stop_rpc_started')
        self.assertLessEqual(started,result['playback']['start_ns'])
        self.assertGreaterEqual(stopped,result['playback']['horizon_ns'])
        self.assertEqual(result['capture_backend']['attempts']['full-reference']['state'],'ready')

    async def test_post_drain_server_activity_requires_independent_wait_before_reset(self):
        arrivals=ArrivalSchedule.from_bytes(json.dumps(dict(version='offered_arrivals_v1',duration_ns=30000000,requests=[
            dict(request_id='r',offset_ns=0,payload=dict(model='fixture',prompt='work',max_tokens=32,stream=False))])).encode())
        runner=CpuArmRunner(self.root/'busy','no_profiler',arrivals,playback_config=playback(drain_s=.005),session_config=SessionConfig(work_s=.15))
        result=await runner.run()
        self.assertEqual(result['playback']['live_request_tasks'],0)
        self.assertGreater(result['post_playback_status']['status']['inflight'],0)
        checks=next(c['checks'] for c in result['session']['quiescence_checks'] if c['phase']=='post_workload')
        self.assertTrue(any(not c['quiet'] for c in checks));self.assertTrue(checks[-1]['quiet'])
        self.assertEqual(result['session']['generation'],3)

    async def test_comparability_checks_hash_fresh_target_and_sampler_ownership(self):
        first=await self.runner('no_profiler').run();second=await self.runner('cheap_only').run()
        require_comparable([first,second])
        for mode in ('hash','instance','sampler'):
            other=copy.deepcopy(second)
            if mode=='hash':other['comparison_contract_sha256']='different'
            elif mode=='instance':other['session']['instance']=first['session']['instance']
            else:other['sampler']['closed']=False
            with self.subTest(mode=mode),self.assertRaises(ValueError):require_comparable([first,other])

    async def test_closed_sampler_cannot_be_reused_by_next_arm(self):
        shared=CpuSamplerSession();first=self.runner('cheap_only',sampler_factory=lambda:shared);await first.run()
        second=CpuArmRunner(self.root/'second','cheap_only',schedule(),playback_config=playback(),
            session_config=SessionConfig(work_s=.05),sampler_factory=lambda:shared)
        with self.assertRaisesRegex(RuntimeError,'reuse'):await second.run()
        self.assertFalse(second.session.cleanup['group_alive'])

    async def test_bad_identity_metrics_reset_and_startup_failures_are_retained(self):
        for fault in ('wrong_identity','missing_metric','stale_reset','stuck_busy','startup_fail'):
            runner=CpuArmRunner(self.root/fault,'cheap_only',schedule(),playback_config=playback(),
                session_config=SessionConfig(work_s=.05,quiescence_s=.05),target_fault=fault)
            with self.subTest(fault=fault),self.assertRaises(Exception):await runner.run()
            saved=json.loads((runner.output/'results.json').read_text())
            self.assertEqual(saved['status'],'failed')
            self.assertFalse(saved['session']['cleanup']['group_alive'])
            self.assertIsNone(saved['playback'])

    async def test_external_cancellation_keeps_target_and_sampler_cleanup(self):
        runner=self.runner('cheap_only');task=asyncio.create_task(runner.run())
        while runner.driver is None:await asyncio.sleep(.005)
        await asyncio.sleep(.01);task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        result=runner.snapshot();self.assertEqual(result['status'],'aborted')
        self.assertTrue(result['sampler']['closed']);self.assertFalse(result['session']['cleanup']['group_alive'])


if __name__=='__main__':unittest.main()
