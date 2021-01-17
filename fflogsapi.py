"""
This contains code for pull requests from v2 of the FFLogs API
as required for damage and card calculations used in cardcalc
and damagecalc
"""

from datetime import timedelta
import os

from cardcalc import card_type, card_name, card_bonus

# Make sure we have the requests library
try:
    import requests
except ImportError:
    raise ImportError("FFlogs parsing requires the Requests module for python."
                      "Run the following to install it:\n    python -m pip install requests")

try:
    from requests_oauthlib import OAuth2Session
except ImportError:
    raise ImportError("This requires the OAuth Lib extension to the Requests module for python.")

try:
    from oauthlib.oauth2 import BackendApplicationClient
except ImportError:
    raise ImportError("This requires the OAuth Lib module for python.")

from python_graphql_client import GraphqlClient 

FFLOGS_CLIENT_ID = os.environ['FFLOGS_CLIENT_ID']
FFLOGS_CLIENT_SECRET = os.environ['FFLOGS_CLIENT_SECRET']

FFLOGS_OAUTH_URL = 'https://www.fflogs.com/oauth/token'
FFLOGS_URL = 'https://www.fflogs.com/api/v2/client'

client = GraphqlClient(FFLOGS_URL)

def get_bearer_token():
    client = BackendApplicationClient(client_id=client_id)
    oauth = OAuth2Session(client=client)
    token = oauth.fetch_token(token_url=FFLOGS_OAUTH_URL, client_id=client_id, client_secret=client_pass)
    return token

def request_fflogs_api(payload, token):
    headers = {
        'Content-TYpe': 'application/json',
        'Authorization': 'Bearer {}'.format(token['access_token']),
    }
    response = requests.request('POST', FFLOGS_URL, data=payload, headers=headers)

    return response

def call_fflogs_api(query, variables, token):
    headers = {
        'Content-TYpe': 'application/json',
        'Authorization': 'Bearer {}'.format(token['access_token']),
    }
    data = client.execute(query=query, variables=variables, headers=headers)

    return data

"""
    The following are some standard methods for getting fight 
    data that will be used a lot 
"""

def get_fight_time(report, fight, token):
    query = """
query reportData($code: String!) {
    reportData {
        report(code: $code) {
            fights {
                id
                startTime
                endTime
            }
        }
    }
}
"""
    variables = {'code': report}
    data = call_fflogs_api(query, variables, token)
    fights = data['data']['reportData']['report']['fights']
    
    for f in fights:
        if f['id'] == fight:
            return f

def get_all_actors(report, start_time, end_time, token):
    query = """
query reportData($code: String!, $startTime: Float!, $endTime: Float) {
    reportData {
        report(code: $code) {
            masterData {
                pets: actors(type: "Pet") {
                    id
                    name
                    type
                    subType
                    petOwner
                }
            }
            table: table(startTime: $startTime, endTime: $endTime)
        }
    }
}"""

    variables = {
        'code': report,
        'startTime': start_time,
        'endTime': end_time
    }
    data = call_fflogs_api(query, variables, token)
    master_data = data['data']['reportData']['report']['masterData']
    table = data['data']['reportData']['report']['table']

    pet_list = master_data['pets']
    composition = table['data']['composition']

    players = {}
    pets = {}

    for p in composition:
        players[p['id']] = {
            'name': p['name'],
            'id': p['id'],
            'type': p['type']
        }

    for p in pet_list:
        if p['petOwner'] in players:
            pets[p['id']] = {
                'name': p['name'],
                'id': p['id'],
                'owner': p['petOwner'],
            }

    return (players, pets)

def get_card_play_events(report, start_time, end_time, token):
    query = """
query reportData($code: String!, $startTime: Float!, $endTime: Float!) {
    reportData {
        report(code: $code) {
            cards: events(
                startTime: $startTime, 
                endTime: $endTime
                dataType: Buffs,
                filterExpression: "ability.id in (1001877, 1001883, 1001886, 1001887, 1001876, 1001882, 1001884, 1001885)"
            ) {
                data
            }            
        }
    }
}
"""

    variables = {
        'code': report,
        'startTime': start_time,
        'endTime': end_time
    }
    data = call_fflogs_api(query, variables, token)
    card_events = data['data']['reportData']['report']['cards']['data']
    
    return card_events

def get_cards_played(card_events, start_time, end_time):
    cards = []

    # Build list from events
    for event in card_events:
        # If applying the buff, add an item to the list of
        # cards played
        if event['type'] == 'applybuff':
            cards.append({
                'source': event['sourceID'],
                'target': event['targetID'],
                'start': event['timestamp'],
                'type': card_type(event['abilityGameID']),
                'name': card_name(event['abilityGameID']),
                'bonus': card_bonus(event['abilityGameID']),
                'id': event['abilityGameID'],
            })
        # If removing the buff, add an end timestamp to the matching application
        elif event['type'] == 'removebuff':
            card_set = [card
                      for card in cards
                      if card['target'] == event['targetID'] and card['source'] == event['sourceID'] and card['id'] == event['abilityGameID'] and 'end' not in card]
            # add it to the discovered tether
            if card_set:
                card = card_set[0]
                card['end'] = event['timestamp']
            # if there is no start event, add one and set it to 15s prior
            else:
                cards.append({
                    'source': event['sourceID'],
                    'target': event['targetID'],
                    'start': max(event['timestamp'] - 15000, start_time),
                    'end': event['timestamp'],
                    'type': card_type(event['abilityGameID']),
                    'name': card_name(event['abilityGameID']),
                    'bonus': card_bonus(event['abilityGameID']),
                    'id': event['abilityGameID'],
                })
    for card in cards:
        if 'end' not in card:
            card['end'] = min(card['start'] + 15000, end_time)

    return cards


def get_card_draw_events(report, start_time, end_time, token):
    query = """
query reportData($code: String!, $startTime: Float!, $endTime: Float!) {
    reportData {
        report(code: $code) {
            draws: events(
                startTime: $startTime,
                endTime: $endTime,
                filterExpression: "ability.id in (3590, 7448, 3593, 1000915, 1000913, 1000914, 1000917, 1000916, 1000918)"
                ) {
                    data
                }
        }
    }
}
"""
    variables = {
        'code': report,
        'startTime': start_time,
        'endTime': end_time,
    }

    data = call_fflogs_api(query, variables, token)
    card_events = data['data']['reportData']['report']['draws']['data']
    
    return card_events

"""
For the initial version of this the following simple rules are use.
Every event starts with one of the following and ends with the same:
 (1) Draw
 (2) Sleeve Draw
 (3) Divination
Redraws and plays are ignored
"""
def get_draw_windows(card_events, start_time, end_time):

    last_time = start_time
    last_event = 'Fight Start'
    draw_windows = []

    for events in card_events:
        # check if cast and if it's draw/sleeve/div
        if event['type'] == 'cast' and event['abilityGameID'] in [3590, 16552, 7448]:
            draw_windows.append({
                'start': last_time,
                'end': event['timestamp'],
                'startEvent': last_event,
                'endEvent': {3590: 'Draw', 16552: 'Divination', 7448: 'Sleeve Draw'}[event['abilityGameID']]
            })
            last_time = event['timestamp']
            last_event =  {3590: 'Draw', 16552: 'Divination', 7448: 'Sleeve Draw'}[event['abilityGameID']]
    
    return draw_windows

def get_damages(report, start_time, end_time, token):
    query = """
query reportData ($code: String!, $startTime: Float!, $endTime: Float!) {
    reportData {
        report(code: $code) {
            table(
                startTime: $startTime, 
                endTime: $endTime,
                dataType: DamageDone,
                filterExpression: "isTick='false'",
                viewBy: Source
                )
        }
    }
}"""

    variables = {
        'code': report,
        'startTime': start_time,
        'endTime': end_time,
    }
    
    data = call_fflogs_api(query, variables, token)
    damage_entries = data['data']['reportData']['report']['table']['data']['entries']

    damages = {}

    for d in damage_entries:
        damages[d['id']] = d['total']

    return damages

def get_all_damage_events(report, start_time, end_time, token):
    query = """
query reportData($code: String!, $startTime: Float!, $endTime: Float!) {
    reportData {
        report(code: $code) {
            damage: events(
                startTime: $startTime,
                endTime: $endTime,
                dataType: DamageDone,
                filterExpression: "isTick='false' and type!='calculateddamage'"
            ) {
                data
            }
            tickDamage: events(
                startTime: $startTime,
                endTime: $endTime,
                dataType: DamageDone,
                filterExpression: "isTick='true' and ability.id != 500000"
            ) {
                data
            }
            tickEvents: events(
                startTime: $startTime,
                endTime: $endTime,
                dataType: Debuffs,
                hostilityType: Enemies,
                filterExpression: "ability.id not in (1000493, 1001203, 1001195, 1001221)"
            ) {
                data
            }
            groundEvents: events(
                startTime: $startTime,
                endTime: $endTime,
                dataType: Buffs,
                filterExpression: "ability.id in (1000749, 1000501, 1001205, 1000312, 1001869)"
            ) {
                data
            }
        }
    }
}
"""

    variables = {
        'code': report,
        'startTime': start_time,
        'endTime': end_time,
    }
    data = call_fflogs_api(query, variables, token)

    base_damages = data['data']['reportData']['report']['damage']['data']
    tick_damages = data['data']['reportData']['report']['tickDamage']    ['data']
    tick_events = data['data']['reportData']['report']['tickEvents']['data']
    ground_events = data['data']['reportData']['report']['groundEvents']['data']

    raw_combined_ticks = tick_damages + tick_events + ground_events

    combined_tick_events = sorted(raw_combined_ticks, key=lambda tick: (tick['timestamp'], event_priority(tick['type'])))

    damage_data = {
        'rawDamage': base_damages,
        'tickDamage': combined_tick_events,
    }
    return damage_data

def event_priority(event):
    return {
        'applydebuff': 1,
        'applybuff': 1,
        'refreshdebuff': 2,
        'refreshbuff': 2,
        'removedebuff': 4,
        'removebuff': 4,
        'damage': 3,
        'damagesnapshot': 3,
    }[event]

"""
This takes a collection of damage events associated with ticks as well as the 

"""
def sum_tick_damage_snapshots(damage_report):
    active_debuffs = {}
    summed_tick_damage = []
    
    for event in damage_report['tickDamage']:
        action = (event['sourceID'], event['targetID'], event['abilityGameID'])

        # these events are either:
        # - apply{buff/debuff}
        # - reapply{buff,debuff}
        # - remove{buff,debuff} (can ignore these)
        # - damage

        # damage is summed from the application (apply or reapply) until
        # another application event or the end of the data
        
        # that damage is then reassociated with application event 

        if event['type'] in ['applybuff', 'refreshbuff', 'applydebuff', 'refreshdebuff'] and event['timestamp']:
            # if it's not an active effect then add it
            if action not in active_debuffs:
                active_debuffs[action] = {
                    'timestamp': event['timestamp'],
                    'damage': 0,
                }
            # if it is an active debuff then add a new damage event associated
            # with the sum and restart summing the damage from this event
            else:
                summed_tick_damage.append({
                    'type': 'damagesnapshot',
                    'sourceID': action[0],
                    'targetID': action[1],
                    'abilityGameID': action[2],
                    'amount': active_debuffs[action]['damage'],
                    'timestamp': active_debuffs[action]['timestamp'],
                })
                active_debuffs[action] = {
                    'timestamp': event['timestamp'],
                    'damage': 0,
                }
        elif event['type'] == 'damage':
            if action in active_debuffs:
                active_debuffs[action]['damage'] += event['amount']

    # now that we're done we can add the remaining events into the damage array
    for action in active_debuffs:
        if active_debuffs[action]['damage'] != 0:
            summed_tick_damage.append({
                'type': 'damagesnapshot',
                'sourceID': action[0],
                'targetID': action[1],
                'abilityGameID': action[2],
                'amount': active_debuffs[action]['damage'],
                'timestamp': active_debuffs[action]['timestamp'],
            })

    # finally sort the new array of snapshotdamage events and return it
    sorted_tick_damage = sorted(summed_tick_damage, key=lambda tick: tick['timestamp'])

    new_damage_report = {
        'rawDamage': damage_report['rawDamage'],
        'snapshotDamage': sorted_tick_damage,
        'combinedDamage': sorted(sorted_tick_damage + damage_report['rawDamage'], key=lambda tick: tick['timestamp'])
    }
    
    return new_damage_report

def calculate_total_damage(damage_report, start_time, end_time, players, pets):
    total_damage = {}

    # add all raw damage events
    for event in damage_report['combinedDamage']:
        if event['timestamp'] > start_time and event['timestamp'] < end_time:
            if event['sourceID'] in total_damage:
                total_damage[event['sourceID']] += event['amount']
            else:
                total_damage[event['sourceID']] = event['amount']                
        # assume order events and if the current event is after 
        # the end time then we're done
        if event['timestamp'] > end_time:
            break

    player_damage = {}
    for p in players:
        if p in total_damage:
            player_damage[p] = total_damage[p]
        # else: 
        #     player_damage[p] = 0

    for p in pets:
        if p in total_damage:
            if pets[p]['owner'] in player_damage:
                player_damage[pets[p]['owner']] += total_damage[p]
            else:
                player_damage[pets[p]['owner']] = total_damage[p]

    return (total_damage, player_damage)


"""
This function is designed to sum the damage done by each actor between the two
timestamp given by start_time and end_time. This involves a simple sum over
the raw damage done and then summing all damage done by tick events applied or 
refreshed during the time window

This should not be used and instead use the calculate_total_damage function
"""
def calculate_total_event_damage(damage_report, start_time, end_time, players, pets):
    raw_damage = {}
    tick_damage = {}

    # add all raw damage events
    for event in damage_report['rawDamage']:
        if event['timestamp'] > start_time and event['timestamp'] < end_time:
            if event['sourceID'] in raw_damage:
                raw_damage[event['sourceID']] += event['amount']
            else:
                raw_damage[event['sourceID']] = event['amount']                
        # assume order events and if the current event is after 
        # the end time then we're done
        if event['timestamp'] > end_time:
            break

    active_debuffs = []
    
    for event in damage_report['tickDamage']:
        action = (event['sourceID'], event['targetID'], event['abilityGameID'])

        if event['type'] in ['applybuff', 'refreshbuff', 'applydebuff', 'refreshdebuff'] and event['timestamp'] > start_time and event['timestamp'] < end_time:
            if action not in active_debuffs:
                active_debuffs.append(action)
        elif event['type'] in ['applybuff', 'refreshbuff', 'applydebuff', 'refreshdebuff'] and event['timestamp'] > end_time:
            if action in active_debuffs:
                active_debuffs.remove(action)
            # since we removed something we can check if we're done
            if len(active_debuffs) == 0 and event['timestamp'] > end_time:
                break
        elif event['type'] == 'damage':
            if action in active_debuffs:
                if event['sourceID'] in tick_damage:
                    tick_damage[event['sourceID']] += event['amount']
                else:
                    tick_damage[event['sourceID']] = event['amount']

    combined_damage = {}
    for p in players:
        combined_damage[p] = 0
        if p in raw_damage:
            combined_damage[p] += raw_damage[p]
        if p in tick_damage:            
            combined_damage[p] += tick_damage[p]

    for p in pets:
        if p in raw_damage:
            combined_damage[pets[p]['owner']] += raw_damage[p]
        if p in tick_damage:
            combined_damage[pets[p]['owner']] += tick_damage[p]

    return (raw_damage, tick_damage, combined_damage)

"""
This searches a window of time for the optimal card play

damage_report: contains all damage instances (both raw and from summing dot snapshots)
start_time: initial value for the search interval to start
end_time: final time that the interval can start
duration: the length of the interval (in milliseconds)
step_size: step_size for the search (in milliseconds)
"""
def search_draw_window(damage_report, start_time, end_time, duration, step_size, players, pets):

    # start searching at the start
    interval_start = start_time
    interval_end = interval_start + duration

    max_damage = {}

    while interval_start < end_time:
        (total_damage, player_damage) = calculate_total_damage(damage_report, interval_start, interval_end, players, pets)
        
        sorted_damage = sorted(player_damage.items(), key=lambda dmg: dmg[1])
        
        max_damage[interval_start] = {
            'id': sorted_damage[0][0],
            'damage': sorted_damage[0][1]
            }

        interval_start += step_size
        interval_end = interval_start + duration
    
    return max_damage