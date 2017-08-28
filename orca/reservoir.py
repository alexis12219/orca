from __future__ import division
import numpy as np 
import matplotlib.pyplot as plt
import pandas as pd
import json
from .util import *


class Reservoir():

  def __init__(self, df, key):
    T = len(df)
    self.dayofyear = df.index.dayofyear
    self.month = df.index.month
    self.key = key
    self.wyt = df.SR_WYT_rolling # 120 day MA lag
    for k,v in json.load(open('orca/data/%s_properties.json' % key)).items():
        setattr(self,k,v)

    self.Q = df['%s_in_fix'% key].values * cfs_tafd
    self.E = df['%s_evap'% key].values * cfs_tafd
    self.fci = df['%s_fci' % key].values
    self.S = np.zeros(T)
    self.R = np.zeros(T)
    self.tocs = np.zeros(T)
    self.Rtarget = np.zeros(T)
    self.R_to_delta = np.zeros(T)
    self.S[0] = df['%s_storage' % key].iloc[0]
    self.R[0] = 0

    self.tocs_index = []
    for i,v in enumerate(self.tocs_rule['index']):        
        self.tocs_index.append(np.zeros(366))
        for day in range(0, 366):  
            self.tocs_index[i][day] = np.interp(day, self.tocs_rule['dowy'][i], self.tocs_rule['storage'][i])

    self.nodds = np.zeros(367)
    for i in range(0,366):  
        self.nodds[i] = np.interp(i, first_of_month, self.nodd)

  def current_tocs(self, d, ix):
    for i,v in enumerate(self.tocs_rule['index']):
        if ix > v:
            break
    return self.tocs_index[i][d]

  def step(self, t, d, m, wyt, dowy, dmin=0.0, sodd=0.0):

    envmin = self.env_min_flow[wyt][m-1] * cfs_tafd
    #nodd = np.interp(d, first_of_month, self.nodd)
    nodd = self.nodds[d]
    sodd *= self.sodd_pct * self.sodd_curtail_pct[wyt]
    self.tocs[t] = self.current_tocs(dowy, self.fci[t])
    dout = dmin * self.delta_outflow_pct

    if not self.nodd_meets_envmin:
      envmin += nodd 

    # decide next release
    W = self.S[t-1] + self.Q[t]
    # HB's idea for flood control relesae..
    # fcr = (W-self.tocs[t])*np.exp(4.5*10**-6 * (W-self.capacity))
    fcr = 0.2*(W-self.tocs[t])
    self.Rtarget[t] = np.max((fcr, nodd+sodd+dout, envmin)) 

    # then clip based on constraints
    self.R[t] = min(self.Rtarget[t], W - self.dead_pool)
    self.R[t] = min(self.R[t], self.max_outflow * cfs_tafd)
    self.R[t] +=  max(W - self.R[t] - self.capacity, 0) # spill
    self.S[t] = W - self.R[t] - self.E[t] # mass balance update
    self.R_to_delta[t] = max(self.R[t] - nodd, 0) # delta calcs need this

  def results_as_df(self, index):
    df = pd.DataFrame()
    names = ['storage', 'out', 'target', 'out_to_delta', 'tocs']
    things = [self.S, self.R, self.Rtarget, self.R_to_delta, self.tocs]
    for n,t in zip(names,things):
      df['%s_%s' % (self.key,n)] = pd.Series(t, index=index)
    return df


