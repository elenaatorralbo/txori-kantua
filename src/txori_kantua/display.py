"""Presence-driven LCD state, independent of the physical backlight driver."""
from dataclasses import dataclass

from .lcd import paginate_text
from .messaging.contracts import validate
from .messaging.timestamps import to_epoch_ms
from .pir import PresenceTracker
from .touch import TouchDebouncer

LANGUAGES=('es','eu','en')
NO_DATA={'es':'Sin datos recientes','eu':'Ez dago datu berririk','en':'No recent data'}
OFFLINE={'es':'Sin conexion MQTT','eu':'MQTT konexiorik ez','en':'MQTT disconnected'}


@dataclass(frozen=True)
class Frame:
    rows:tuple[str,str]
    backlight:bool
    language:str


class DisplayController:
    def __init__(self,*,catalogue=None,warmup_ms=60000,debounce_ms=50,timeout_ms=20000,max_age_ms=300000):
        if timeout_ms<=0 or max_age_ms<=0: raise ValueError('timeouts must be positive')
        self.catalogue=catalogue or {}
        self.pir=PresenceTracker(stabilization_ms=warmup_ms)
        self.touch=TouchDebouncer(debounce_ms)
        self.timeout_ms,self.max_age_ms=timeout_ms,max_age_ms
        self.latest=None
        self.latest_key=None
        self.last_interaction=None
        self.page=0
        self.language=0
        self.connected=False

    def receive(self,event):
        validate('detection',event)
        key=(to_epoch_ms(event['observed_at']),event['event_id'])
        if self.latest_key is None or key>self.latest_key:
            # Copy only metadata consumed by the display; callers cannot mutate it.
            self.latest=(key[0],event['species']['scientific_name'])
            self.latest_key=key
            self.page=0
            return True
        return False

    def tick(self,*,pir,touch,monotonic_ms,utc_ms):
        presence=self.pir.update(pir,monotonic_ms)
        touched=self.touch.update(touch,monotonic_ms)
        if presence.activated or touched:
            self.last_interaction=monotonic_ms
        lang=LANGUAGES[self.language]
        pages=self._pages(lang,utc_ms)
        if touched:
            self.page+=1
            if self.page>=len(pages):
                self.page=0; self.language=(self.language+1)%len(LANGUAGES)
                lang=LANGUAGES[self.language]; pages=self._pages(lang,utc_ms)
        self.page%=len(pages)
        on=self.last_interaction is not None and monotonic_ms-self.last_interaction<self.timeout_ms
        return Frame(pages[self.page],on,lang)

    def _pages(self,lang,utc_ms):
        if not self.connected: return paginate_text(OFFLINE[lang])
        if self.latest is None or not 0<=utc_ms-self.latest[0]<=self.max_age_ms:
            return paginate_text(NO_DATA[lang])
        name=self.latest[1]
        translated=self.catalogue.get(name,{}).get(lang) or name
        return paginate_text(translated)
