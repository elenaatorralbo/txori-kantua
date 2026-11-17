import numpy as np
import pytest
from datetime import date
from txori_kantua.audio.birdnet import Candidate, WINDOW_SAMPLES
from txori_kantua.audio.filtering import DetectionFilter
from txori_kantua.audio.pipeline import Inference, Window, WindowQueue
from txori_kantua.messaging.contracts import validate

NAME='Turdus merula'
def filt(**kw):
    params=dict(threshold=.5,region='test-region',revision='synthetic',
                seasons={'test-region':{'11':[NAME],'12':[]},'other':{'11':[]}})
    params.update(kw)
    return DetectionFilter(**params)

def window(): return Window(bytearray(b'\x01\x00'*WINDOW_SAMPLES),'2026-11-17T10:00:00Z')


def test_boundaries_season_and_region():
    f=filt()
    for score,expected in [(.4999,False),(.5,True),(.5001,True),(float('nan'),False)]:
        assert f.accepts(Candidate(0,NAME,'Blackbird',score),date(2026,11,17)) is expected
    assert not f.accepts(Candidate(0,NAME,'Blackbird',.9),date(2026,12,17))
    assert not filt(region='other').accepts(Candidate(0,NAME,'Blackbird',.9),date(2026,11,17))


def test_overload_wipes_old_window_and_bounds_queue():
    q=WindowQueue(2); first=window(); q.put(first)
    for _ in range(20): q.put(window())
    assert not any(first.pcm)
    assert q.stats['dropped']==19
    a,b=q.pop(),q.pop(); assert q.pop() is None
    a.clear(); b.clear(); q.close()

class Model:
    def version(self): return 'synthetic-test'
    def predict(self,samples): return np.array([.8])
    def top(self,scores,**kw): return [Candidate(0,NAME,'Blackbird',float(scores[0]))]


def test_normalized_repeatable_metadata_and_failure_cleanup():
    engine=Inference(Model(),filt(),'station-01')
    w=window(); a=engine.process(w)
    assert not any(w.pcm)
    validate('detection',a[0]); assert engine.process(window())==a
    class Broken(Model):
        def predict(self,samples): raise RuntimeError('model failed')
    w=window(); engine=Inference(Broken(),filt(),'station-01')
    with pytest.raises(RuntimeError): engine.process(w)
    assert not any(w.pcm) and engine.stats['errors']==1 and engine.stats['empty']==0


def test_missing_season_context_is_an_explicit_rejection():
    f=filt()
    assert not f.accepts(Candidate(0,NAME,'Blackbird',.9),date(2026,1,1))
    assert f.stats['missing_context']==1
