"""Additive dashboard JSON stored in the existing workspace table; v1 stays valid."""
from typing import Literal
from pydantic import Field, model_validator
from app.workspace_schemas import StrictModel, ChartConfiguration, Day


class GridCell(StrictModel):
    x:int=Field(0,ge=0,le=11)
    y:int=Field(0,ge=0,le=100)
    w:int=Field(6,ge=3,le=12)
    h:int=Field(4,ge=3,le=10)
    @model_validator(mode='after')
    def bounded(self):
        if self.x+self.w>12:raise ValueError('Grid cell exceeds 12 columns')
        return self


class SavedZoom(StrictModel):
    start:Day
    end:Day
    @model_validator(mode='after')
    def ordered(self):
        if self.start>self.end:raise ValueError('Zoom must be ordered')
        return self


class DashboardChart(StrictModel):
    id:str=Field(min_length=1,max_length=60,pattern=r'^[A-Za-z0-9_-]+$')
    configuration:ChartConfiguration
    grid:GridCell=Field(default_factory=GridCell)
    linked:bool=True
    independent:bool=False
    collapsed:bool=False
    zoom:SavedZoom|None=None


class DashboardConfiguration(StrictModel):
    kind:Literal['dashboard']='dashboard'
    configuration_version:Literal[2]=2
    title:str=Field('Research Dashboard',min_length=1,max_length=140)
    charts:list[DashboardChart]=Field(min_length=1,max_length=8)
    linked:bool=True
    layout_mode:Literal['single','two','four','custom']='custom'
    active_chart_id:str=Field(min_length=1,max_length=60)
    start:Day
    end:Day
    data_mode:Literal['latest','vintage']='latest'
    as_of:Day|None=None
    @model_validator(mode='after')
    def consistent(self):
        ids=[c.id for c in self.charts]
        if len(set(ids))!=len(ids) or self.active_chart_id not in ids:raise ValueError('Unique chart IDs and a valid active chart required')
        if self.start>self.end or (self.end-self.start).days>43830:raise ValueError('Invalid dashboard date range')
        if (self.data_mode=='vintage')!=(self.as_of is not None):raise ValueError('Vintage requires as_of; latest must not set it')
        for c in self.charts:
            if not c.independent and (c.configuration.data_mode!=self.data_mode or c.configuration.as_of!=self.as_of):raise ValueError('Linked historical context must match global mode/as_of, or be explicitly independent')
        return self
