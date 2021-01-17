from datetime import timedelta
import os
from urllib.parse import urlparse, parse_qs

from fflogsapi import get_bearer_token, get_actor_lists, get_damage_events, get_fight_info
from cardcalc_data import ActorList, FightInfo, SearchWindow
from damagecalc import search_burst_window, calculate_tick_snapshot_damage

import pandas as pd
import numpy as np
import plotly.io as pio
import plotly.express as px

def decompose_url(url):
    parts = urlparse(url)

    report_id = [segment for segment in parts.path.split('/') if segment][-1]
    try:
        fight_id = parse_qs(parts.fragment)['fight'][0]
    except KeyError:
        raise CardCalcException("Fight ID is required. Select a fight first")

    if fight_id == 'last':
        fight_id = get_last_fight_id(report_id)

    fight_id = int(fight_id)
    return report_id, fight_id

token = get_bearer_token()

url = 'https://www.fflogs.com/reports/MQjnkJ7YRwqCaLcN#fight=1'
url = 'https://www.fflogs.com/reports/KaCwVdgTQYhmRAxD#fight=10'
report_id, fight_id = decompose_url(url)

fight_info = get_fight_info(report_id, fight_id, token)
(players, pets) = get_actor_lists(fight_info, token)

actors = ActorList(players, pets)

damage_data = get_damage_events(fight_info, token)
damage_report = calculate_tick_snapshot_damage(damage_data)
search_window = SearchWindow(fight_info.start, fight_info.end, 15000, 1000)
burst_damage_collection = search_burst_window(damage_report, search_window, actors)

df = pd.DataFrame(damage_report['combinedDamage'], columns=['timestamp', 'type', 'sourceID', 'targetID', 'abilityGameID', 'amount'])

df['duration'] = df['timestamp'].apply(lambda x: fight_info.Duration(x))

# fig = px.scatter(df, x='duration', y='amount', color='type')
# fig.update_layout(template='plotly_white')
# fig.update_layout(title='Damage Output Snapshot')
# fig.show()
# pio.write_html(fig, file='index.html', auto_open=True)

actors.PrintAll()
