"""No GPU: reproduce cancellation-closes-sampler across successive pilot arms."""
import tempfile
from pathlib import Path
import unittest

from experiments.scripts.run_l4_pilot import with_fresh_sampler
from experiments.tracing.timing import MonotonicClock


class PilotOwnershipTests(unittest.IsolatedAsyncioTestCase):
    async def test_closed_sampler_is_never_reused_across_episode_boundaries(self):
        created=[]
        class ClosingSampler:
            def __init__(self,*args):
                self.closed=False;self.metadata={'source':'fake'};self.events=[]
                created.append(self)
            async def __aenter__(self):
                if self.closed:raise RuntimeError('Cannot reuse closed sampler')
                return self
            async def __aexit__(self,*args):self.closed=True
        async def end_of_episode(sampler):
            self.assertFalse(sampler.closed)
            # Models the native callback closing after cancellation at horizon.
            sampler.closed=True
            return 'completed'
        with tempfile.TemporaryDirectory() as temporary:
            for index in range(2):
                result=await with_fresh_sampler(MonotonicClock(),'GPU-test',Path(temporary)/str(index),
                    end_of_episode,sampler_factory=ClosingSampler)
                self.assertEqual(result,'completed')
                self.assertTrue((Path(temporary)/str(index)/'sampler.json').exists())
        self.assertEqual(len(created),2)
        self.assertIsNot(created[0],created[1])
        self.assertTrue(all(s.closed for s in created))


if __name__=='__main__':unittest.main()
