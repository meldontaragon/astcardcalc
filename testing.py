from datetime import timedelta
import os
from urllib.parse import urlparse, parse_qs

from fflogsapi import get_bearer_token, get_actor_lists, get_damage_events, get_fight_info, decompose_url
from cardcalc_data import ActorList, FightInfo, SearchWindow, CardCalcException
from damagecalc import search_burst_window, calculate_tick_snapshot_damage, calculate_tick_damage, time_averaged_dps
from cardcalc import cardcalc

import pandas as pd
import numpy as np

import plotly.io as pio
import plotly.express as px
import plotly.graph_objects as go

import scipy.signal as sig
import scipy as scipy

def test_to_dict_damage_table(card_damage_table):
    print(card_damage_table)

def test_to_dict_actor_list(actor_list):
    test_dict = actor_list.to_dict()
    print(test_dict)

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

token = get_bearer_token()

# url = 'https://www.fflogs.com/reports/MQjnkJ7YRwqCaLcN#fight=1'
# url = 'https://www.fflogs.com/reports/KaCwVdgTQYhmRAxD#fight=10'
# url = 'https://www.fflogs.com/reports/byLqHjz8MnphQP3r#fight=1'
# url = 'https://www.fflogs.com/reports/TmzFDHfWL8bhdMAn#fight=6'
url = 'https://www.fflogs.com/reports/fZXhDbTjw7GWmKLz#fight=2'

report_id, fight_id = decompose_url(url)

# print('Report: {} ({})\nFight: {} ({})'.format(report_id, type(report_id), fight_id, type(fight_id)))

cardcalc_data, actors, _ = cardcalc(report_id, fight_id, token)

dmg_tbl = cardcalc_data[0]['cardDamageTable']

test_to_dict_damage_table(dmg_tbl)

# fight_info = get_fight_info(report_id, fight_id, token)
# actor_list = get_actor_lists(fight_info, token)

# damage_data = get_damage_events(fight_info, token)

# damage_report = calculate_tick_snapshot_damage(damage_data)
# damage_report_base = calculate_tick_damage(damage_data)

# search_window = SearchWindow(fight_info.start, fight_info.end, 15000, 1000)
# burst_damage_collection = search_burst_window(damage_report, search_window, actor_list)

# df_base = damage_report_base['combinedDamage']
# df_snapshot = damage_report['combinedDamage']

print(actors)


