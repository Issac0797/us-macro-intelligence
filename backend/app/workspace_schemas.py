"""Versioned, bounded single-user research configuration."""
import re
from datetime import date
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, BeforeValidator, model_validator


def date_only(value):
    if isinstance(value, str) and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('Only date precision is supported')
    return value


Day = Annotated[date, BeforeValidator(date_only)]
Frequency = Literal['daily', 'weekly', 'monthly', 'quarterly']


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Calculation(StrictModel):
    transform: Literal['raw', 'mom', 'yoy', 'annualized_3m', 'annualized_6m', 'moving_average', 'z_score', 'index_100', 'absolute_change'] = 'raw'
    window: int = Field(12, ge=3, le=365)
    base_date: Day | None = None

    @model_validator(mode='after')
    def parameters(self):
        if self.transform == 'moving_average' and self.window not in (3, 6, 12):
            raise ValueError('Moving average window must be 3, 6 or 12 native observations')
        if self.transform == 'index_100' and not self.base_date:
            raise ValueError('Index 100 requires an explicit observation base_date')
        return self


class ChartLine(StrictModel):
    key: str = Field(min_length=1, max_length=60, pattern=r'^[A-Za-z0-9_-]+$')
    series_id: str = Field(min_length=1, max_length=32, pattern=r'^[A-Z0-9]+$')
    subtract_series_id: str | None = Field(None, max_length=32, pattern=r'^[A-Z0-9]+$')
    display_name: str = Field(min_length=1, max_length=120)
    calculations: list[Calculation] = Field(default_factory=lambda: [Calculation()], min_length=1, max_length=3)
    axis: Literal['left', 'right'] = 'left'
    line_style: Literal['solid', 'dashed', 'dotted'] = 'solid'
    visible: bool = True
    chart_type: Literal['line', 'bar'] = 'line'
    alignment: Literal['period_end', 'period_average', 'last_available'] = 'period_end'


class ChartConfiguration(StrictModel):
    configuration_version: Literal[1] = 1
    title: str = Field('Macro Research', min_length=1, max_length=140)
    start: Day = date(2020, 1, 1)
    end: Day = Field(default_factory=date.today)
    data_mode: Literal['latest', 'vintage'] = 'latest'
    as_of: Day | None = None
    frequency: Frequency = 'monthly'
    show_recessions: bool = True
    lines: list[ChartLine] = Field(min_length=1, max_length=6)
    data_fingerprints: dict[Annotated[str, Field(max_length=60)], Annotated[str, Field(pattern=r'^[a-f0-9]{64}$')]] = Field(default_factory=dict, max_length=6)

    @model_validator(mode='after')
    def coherent(self):
        if self.start > self.end or (self.end-self.start).days > 43830:
            raise ValueError('Date range must be ordered and at most 120 years')
        if self.data_mode == 'vintage' and not self.as_of:
            raise ValueError('Historical Vintage mode requires a shared as_of date')
        if self.data_mode == 'latest' and self.as_of:
            raise ValueError('Latest mode must not contain as_of')
        if len({line.key for line in self.lines}) != len(self.lines):
            raise ValueError('Line keys must be unique')
        return self


class WorkspaceWrite(StrictModel):
    name: str = Field(min_length=1, max_length=140)
    description: str = Field('', max_length=2000)
    configuration: ChartConfiguration

