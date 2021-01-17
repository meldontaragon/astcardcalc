from datetime import timedelta
import os

from python_graphql_client import GraphqlClient 

# Make sure we have the requests library
try:
    import requests
except ImportError:
    raise ImportError("FFlogs parsing requires the Requests module for python."
                      "Run the following to install it:\n    python -m pip install requests")

from requests_oauthlib import OAuth2Session
from oauthlib.oauth2 import BackendApplicationClient

from fflogsapi import get_fight_time, get_all_actors, get_card_play_events, get_cards_played, get_damages, get_all_damage_events, calculate_total_damage, sum_tick_damage_snapshots, search_draw_window

client_id = '9281480c-43fe-4fbd-9cd6-3090bee3dba1'
client_pass = 'KfJPAmBM5a0hUjo5vNFaS4cwLGhdtRRsplEElcyQ'
data = 'grant_type=client_credentials'
oauth_url = 'https://www.fflogs.com/oauth/token'

# r = requests.get(oauth_url, auth=(client_id, client_pass))
# print(r)

client = BackendApplicationClient(client_id=client_id)
oauth = OAuth2Session(client=client)
token = oauth.fetch_token(token_url=oauth_url, client_id=client_id, client_secret=client_pass)

#https://www.fflogs.com/reports/MQjnkJ7YRwqCaLcN#fight=1

# report_id = 'byLqHjz8MnphQP3r'
report_id = 'MQjnkJ7YRwqCaLcN'
fight = 1

data = get_fight_time(report_id, fight, token)

start_time = data['startTime']
end_time = data['endTime']

(players, pets) = get_all_actors(report=report_id, start_time=start_time, end_time=end_time, token=token)

# card_events = get_card_play_events(report_id, start_time, end_time, token)

# cards = get_cards_played(card_events, start_time, end_time)

# player_cards = []
# for c in cards:
#     if c['target'] not in pets:
#         player_cards.append(c)

# cards = player_cards

custom_start = 100000
custom_end = 140000

damage_data = get_all_damage_events(report_id, start_time, end_time, token)
damage_report = sum_tick_damage_snapshots(damage_data)

# (total_damage, player_damage) = calculate_total_damage(damage_report, custom_start, custom_end, players, pets)

max_damage_windows = search_draw_window(damage_report, start_time, end_time, 5000, 1000, players, pets)

tabular = '{:<11}{:<24}{:>9}'
print(tabular.format('Time', 'Player', 'Damage'))
print('-' * 50)
for m in max_damage_windows:
    print(tabular.format(str(timedelta(milliseconds=(m-start_time)))[2:11], players[max_damage_windows[m]['id']]['name'], max_damage_windows[m]['damage']))
    

# print('Start Time: {}\nEnd Time:   {}\n'.format(str(timedelta(milliseconds=(custom_start - start_time)))[2:11], str(timedelta(milliseconds=(custom_end - start_time)))[2:11]))

# print("Total Damage")
# for p in total_damage:
#     if p in players:
#         print('{:<24} - {:>9}'.format(players[p]['name'], total_damage[p]))
#     elif p in pets:
#         print('{:<24} - {:>9}'.format(pets[p]['name'], total_damage[p]))
#     else:
#         print('{:<24} - {:>9}'.format('id: ' + str(p), total_damage[p]))

# print()
# print("Player Damage")
# for p in player_damage:
#     if p in players:
#         print('{:<24} - {:>9}'.format(players[p]['name'], player_damage[p]))
#     else:
#         print('{:<24} - {:>9}'.format('id: ' + str(p), player_damage[p]))
