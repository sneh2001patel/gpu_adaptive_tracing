"""Join closed acquisition windows to newly available parsed evidence.

This measured-input bridge is CPU validated separately from the legacy live
kernel-only callback. Capture intervals supplied here are host acquisition
intervals, not certified GPU capture-active boundaries.
"""
from revision.tracing.diagnosis import UncalibratedClassifier
from revision.tracing.feature_collection import FeatureWindow
from revision.tracing.measured_evidence import Acquisition, KernelObservation, MeasuredObservation, PROVENANCES, identity, integer
from revision.tracing.profiler import ReadyEvidence, EvidenceNotReady


def kernel_from_ready(ready, acquisition, *, provenance, expected_device_uuid, expected_worker_pid):
    if type(ready) is not ReadyEvidence or type(acquisition) is not Acquisition:
        raise ValueError('Typed parsed evidence/acquisition required')
    if ready.provenance != provenance or provenance not in PROVENANCES:
        raise ValueError('Cross-provenance kernel evidence')
    if ready.clock_domain != acquisition.clock_domain or ready.ready_at_ns != acquisition.available_at_ns:
        raise ValueError('Kernel availability/domain differs from parsed evidence')
    payload=ready.payload
    source='synthetic_fixture' if provenance=='synthetic_simulation' else 'nsys_sqlite'
    if type(payload) is not dict or payload.get('source') != source:
        raise ValueError('Unexpected kernel source')
    if payload.get('device_uuid') != expected_device_uuid or payload.get('captured_worker_pids') != [expected_worker_pid]:
        raise ValueError('Captured worker/device identity differs from configured target')
    # Explicit extraction: no raw names, note strings, scenario or reference data.
    return KernelObservation(ready.capture_id,ready.evidence_id,payload['device_uuid'],
        tuple(payload['captured_worker_pids']),payload['kernel_count'],payload['kernel_time_sum_s'],
        payload['coverage'],acquisition)


class FeatureClassifierBridge:
    def __init__(self,clock,*,provenance,device_uuid,worker_pid):
        if provenance not in PROVENANCES:raise ValueError('Explicit provenance required')
        identity(device_uuid,'device_uuid');integer(worker_pid,'worker_pid',1)
        if not device_uuid.startswith('GPU-'):raise ValueError('Explicit physical GPU UUID required')
        self.clock,self.provenance=clock,provenance
        self.device_uuid,self.worker_pid=device_uuid,worker_pid
        self.windows={};self.consumed=set();self.observations=[];self.predictions=[]
        self.classifier=UncalibratedClassifier()

    def register(self,window_id,window):
        identity(window_id,'window_id')
        if not isinstance(window, FeatureWindow) or window.clock is not self.clock:
            raise ValueError('Feature window must share the bridge clock object')
        binding=getattr(window,'binding',None)
        if binding is not None and (window.provenance!=self.provenance or
                binding.device_uuid!=self.device_uuid or binding.worker_pid!=self.worker_pid):
            raise ValueError('Feature window provenance/worker/device differs from bridge')
        if window_id in self.windows:raise ValueError('Duplicate window identity')
        # Registration is allowed only after closure, preserving its availability.
        if window.metrics is None:raise EvidenceNotReady('Feature window has not closed')
        self.windows[window_id]=window

    def classify(self,window_id,*,ready=None,capture_acquisition=None):
        window=self.windows[window_id];now=self.clock.now_ns();kernel=None
        if ready is not None:
            kernel=kernel_from_ready(ready,capture_acquisition,provenance=self.provenance,
                expected_device_uuid=self.device_uuid,expected_worker_pid=self.worker_pid)
            key=('kernel',kernel.evidence_id)
            available=max(window.closed_at_ns,kernel.acquisition.available_at_ns)
        else:
            if capture_acquisition is not None:raise ValueError('Acquisition without parsed evidence')
            key=('cheap',window_id);available=window.closed_at_ns
        if key in self.consumed:raise ValueError('Evidence already classified')
        if available>now:raise EvidenceNotReady('Parsed evidence is not available yet')
        observation=MeasuredObservation(window_id+':'+str(key[1]),self.provenance,
            Acquisition(window.start_ns,window.end_ns,available,self.clock.domain),window.metrics,kernel)
        # Constructor rejects a different/adjacent acquisition interval. Never use
        # latest-window fallback, waiting time backdating, or future evidence.
        prediction=self.classifier.classify(observation,now_ns=now,clock_domain=self.clock.domain)
        self.consumed.add(key);self.observations.append(observation);self.predictions.append(prediction)
        return prediction
