"""Bounded RAM windows and normalized BirdNET detection events (#15–18)."""
from collections import Counter, deque
from dataclasses import dataclass
from datetime import timedelta
from threading import Lock

from .birdnet import WINDOW_SAMPLES, pcm16_to_float32
from ..messaging.events import new_detection, stable_event_id
from ..messaging.timestamps import parse_timestamp


@dataclass
class Window:
    pcm:bytearray
    observed_at:str

    def clear(self):
        self.pcm[:]=b'\x00'*len(self.pcm)


class WindowQueue:
    """Drop oldest window on overload. Wipe dropped and processed buffers."""
    def __init__(self,capacity=2):
        if type(capacity) is not int or not 1<=capacity<=16:
            raise ValueError('capacity must be between 1 and 16')
        self.capacity=capacity; self._queue=deque(); self._lock=Lock(); self.stats=Counter()

    def put(self,window):
        if len(window.pcm)!=WINDOW_SAMPLES*2:
            window.clear()
            raise ValueError('requires 3 seconds of mono 48 kHz S16_LE')
        with self._lock:
            if len(self._queue)==self.capacity:
                self._queue.popleft().clear(); self.stats['dropped']+=1
            self._queue.append(window); self.stats['captured']+=1

    def pop(self):
        with self._lock:
            return self._queue.popleft() if self._queue else None

    def close(self):
        with self._lock:
            while self._queue: self._queue.popleft().clear()


class Inference:
    def __init__(self,model,filter,station_id):
        self.model,self.filter,self.station_id=model,filter,station_id
        self.version=model.version()  # hash model once, not once per window
        self.stats=Counter()

    def process(self,window):
        samples=pcm16_to_float32(window.pcm)
        try:
            scores=self.model.predict(samples)
            start=parse_timestamp(window.observed_at)
            events=[]
            for candidate in self.model.top(scores,k=len(scores),species_only=True):
                if self.filter.accepts(candidate,start.date()):
                    events.append(new_detection(station_id=self.station_id,
                        scientific_name=candidate.scientific_name,confidence=candidate.confidence,
                        observed_at=start,window_end=start+timedelta(seconds=3),
                        model_name='BirdNET',model_version=self.version,
                        event_id=stable_event_id(self.station_id,window.observed_at,
                                                candidate.scientific_name,self.version)))
            self.stats['processed']+=1
            self.stats['detections']+=len(events)
            if not events: self.stats['empty']+=1
            return events
        except Exception:
            self.stats['errors']+=1
            raise
        finally:
            samples.fill(0)
            window.clear()
