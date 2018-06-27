import numpy as np 
import scipy.stats as sp
import pandas as pd
from sklearn import linear_model
from .write_json import modify
cfsd_mafd = 2.29568411*10**-5 * 86400 / 10 ** 6
cfs_tafd = 2.29568411*10**-5 * 86400 / 1000
pd.options.mode.chained_assignment = None  # default='warn'

def WYI_to_WYT(WYI, thresholds, values):
  for t,v in zip(thresholds,values):
    if WYI > t:
      return v

def octmar_cumulative(x): #cumulative inflow from october through march
	ix = (x.index.month >= 10) | (x.index.month <= 3)
	octmar = (x[ix]. sum() - x[ix].cumsum())
	ix = (x.index.month >= 4) & (x.index.month <= 7)
	x[ix] = octmar[5]
	aprjul = x[ix]
	return pd.concat([octmar,aprjul])

def aprjul_cumulative(x): #cumulative inflow from april through july
	ix = (x.index.month >= 4) & (x.index.month <= 7)
	aprjul = (x[ix].sum() - x[ix].cumsum())
	ix = (x.index.month >= 10) | (x.index.month <= 3)
	x[ix] = aprjul[0]
	octmar = x[ix]
	ix = (x.index.month == 8) | (x.index.month ==9)
	x[ix] = aprjul[3]
	augsep = x[ix]

	return pd.concat([octmar,aprjul,augsep]) 

def octmar_flow_to_date(x):
	ix = (x.index.month >= 10) | (x.index.month <= 3)
	octmar = x[ix].cumsum()
	ix = (x.index.month >= 4) & (x.index.month <= 7)
	x[ix] = octmar[5]
	aprjul =  x[ix]
	ix = (x.index.month == 8) | (x.index.month == 9)
	x[ix] = octmar[5]
	augsep = x[ix]
	return pd.concat([octmar,aprjul,augsep])

def aprjul_flow_to_date(x):
	ix = (x.index.month >= 4) & (x.index.month <= 7)
	aprjul =  x[ix].cumsum()
	return aprjul

def flow_to_date(x):
	# ix = (x.index.month >= 1) 
	cum_flow = x.cumsum()
	return cum_flow

def rem_flow(x):
	# ix = (x.index.month >= 1)
	remaining_flow = (x.sum() - x.cumsum())
	return remaining_flow

def get_forecast_WYI(df, zscore1, zscore2): #now determining forecasting regression coefficients based off perfect foresight
	flow_sites = ['BND_fnf', 'ORO_fnf', 'YRS_fnf', 'FOL_fnf']
	snow_sites = ['BND_swe', 'ORO_swe', 'YRS_swe', 'FOL_swe']

	Qm = (df[flow_sites].sum(axis=1).resample('MS').sum().to_frame(name='flow') * cfsd_mafd)

	Qm['WY'] = df.WY.resample('MS').first() # need this for grouping
	Qm['snow'] = df[snow_sites].sum(axis=1).resample('MS').first()
	Qm = Qm[Qm.WY != Qm.WY[-1]] 
	Qm['octmar_cumulative'] = (Qm.groupby('WY').flow
	                          .apply(octmar_cumulative)
	                          .reset_index(level=0)
	                          .drop('WY', axis=1)) 

	Qm['aprjul_cumulative'] = (Qm.groupby('WY').flow
	                           .apply(aprjul_cumulative))

	Qm['octmar_flow_to_date'] = (Qm.groupby('WY').flow
	                           .apply(octmar_flow_to_date))

	Qm['aprjul_flow_to_date'] = (Qm.groupby('WY').flow
	                           .apply(aprjul_flow_to_date)
	                           .reset_index(level=0).drop('WY', axis=1)) 

	aprjul_slopes = np.zeros(12)
	aprjul_intercepts = np.zeros(12)
	aprjul_means = np.zeros(12)
	aprjul_stds = np.zeros(12)
	octmar_means = np.zeros(12)
	octmar_stds = np.zeros(12)
	octmar_slopes = np.zeros(12)
	octmar_intercepts = np.zeros(12)
	month = Qm.index.month
	snow_ind = Qm.snow
	aprjul_cumulative_ind = Qm.aprjul_cumulative
	for m in range(1,13):
		oct_index = (month == 10)
		ix = (month == m)
		coeffs = np.polyfit(snow_ind[ix],aprjul_cumulative_ind[ix],1)
		aprjul_slopes[m-1] = coeffs[0]
		aprjul_intercepts[m-1] = coeffs[1]
		aprjul_means[m-1] = np.mean(aprjul_cumulative_ind[ix]) 
		aprjul_stds[m-1] =  np.std(aprjul_cumulative_ind[ix])
	octmar_flow_to_date_ind = Qm.octmar_flow_to_date	
	octmar_cumulative_ind = Qm.octmar_cumulative
	for m in list(range(10,13))+list(range(1,3)):  
		flow_coeffs = np.polyfit(octmar_flow_to_date_ind[oct_index], octmar_cumulative_ind[ix], 1)
		octmar_slopes[m-1] = flow_coeffs[0]
		octmar_intercepts[m-1] = flow_coeffs[1]
		octmar_means[m-1] = np.mean(octmar_cumulative_ind[ix])
		octmar_stds[m-1] = np.std(octmar_cumulative_ind[ix])
	stats =  {'aprjul_slope': aprjul_slopes,
                    'aprjul_intercept': aprjul_intercepts, 
                    'aprjul_mean': aprjul_means,
                    'aprjul_std':  aprjul_stds, 
                    'octmar_mean': octmar_means,
                    'octmar_std':  octmar_stds, 
                    'octmar_intercept': octmar_intercepts, 
                    'octmar_slope': octmar_slopes}

	stats = pd.DataFrame(stats, columns = ['aprjul_slope',
                    'aprjul_intercept', 
                    'aprjul_mean',
                    'aprjul_std', 
                    'octmar_mean',
                    'octmar_std', 
                    'octmar_intercept', 
                    'octmar_slope'])
	stats.to_csv('WYI_forcasting_regression_stats.csv')
	for s in stats: 
		df[s] = pd.Series(index=df.index)
		for m in range(1,13):
			Qm.loc[month==m, s] = stats[s][m-1]

	Qm = Qm.fillna(0)
	Qm['WYI'] = pd.Series(index=Qm.index)
	prev = 10
	for index, row in Qm.iterrows():
		ix = index.month
		if (ix == 10) | (ix == 11):
			WYI = 0.3 * prev + 0.3 * (Qm.loc[index, 'octmar_flow_to_date'] + Qm.loc[index, 'octmar_mean'])\
			+ 0.4 * (Qm.loc[index, 'aprjul_flow_to_date'] + Qm.loc[index, 'aprjul_mean'])
		elif (ix == 12) | (ix <= 4):
			WYI = 0.3 * prev + 0.3 * (Qm.loc[index, 'octmar_flow_to_date'] + Qm.loc[index, 'octmar_mean'])\
			+ 0.4 * (Qm.loc[index, 'aprjul_flow_to_date'] +  (Qm.loc[index, 'aprjul_slope'] * Qm.loc[index, 'snow'] + Qm.loc[index,'aprjul_intercept'])*zscore1)
		elif ix == 5: 
			WYI = 0.3 * prev + 0.3 * (Qm.loc[index, 'octmar_flow_to_date'] + Qm.loc[index, 'octmar_mean'])\
			+ 0.4 * (Qm.loc[index, 'aprjul_flow_to_date'] + (Qm.loc[index, 'aprjul_slope'] * Qm.loc[index, 'snow'] + Qm.loc[index,'aprjul_intercept'])*zscore1)
		if (ix == 9) | (ix == 8):
			WYI = np.NaN
		Qm.loc[index, 'WYI'] = WYI

	Qm.WYI = Qm.WYI.shift(periods=-1)
	return(Qm.WYI)

def forecast(df):
	WYI_sim = get_forecast_WYI(df,0.4,0) #wyt
	df['WYI_sim'] = WYI_sim
	df.WYI_sim = df.WYI_sim.fillna(method = 'bfill')
	df.loc[df['WYI_sim'].isnull(),'WYI_sim'] = df['SR_WYI']

	df['WYT_sim'] = df.WYI_sim.apply(WYI_to_WYT,
	                               thresholds=[9.2, 7.8, 6.5, 5.4, 0.0], 
	                               values=['W', 'AN', 'BN', 'D', 'C'])

	###making forcasts for reservoir carryover:

	snow_sites = ['BND_swe', 'ORO_swe','FOL_swe']
	res_ids = ['SHA','ORO','FOL']

	SHA_inf = (df['SHA_fnf'].to_frame(name='inf') * cfsd_mafd)  
	ORO_inf = (df['ORO_fnf'].to_frame(name='inf') * cfsd_mafd)
	FOL_inf = (df['FOL_fnf'].to_frame(name='inf') * cfsd_mafd)


	res_frames = [SHA_inf,ORO_inf,FOL_inf]
	stats_file = pd.DataFrame()
	for r, swe, res_id in zip(res_frames, snow_sites, res_ids):
		r['WY'] = df.WY
		r['DOWY'] = df.DOWY
		r['snowpack'] = df[swe]
		r = r[r.WY != r.WY[-1]]
		month = r.index.month

		r['cum_flow_to_date'] = (r.groupby('WY').inf
		                           .apply(flow_to_date))
		r['remaining_flow'] = (r.groupby('WY').inf
		                            .apply(rem_flow))
		r.cum_flow_to_date.fillna(method='ffill', inplace=True)
		slopes = np.zeros(365)
		intercepts = np.zeros(365)
		means = np.zeros(365)
		stds = np.zeros(365)
		snowpack = r.snowpack
		remaining_flow = r.remaining_flow
		DOWY = r.DOWY
		for d in range(1,365):
			ix = (DOWY == d)
			coeffs = np.polyfit(snowpack[ix],remaining_flow[ix],1)
			slopes[d] = coeffs[0]
			intercepts[d] = coeffs[1]
			means[d] = np.mean(remaining_flow[ix]) 
			stds[d] = np.std(remaining_flow[ix])
		

		res_stats =['%s_slope'%res_id,'%s_intercept'%res_id,'%s_mean'%res_id,'%s_std'%res_id]

		stats =  {res_stats[0]: slopes,
		                  res_stats[1]: intercepts, 
		                  res_stats[2]: means,
		                  res_stats[3]: stds}


		stats = pd.DataFrame(stats, columns = [res_stats])

		if res_id == 'SHA':
			stats_file = stats
		else:
			stats_file[res_stats] = stats

		stats = stats.values.T
		for i,s in enumerate(stats):
			yearly_stats = stats[i]
			v = np.append(yearly_stats,np.tile(yearly_stats, 3)) #1997-2000 WY
			v = np.append(v,[yearly_stats[364]]) #leap year
			for y in range(4): # 14 more years
				v = np.append(v,np.tile(yearly_stats, 4))
				v = np.append(v,[yearly_stats[364]]) #leap year
			v = np.append(v,np.tile(yearly_stats, 1)) #2017 WY
			r[res_stats[i]] = pd.Series(v,index=r.index)
		r.rename(columns = {'cum_flow_to_date':'%s_cum_flow_to_date'%res_id}, inplace=True)
		r.rename(columns = {'remaining_flow':'%s_remaining_flow'%res_id}, inplace=True)
		r.rename(columns = {'snowpack':'%s_snowpack'%res_id}, inplace=True)
		r.drop(['inf','WY','DOWY'], axis=1, inplace=True)
		df = pd.concat([df, r], axis=1, join_axes=[df.index])
	return df,stats_file

	# stats_file.to_csv('carryover_regression_statistics.csv')
	# df.to_csv('orca-data-forecasted.csv')



#############climate projection functions
def get_projection_forecast_WYI(df, stats_file,zscore1, zscore2): #now determining forecasting regression coefficients based off perfect foresight
	flow_sites = ['BND_fnf', 'ORO_fnf', 'YRS_fnf', 'FOL_fnf']
	snow_sites = ['BND_swe', 'ORO_swe', 'YRS_swe', 'FOL_swe']

	Qm = (df[flow_sites].sum(axis=1).resample('M').sum().to_frame(name='flow') * cfsd_mafd)

	Qm['WY'] = df.WY.resample('M').first() # need this for grouping

	Qm['snow'] = df[snow_sites].sum(axis=1).resample('M').first()
	Qm = Qm[Qm.WY != Qm.WY[-1]] 
	Qm['octmar_cumulative'] = (Qm.groupby('WY').flow
	                          .apply(octmar_cumulative)
	                          .reset_index(level=0)
	                          .drop('WY', axis=1)) 

	Qm['aprjul_cumulative'] = (Qm.groupby('WY').flow
	                           .apply(aprjul_cumulative))

	Qm['octmar_flow_to_date'] = (Qm.groupby('WY').flow
	                           .apply(octmar_flow_to_date))

	Qm['aprjul_flow_to_date'] = (Qm.groupby('WY').flow
	                           .apply(aprjul_flow_to_date)
	                           .reset_index(level=0).drop('WY', axis=1)) 

	month = Qm.index.month
	snow_ind = Qm.snow
	aprjul_cumulative_ind = Qm.aprjul_cumulative
	octmar_flow_to_date_ind = Qm.octmar_flow_to_date	
	octmar_cumulative_ind = Qm.octmar_cumulative

	# stats = pd.read_csv('WYI_forcasting_regression_stats.csv', index_col=0, parse_dates=True)

	for s in stats_file: 
		df[s] = pd.Series(index=df.index)
		for m in range(1,13):
			Qm.loc[month==m, s] = stats_file[s][m-1]
  #Qm.octmar_cumulative = Qm.octmar_cumulative.shift(periods=1)
  #Qm.aprjul_cumulative = Qm.aprjul_cumulative.shift(periods=1)

	Qm = Qm.fillna(0)
	Qm['WYI'] = pd.Series(index=Qm.index)
	prev = 10
	for index, row in Qm.iterrows():
		ix = index.month
		if (ix == 10) | (ix == 11):
			WYI = 0.3 * prev + 0.3 * (Qm.loc[index, 'octmar_flow_to_date'] + Qm.loc[index, 'octmar_mean'])\
			+ 0.4 * (Qm.loc[index, 'aprjul_flow_to_date'] + Qm.loc[index, 'aprjul_mean'])
		elif (ix == 12) | (ix <= 4):
			WYI = 0.3 * prev + 0.3 * (Qm.loc[index, 'octmar_flow_to_date'] + Qm.loc[index, 'octmar_mean'])\
			+ 0.4 * (Qm.loc[index, 'aprjul_flow_to_date'] +  (Qm.loc[index, 'aprjul_slope'] * Qm.loc[index, 'snow'] + Qm.loc[index,'aprjul_intercept'])*zscore1)
		elif ix == 5: 
			WYI = 0.3 * prev + 0.3 * (Qm.loc[index, 'octmar_flow_to_date'] + Qm.loc[index, 'octmar_mean'])\
			+ 0.4 * (Qm.loc[index, 'aprjul_flow_to_date'] + (Qm.loc[index, 'aprjul_slope'] * Qm.loc[index, 'snow'] + Qm.loc[index,'aprjul_intercept'])*zscore1)
#right now using zscore- more conservative- will discuss later
		if (ix == 9) | (ix == 8):
			WYI = np.NaN
		Qm.loc[index, 'WYI'] = WYI

	Qm.WYI = Qm.WYI.shift(periods=-1)
	# Qm.WYI = Qm.WYI.fillna(method = 'bfill')
	return(Qm.WYI)

def projection_forecast(df):
	WYI_sim = get_forecast_WYI(df,0.4,0) #wyt
	df['WYI_sim'] = WYI_sim
	df.WYI_sim = df.WYI_sim.fillna(method = 'bfill')
	df.loc[df['WYI_sim'].isnull(),'WYI_sim'] = df['SR_WYI']

	df['WYT_sim'] = df.WYI_sim.apply(WYI_to_WYT,
                               thresholds=[9.2, 7.8, 6.5, 5.4, 0.0], 
                               values=['W', 'AN', 'BN', 'D', 'C'])

	snow_sites = ['BND_swe', 'ORO_swe','FOL_swe']
	res_ids = ['SHA','ORO','FOL']

	SHA_inf = (df['BND_fnf'].to_frame(name='inf') * cfsd_mafd)  
	ORO_inf = (df['ORO_fnf'].to_frame(name='inf') * cfsd_mafd)
	FOL_inf = (df['FOL_fnf'].to_frame(name='inf') * cfsd_mafd)


	res_frames = [SHA_inf,ORO_inf,FOL_inf]

	for r, swe, res_id in zip(res_frames, snow_sites, res_ids):

		r['WY'] = df.WY
		r['DOWY'] = df.DOWY
		r['snowpack'] = df[swe]
		r = r[r.WY != r.WY[-1]]
		month = r.index.month

		r['cum_flow_to_date'] = (r.groupby('WY').inf
		                           .apply(flow_to_date))
		r['remaining_flow'] = (r.groupby('WY').inf
		                            .apply(rem_flow))
		r.cum_flow_to_date.fillna(method='ffill', inplace=True)

		res_stats =['%s_slope'%res_id,'%s_intercept'%res_id,'%s_mean'%res_id,'%s_std'%res_id]

		stats = pd.read_csv('carryover_regression_statistics.csv', index_col = 0)
		stats = stats[res_stats]
		stats = stats.values.T
		for i,s in enumerate(stats):
			yearly_stats = stats[i]
			v = np.append(yearly_stats,np.tile(yearly_stats, 1)) #2000 WY
			v = np.append(v,[yearly_stats[364]]) #leap year
			for y in range(24): # 2001-2096 WYs
				v = np.append(v,np.tile(yearly_stats, 4))
				v = np.append(v,[yearly_stats[364]]) #leap year
			v = np.append(v,np.tile(yearly_stats, 2)) #2097-2099 WY
			r[res_stats[i]] = pd.Series(v,index=r.index)
		r.rename(columns = {'cum_flow_to_date':'%s_cum_flow_to_date'%res_id}, inplace=True)
		r.rename(columns = {'remaining_flow':'%s_remaining_flow'%res_id}, inplace=True)
		r.rename(columns = {'snowpack':'%s_snowpack'%res_id}, inplace=True)

		r.drop(['inf','WY','DOWY'], axis=1, inplace=True)
		df = pd.concat([df, r], axis=1, join_axes=[df.index])

	return df