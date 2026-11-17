from txori_kantua.display import DisplayController
from txori_kantua.messaging.events import new_detection
from txori_kantua.messaging.timestamps import to_epoch_ms

STAMP=to_epoch_ms('2026-11-17T10:00:00Z')
def event(**extra):
    args=dict(station_id='station-01',scientific_name='Turdus merula',confidence=.9,
        observed_at='2026-11-17T10:00:00Z',window_end='2026-11-17T10:00:03Z',
        model_name='BirdNET',model_version='synthetic')
    args.update(extra)
    return new_detection(**args)

def tick(d,ms,pir=False,touch=False,utc=STAMP):
    return d.tick(pir=pir,touch=touch,monotonic_ms=ms,utc_ms=utc)


def test_presence_timeout_and_held_input_do_not_extend_forever():
    d=DisplayController(warmup_ms=0)
    assert tick(d,0,True).backlight
    assert tick(d,19999,True).backlight
    assert not tick(d,20000,True).backlight
    tick(d,21000,False)
    assert tick(d,22000,True).backlight


def test_recent_stale_disconnected_and_duplicate():
    d=DisplayController(warmup_ms=0); d.connected=True
    e=event(); assert d.receive(e); assert not d.receive(e)
    assert 'Turdus' in ''.join(tick(d,0,True).rows)
    assert 'Sin datos' in ''.join(tick(d,1,utc=STAMP+300001).rows)
    d.connected=False
    assert 'conexion' in ''.join(tick(d,2).rows)
    old=event(observed_at='2026-11-16T10:00:00Z',window_end='2026-11-16T10:00:03Z')
    assert not d.receive(old)


def test_touch_debounce_languages_and_long_names():
    d=DisplayController(warmup_ms=0,catalogue={'Turdus merula':{'es':'Mirlo común','eu':'Zozoa','en':'Common blackbird'}})
    d.connected=True; d.receive(event())
    tick(d,0); tick(d,60)
    tick(d,70,touch=True); f=tick(d,130,touch=True)
    assert f.language=='eu' and f.backlight
    assert tick(d,500,touch=True).language=='eu'
    tick(d,600); tick(d,660); tick(d,700,touch=True)
    assert tick(d,760,touch=True).language=='en'
    assert all(len(row)==16 for row in f.rows)
