from datetime import date
from typing import Literal
from pydantic import Field, model_validator
from app.workspace_schemas import StrictModel, ChartLine, Day, Frequency

class AnalyticsConfiguration(StrictModel):
    kind: Literal['analytics'] = 'analytics'
    configuration_version: Literal[1] = 1
    title: str = Field('Macro Analytics',min_length=1,max_length=140)
    start: Day = date(2010,1,1)
    end: Day = Field(default_factory=date.today)
    data_mode: Literal['latest','vintage'] = 'latest'
    as_of: Day|None = None
    frequency: Frequency = 'monthly'
    lines: list[ChartLine] = Field(min_length=2,max_length=8)
    operation: Literal['correlation','rolling-correlation','lead-lag','rolling-statistics'] = 'correlation'
    data_fingerprints: dict[str,str] = Field(default_factory=dict,max_length=8)
    rule_parameters: dict[str,float] = Field(default_factory=dict,max_length=7)
    statistic: Literal['mean','std','z_score','percentile'] = 'z_score'
    view: Literal['analytics','business-cycle'] = 'analytics'
    method: Literal['pearson','spearman'] = 'pearson'
    window: int = Field(24,ge=3,le=120)
    max_lag: int = Field(12,ge=0,le=36)
    min_samples: int = Field(12,ge=3,le=120)
    show_ex_post_recessions: bool = False
    rule_version: Literal['cycle-v1'] = 'cycle-v1'
    @model_validator(mode='after')
    def valid(self):
        if self.start>self.end or (self.end-self.start).days>36525: raise ValueError('Ordered range, maximum 100 years')
        if self.data_mode=='vintage' and self.as_of is None: raise ValueError('Vintage requires shared as_of')
        if self.data_mode=='latest' and self.as_of is not None: raise ValueError('Latest must not set as_of')
        if len({l.key for l in self.lines})!=len(self.lines): raise ValueError('Duplicate line keys')
        from app.analytics.cycle import Thresholds
        Thresholds.model_validate(self.rule_parameters)
        return self
