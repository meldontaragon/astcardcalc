from cardcalc_data import Player, Pet, SearchWindow, FightInfo, BurstDamageCollection, ActorList

import pandas as pd
import numpy as np

"""
This takes a collection of damage events associated with ticks as well as the 
"""
def calculate_tick_snapshot_damage(damage_events):
    active_debuffs = {}
    summed_tick_damage = []
    
    for event in damage_events['tickDamage']:
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

    combined_damage = pd.DataFrame(sorted(sorted_tick_damage + damage_events['rawDamage'], key=lambda tick: tick['timestamp']), columns=['timestamp', 'type', 'sourceID', 'targetID', 'abilityGameID', 'amount'])

    damage_report = {
        'combinedDamage': combined_damage
    }
    
    return damage_report

def calculate_tick_damage(damage_events):
    instanced_tick_damage = []
    
    for event in damage_events['tickDamage']:        
        if event['type'] == 'damage':
            instanced_tick_damage.append({
                'timestamp': event['timestamp'],
                'sourceID': event['sourceID'],
                'targetID': event['targetID'],
                'amount': event['amount'],
                'type': 'tickdamage',
                'abilityGameID': event['abilityGameID']
            })

    # finally sort the new array of snapshotdamage events and return it
    sorted_tick_damage = sorted(instanced_tick_damage, key=lambda tick: tick['timestamp'])

    combined_damage = pd.DataFrame(sorted(sorted_tick_damage + damage_events['rawDamage'], key=lambda tick: tick['timestamp']), columns=['timestamp', 'type', 'sourceID', 'targetID', 'abilityGameID', 'amount'])

    damage_report = {
        'combinedDamage': combined_damage
    }
    
    return damage_report

def calculate_total_damage(damage_report, start_time, end_time, actors: ActorList):
    combined_damage = {}

    # create a dataframe with only the current time window
    current_df = damage_report['combinedDamage'].query('timestamp >= {} and timestamp <= {}'.format(start_time, end_time))

    for actor in current_df['sourceID'].unique():
        combined_damage[actor] = current_df.query('sourceID == {}'.format(actor))['amount'].sum()

    player_damage = {}
    for p in actors.players:
        if p in combined_damage:
            player_damage[p] = combined_damage[p]
        else:
            player_damage[p] = 0
            combined_damage[p] = 0

    pet_damage = {}
    for p in actors.pets:
        if p in combined_damage:
            pet_damage[p] = combined_damage[p]
            if actors.pets[p].owner in player_damage:
                player_damage[actors.pets[p].owner] += combined_damage[p]
            else:
                player_damage[actors.pets[p].owner] = combined_damage[p]
        else:
            pet_damage[p] = 0
            combined_damage[p] = 0

    return (combined_damage, player_damage, pet_damage)

"""
This searches a window of time for the optimal card play

damage_report: contains all damage instances (both raw and from summing dot snapshots)
start_time: initial value for the search interval to start
end_time: final time that the interval can start
duration: the length of the interval (in milliseconds)
step_size: step_size for the search (in milliseconds)
"""
def search_burst_window(damage_report, search_window: SearchWindow, actors: ActorList):
    ###
    ### TODO: this function is likely the whole computational time
    ### of this project right now so any work to optimize this will
    ### greatly aid the performance of this project
    ###
    # start searching at the start
    interval_start = search_window.start
    interval_end = interval_start + search_window.duration

    damage_collection = []
    # print('\t\tStarting search in window from {} to {}'.format(search_window.start, search_window.end))

    while interval_start < search_window.end:
        # print('\t\t\tSearching at {}...'.format(interval_start))
        (_, total_damage, _) = calculate_total_damage(damage_report, interval_start, interval_end, actors)
        
        # add all values to the collection at this timestamp
        current_damage = total_damage
        current_damage['timestamp'] = interval_start
        damage_collection.append(current_damage)

        interval_start += search_window.step
        interval_end = interval_start + search_window.duration
        # print('\t\t\tDone.')

    damage_df = pd.DataFrame(damage_collection)
    damage_df.set_index('timestamp', drop=True, inplace=True)
    # print('\t\tDone with full search.')
    return BurstDamageCollection(damage_df, search_window.duration)


def time_averaged_dps(damage_report, startTime, endTime, stepSize, timeRange):

    average_dps = []
    df = damage_report['combinedDamage']

    current_time = startTime
    min_time = max(current_time - timeRange, startTime)
    max_time = min(current_time + timeRange, endTime)

    # sum up all 
    while current_time < endTime:
        delta = (max_time - min_time)/1000

        active_events = df.query('timestamp <= {} and timestamp >= {}'.format(max_time, min_time))
        step_damage = active_events['amount'].sum()

        average_dps.append({
            'timestamp': current_time,
            'dps': step_damage/delta,
        })

        current_time += stepSize
        min_time = max(current_time - timeRange, startTime)
        max_time = min(current_time + timeRange, endTime)

    return pd.DataFrame(average_dps)