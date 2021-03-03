import os
import profile
import pstats

from datetime import timedelta
from urllib.parse import urlparse, parse_qs

import pandas as pd
import numpy as np
import plotly.io as pio
import plotly.express as px
import plotly.graph_objects as go

from cardcalc_data import ActorList, FightInfo, SearchWindow, CardCalcException

from cardcalc_fflogsapi import get_bearer_token, get_actor_lists, get_damage_events, get_fight_info, decompose_url

from cardcalc_damage import search_burst_window, calc_snapshot_damage, calc_tick_damage, compute_time_averaged_dps, compute_total_damage, cleanup_hit_data

from cardcalc_cards import cardcalc

def test_plotting():
    # df_base.set_index(pd.TimedeltaIndex(data=df_base['timestamp'].apply(lambda x: fight_info.TimeElapsed(x)), unit='ms'), inplace=True)
    # df_snapshot.set_index(pd.TimedeltaIndex(data=df_snapshot['timestamp'].apply(lambda x: fight_info.TimeElapsed(x)), unit='ms'), inplace=True)

    total_ms = fight_info.end - fight_info.start
    step_size = int(total_ms/250)
    averaging_size = step_size*4
    print('Step: {}\nAveraging: {}'.format(step_size, averaging_size))

    average_dps = time_averaged_dps(damage_report, fight_info.start, fight_info.end, step_size, averaging_size)
    base_average_dps = time_averaged_dps(damage_report_base, fight_info.start, fight_info.end, step_size, averaging_size)

    average_dps.set_index(pd.TimedeltaIndex(data=average_dps['timestamp'].apply(lambda x: fight_info.TimeElapsed(x)), unit='ms'), inplace=True)
    base_average_dps.set_index(pd.TimedeltaIndex(data=base_average_dps['timestamp'].apply(lambda x: fight_info.TimeElapsed(x)), unit='ms'), inplace=True)

    average_dps.index = average_dps.index + pd.Timestamp("1970/01/01")
    base_average_dps.index = base_average_dps.index + pd.Timestamp("1970/01/01")

    fig = go.Figure()

    fig.add_trace(go.Scatter(name='Snapshot DPS', x=average_dps.index, y=average_dps['dps'], line=go.scatter.Line(shape='spline', smoothing=0.8)))

    fig.add_trace(go.Scatter(name='Base DPS', x=base_average_dps.index, y=base_average_dps['dps'], line=go.scatter.Line(shape='spline', smoothing=0.8)))

    # fig.update_layout(template='plotly_white')
    fig.update_layout(title='Damage Done')

    fig.update_layout(xaxis = dict(tickformat = '%M:%S', nticks=20))

    fig.update_layout(yaxis_range=[0,max(average_dps['dps'].max(), base_average_dps['dps'].max())*1.05])
    fig.show()

    # pio.write_html(fig, file='index.html', auto_open=True)

def testing_damage_report(url, token):
    report_id, fight_id = decompose_url(url, token)
    fight_info = get_fight_info(report_id, fight_id, token)
    actor_list = get_actor_lists(fight_info, token)

    damage_data = get_damage_events(fight_info, token)

    damage_report = calc_snapshot_damage(damage_data)
    damage_report = cleanup_hit_data(damage_report)
    
    return damage_report

def run_card_calc(url, token):
    report_id, fight_id = decompose_url(url, token)
    cardcalc_data, actors, _ = cardcalc(report_id, fight_id, token)
    
    return cardcalc_data, actors
def run_profile(url, token, filename):
    profile.run('run_card_calc(url, token)', filename)
    # profile.run('run_compute_total_damage(url, token)', filename)

def read_stats(filename, sort_options = 'tottime', print_options = 'cardcalc_'):
    stats = pstats.Stats(filename)
    stats.strip_dirs()

    stats.sort_stats(sort_options)
    stats.print_stats(print_options, 10)

def run_compute_total_damage(url, token):
    report_id, fight_id = decompose_url(url, token)
    fight_info = get_fight_info(report_id, fight_id, token)
    actors = get_actor_lists(fight_info, token)
    damage_events = get_damage_events(fight_info, token)
    damage_report = calc_snapshot_damage(damage_events)

    # damage = compute_total_damage(damage_report, fight_info.start, fight_info.end, actors)
    search_burst_window(damage_report, SearchWindow(fight_info.start, fight_info.end, 15000, 1000), actors)

###########################################################

# url = 'https://www.fflogs.com/reports/MQjnkJ7YRwqCaLcN#fight=1'
# url = 'https://www.fflogs.com/reports/KaCwVdgTQYhmRAxD#fight=10'
# url = 'https://www.fflogs.com/reports/byLqHjz8MnphQP3r#fight=1'
# url = 'https://www.fflogs.com/reports/TmzFDHfWL8bhdMAn#fight=6'
# url = 'https://www.fflogs.com/reports/fZXhDbTjw7GWmKLz#fight=2'
# url = 'https://www.fflogs.com/reports/p47GRHQBvaZXq1xk#fight=last'
# url = 'https://www.fflogs.com/reports/AkjHFtzwBMWJQdaY#fight=12&type=damage-done'
# url = 'https://www.fflogs.com/reports/8jA937KGgXMp4mbn#fight=1&type=damage-done'
# url = 'https://www.fflogs.com/reports/MHGzygdJFZkKh7vm#fight=1'
url = 'https://www.fflogs.com/reports/jtWfFhBLY1g9xbT8#fight=6&type=damage-done'
token = get_bearer_token()

# damage_report = testing_damage_report(url, token)

# print(damage_report.loc[(damage_report['timestamp']>= 3354304) & (damage_report['timestamp'] <= 3368464) & (damage_report['sourceID'] == 7)])

# print(damage_report.loc[(damage_report['timestamp']>= 3354304) & (damage_report['timestamp'] <= 3368464) & (damage_report['sourceID'] == 7) & (damage_report['hitType'] != 'dot'), 'amount'].sum())
# print(damage_report.loc[(damage_report['timestamp']>= 3354304) & (damage_report['timestamp'] <= 3368464) & (damage_report['sourceID'] == 7), 'amount'].sum())
# print(damage_report.loc[(damage_report['timestamp']>= 3354304) & (damage_report['timestamp'] <= 3368464) & (damage_report['sourceID'] == 7), 'amount'].sum()/1.06)

# data, actors = run_card_calc(url, token)

# for d in data:
#     if d['startTime'] == '00:33.554':
#         for p in d:
#             print('{}: {}'.format(p, d[p]))
    # else:
    #     print(d['startTime'])

for i in range(0,10):
    print('Running #{}'.format(i))
    filename = 'profile_role_tab_changes_{}.out'.format(i)
    run_profile(url, token, filename)
file_base = 'profile_base_rerun_{}.out'
# file_base = 'profile_lambda_compute_{}.out'

# for i in range(0,5):
    # print('Running #{}'.format(i))
    # filename = file_base.format(i)
    # run_profile(url, token, filename)

sort_options = 'time'
# sort_options = 'cumulative'

output_options = 'cardcalc_'
filename = 'profile_role_tab_changes_{}.out'.format(0)

filename = file_base.format(0)
stats = pstats.Stats(filename)
for i in range(1,10):
    filename = file_base.format(i)
    stats.add(filename)

stats.strip_dirs()
stats.sort_stats(sort_options)
stats.print_stats(output_options, 20)

read_stats(filename, output_option)
# read_stats('profile_total_burst_damage_output.txt', output_option)

def generate_sample_df():
    tmp_dict = [
        {
            'time': 1,
            'a': 5,
            'b': 3,
            'c': 10,},
        {
            'time': 2,
            'a': 12,
            'b': 129,
            'c': 92,},
        {
            'time': 3,
            'a': 12,
            'b': 9,
            'c': 0,}
    ]
    df =  pd.DataFrame(tmp_dict)
    df.set_index('time', inplace=True, drop=True)
    return df

# df = generate_sample_df()
# print(df.unstack())
# print(df.unstack().tolist())

# sorted_list = sorted(df.unstack().to_dict().items(), key=lambda x: x[1])
# for a in sorted_list:
#     print(a)