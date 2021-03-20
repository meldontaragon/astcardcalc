"""
This contains code for pull requests from v2 of the FFLogs API
as required for damage and card calculations used in cardcalc
and damagecalc
"""

from datetime import timedelta
import os

# Imports related to making API requests
from requests_oauthlib import OAuth2Session
from oauthlib.oauth2 import BackendApplicationClient
from python_graphql_client import GraphqlClient
from urllib.parse import urlparse, parse_qs

# local imports
from cardcalc_data import Player, Pet, FightInfo, CardCalcException, ActorList

FFLOGS_CLIENT_ID = os.environ['FFLOGS_CLIENT_ID']
FFLOGS_CLIENT_SECRET = os.environ['FFLOGS_CLIENT_SECRET']

FFLOGS_OAUTH_URL = 'https://www.fflogs.com/oauth/token'
FFLOGS_URL = 'https://www.fflogs.com/api/v2/client'

client = GraphqlClient(FFLOGS_URL)

# this is used to handle sorting events
def _event_priority(event):
    return {
        'applybuff': 1,
        'applybuffstack': 2,
        'applydebuff': 3,
        'applydebuffstack': 4,
        'refreshbuff': 5,
        'refreshdebuff': 6,
        'removedebuff': 7,
        'removebuff': 8,
        'removebuffstack': 9,
        'damage': 10,
        'damagesnapshot': 11,
    }[event]

# used to obtain a bearer token from the fflogs api
def get_bearer_token():
    token_client = BackendApplicationClient(client_id=FFLOGS_CLIENT_ID)
    
    oauth = OAuth2Session(client=token_client)
    token = oauth.fetch_token(token_url=FFLOGS_OAUTH_URL, client_id=FFLOGS_CLIENT_ID, client_secret=FFLOGS_CLIENT_SECRET)
    return token

# make a request for the data defined in query given a set of
# variables
def call_fflogs_api(query, variables, token):
    headers = {
        'Content-TYpe': 'application/json',
        'Authorization': 'Bearer {}'.format(token['access_token']),
    }
    data = client.execute(query=query, variables=variables, headers=headers)

    return data

def get_last_fight(report, token):
    variables = {
        'code': report
    }
    query = """
query reportData($code: String!) {
    reportData {
        report(code: $code) {
            fights {
                id
                startTime
                endTime
                name
                kill
            }
        }
    }
}
"""
    data = call_fflogs_api(query, variables, token)
    return data['data']['reportData']['report']['fights'][-1]['id']

def decompose_url(url, token):
    parts = urlparse(url)

    report_id = [segment for segment in parts.path.split('/') if segment][-1]
    try:
        fight_id = parse_qs(parts.fragment)['fight'][0]
    except KeyError:
        raise CardCalcException("Fight ID is required. Select a fight first")
    
    if fight_id == 'last':
        fight_id = get_last_fight(report_id, token)
    fight_id = int(fight_id)

    return report_id, fight_id

def get_fight_info(report, fight, token):
    variables = {
        'code': report
    }
    query = """
query reportData($code: String!) {
    reportData {
        report(code: $code) {
            fights {
                id
                startTime
                endTime
                name
                kill
            }
        }
    }
}
"""
    data = call_fflogs_api(query, variables, token)
    fights = data['data']['reportData']['report']['fights']

    for f in fights:
        if f['id'] == fight:
            return FightInfo(report_id=report, fight_number=f['id'], start_time=f['startTime'], end_time=f['endTime'], name=f['name'], kill=f['kill'])
        
    raise CardCalcException("Fight ID not found in report")

def get_actor_lists(fight_info: FightInfo, token):
    variables = {
        'code': fight_info.id,
        'startTime': fight_info.start,
        'endTime': fight_info.end,
    }    
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

    data = call_fflogs_api(query, variables, token)
    master_data = data['data']['reportData']['report']['masterData']
    table = data['data']['reportData']['report']['table']

    pet_list = master_data['pets']
    composition = table['data']['composition']

    players = {}
    pets = {}

    for p in composition:
        players[p['id']] = Player(p['id'], p['name'], p['type'])

    for p in pet_list:
        if p['petOwner'] in players:
            pets[p['id']] = Pet(p['id'], p['name'], p['petOwner'])

    return ActorList(players, pets)

def get_card_play_events(fight_info: FightInfo, token):
    variables = {
        'code': fight_info.id,
        'startTime': fight_info.start,
        'endTime': fight_info.end,
    }
    query = """
query reportData($code: String!, $startTime: Float!, $endTime: Float!) {
    reportData {
        report(code: $code) {
            cardPlayEvents: events(
                startTime: $startTime, 
                endTime: $endTime
                filterExpression: "ability.id in (1001877, 1001883, 1001886, 1001887, 1001876, 1001882, 1001884, 1001885, 7445, 7444, 4401, 4402, 4403, 4404, 4405, 4406)"
            ) {
                data
            }
        }
    }
}
"""

    data = call_fflogs_api(query, variables, token)
    card_events = data['data']['reportData']['report']['cardPlayEvents']['data']

    return card_events

def get_card_draw_events(fight_info: FightInfo, token):
    variables = {
        'code': fight_info.id,
        'startTime': fight_info.start,
        'endTime': fight_info.end,
    }
    query = """
query reportData($code: String!, $startTime: Float!, $endTime: Float!) {
    reportData {
        report(code: $code) {
            draws: events(
                startTime: $startTime,
                endTime: $endTime,
                filterExpression: "ability.id in (3590, 7448, 16552, 3593, 1000915, 1000913, 1000914, 1000917, 1000916, 1000918)"
                ) {
                    data
                }
        }
    }
}
"""

    data = call_fflogs_api(query, variables, token)
    card_events = data['data']['reportData']['report']['draws']['data']
    
    return card_events

def get_damage_events(fight_info: FightInfo, token):
    variables = {
        'code': fight_info.id,
        'startTime': fight_info.start,
        'endTime': fight_info.end,
    }
    query = """
query reportData($code: String!, $startTime: Float!, $endTime: Float!) {
    reportData {
        report(code: $code) {
            damage: events(
                startTime: $startTime,
                endTime: $endTime,
                dataType: DamageDone,
                limit: 10000,
                filterExpression: "isTick='false' and type!='calculateddamage'"
            ) {
                data
            }
            tickDamage: events(
                startTime: $startTime,
                endTime: $endTime,
                dataType: DamageDone,
                limit: 10000,
                filterExpression: "isTick='true' and ability.id != 500000"
            ) {
                data
            }
            tickEvents: events(
                startTime: $startTime,
                endTime: $endTime,
                dataType: Debuffs,
                hostilityType: Enemies,
                limit: 10000,
                filterExpression: "ability.id not in (1000493, 1001203, 1001195, 1001221)"
            ) {
                data
            }
            groundEvents: events(
                startTime: $startTime,
                endTime: $endTime,
                dataType: Buffs,
                limit: 10000,
                filterExpression: "ability.id in (1000749, 1000501, 1001205, 1000312, 1001869)"
            ) {
                data
            }
        }
    }
}
"""

    data = call_fflogs_api(query, variables, token)

    base_damages = data['data']['reportData']['report']['damage']['data']
    tick_damages = data['data']['reportData']['report']['tickDamage']    ['data']
    tick_events = data['data']['reportData']['report']['tickEvents']['data']
    ground_events = data['data']['reportData']['report']['groundEvents']['data']

    combined_tick_events = sorted((tick_damages + tick_events + ground_events), key=lambda tick: (tick['timestamp'], _event_priority(tick['type'])))

    damage_events = {
        'rawDamage': base_damages,
        'tickDamage': combined_tick_events,
    }
    return damage_events
