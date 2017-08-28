import numpy as np
import pandas as pd
from .reservoir import Reservoir
from .delta import Delta
from .util import *


class Model():

  def __init__(self, datafile, sd='10-01-1999'):
    self.df = pd.read_csv(datafile, index_col=0, parse_dates=True)
    self.T = len(self.df)

    self.shasta = Reservoir(self.df, 'SHA')
    self.folsom = Reservoir(self.df, 'FOL')
    self.oroville = Reservoir(self.df, 'ORO')
    self.reservoirs = [self.shasta, self.folsom, self.oroville]
    self.delta = Delta(self.df, 'DEL')
    self.dayofyear = self.df.index.dayofyear
    self.month = self.df.index.month    
    self.wyt = self.df.SR_WYT_rolling

  def simulate(self):
    self.sumnodds = np.zeros(367)
    for d in range(0,365):
      for r in self.reservoirs:
        self.sumnodds[d] = sum([np.interp(d, first_of_month, r.nodd) for r in self.reservoirs])
   
    for t in range(1,self.T):
      d = self.dayofyear[t]
      dowy = water_day(d)
      m = self.month[t]
      wyt = self.wyt[t]
      self.delta.calc_flow_bounds(t, d, m, wyt, self.sumnodds[d])
      self.shasta.step(t, d, m, wyt, dowy, self.delta.dmin[t], self.delta.sodd_cvp[t])
      self.folsom.step(t, d, m, wyt, dowy, self.delta.dmin[t], self.delta.sodd_cvp[t])
      self.oroville.step(t, d, m, wyt, dowy, self.delta.dmin[t], self.delta.sodd_swp[t])
      self.delta.step(t, d, m, wyt,
                      self.shasta.R_to_delta[t] + self.folsom.R_to_delta[t],
                      self.oroville.R_to_delta[t], self.df.DeltaIn[t])

    return self.results_as_df()


  def results_as_df(self):
    df = pd.DataFrame(index=self.df.index)
    for x in [self.shasta, self.folsom, self.oroville, self.delta]:
      df = pd.concat([df, x.results_as_df(df.index)], axis=1)
    return df