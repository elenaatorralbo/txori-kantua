"""Versioned, explicit seasonal/region allowlists and score thresholds (#17).

An allowlist is a reviewed configuration, not a claim of ecological absence.
No location or coordinates are added to events. Missing region/month fails closed.
"""
import math
from collections import Counter
from datetime import date


class DetectionFilter:
    def __init__(self,*,threshold=.5,region,seasons,revision):
        if not math.isfinite(threshold) or not 0<=threshold<=1:
            raise ValueError('threshold must be in [0,1]')
        if not region or not revision or not isinstance(seasons,dict):
            raise ValueError('region, revision and seasonal allowlists are required')
        self.threshold,self.region,self.revision=threshold,region,revision
        self.seasons=seasons
        self.stats=Counter()

    def accepts(self,candidate,day:date):
        if not math.isfinite(candidate.confidence) or not 0<=candidate.confidence<=1:
            self.stats['invalid_score']+=1
            return False
        allowed=self.seasons.get(self.region,{}).get(str(day.month))
        if allowed is None:
            self.stats['missing_context']+=1
            return False
        if candidate.confidence<self.threshold:
            self.stats['below_threshold']+=1
            return False
        if candidate.scientific_name not in allowed:
            self.stats['outside_allowlist']+=1
            return False
        self.stats['accepted']+=1
        return True
