from cardcalc_data import Player, Pet, SearchWindow, FightInfo, BurstDamageCollection, ActorList

import pandas as pd

"""
This takes a collection of damage events associated with ticks as well as the 
"""
def calc_snapshot_damage(damage_events):
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
    damage_report = pd.DataFrame(summed_tick_damage + damage_events['rawDamage'], columns=['timestamp', 'type', 'sourceID', 'targetID', 'abilityGameID', 'amount'])
    damage_report.sort_values(by='timestamp', inplace=True, ignore_index=True)
    return damage_report

def calc_tick_damage(damage_events):
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

    damage_report = pd.DataFrame(sorted(sorted_tick_damage + damage_events['rawDamage'], key=lambda tick: tick['timestamp']), columns=['timestamp', 'type', 'sourceID', 'targetID', 'abilityGameID', 'amount'])

    return damage_report

def compute_remove_card_damage(damage_report,
                               cards, 
                               actors: ActorList):
    for card in cards:
        # check the real bonus received
        eff_bonus = 1.0

        if card.target in actors.players:
            if card.role == actors.players[card.target].role:
                eff_bonus = card.bonus
            else:
                eff_bonus = 1.0 + ((card.bonus - 1.0)/2.0)
        elif card.target in actors.pets:
            if card.role == actors.players[actors.pets[card.target].owner].role:
                eff_bonus = card.bonus
            else:
                eff_bonus = 1.0 + ((card.bonus - 1.0)/2.0)

        # check if there are any valid damage values for the active card holder during it's time window (this should be non-empty but especially for pets may sometimes not be)
        if damage_report.loc[lambda df: (df['timestamp'] > card.start) & (df['timestamp'] < card.end) & (df['sourceID'] == card.target), 'amount'].empty:
            next
        else:
            # modifiy all values with the correct sourceID that lie between the start event and end event times for the card
            damage_report.loc[lambda df: (df['timestamp'] > card.start) & (df['timestamp'] < card.end) & (df['sourceID'] == card.target), 'amount'] = damage_report.loc[lambda df: (df['timestamp'] > card.start) & (df['timestamp'] < card.end) & (df['sourceID'] == card.target), 'amount'].transform(lambda x: int(x/eff_bonus))

    return damage_report

def compute_total_damage(damage_report, 
                         start_time: int, 
                         end_time: int, 
                         actors: ActorList):
    combined_damage = {}

    # create a dataframe with only the current time window
    current_df = damage_report.loc[lambda df: (df['timestamp'] >= start_time) & (df['timestamp'] <= end_time)]

    for actor in current_df['sourceID'].unique():
        combined_damage[actor] = current_df.loc[lambda df: df['sourceID'] == actor, 'amount'].sum()

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
def search_burst_window(damage_report, 
                        search_window: SearchWindow, 
                        actors: ActorList):
    ###
    ### TODO: this function is likely the whole computational time
    ### of this project right now so any work to optimize this will
    ### greatly aid the performance of this project
    ###
    # start searching at the start
    interval_start = search_window.start
    interval_end = interval_start + search_window.duration

    damage_collection = []

    while interval_start < search_window.end:
        (_, total_damage, _) = compute_total_damage(damage_report, interval_start, interval_end, actors)
        
        # add all values to the collection at this timestamp
        current_damage = total_damage
        current_damage['timestamp'] = interval_start
        damage_collection.append(current_damage)

        interval_start += search_window.step
        interval_end = interval_start + search_window.duration

    damage_df = pd.DataFrame(damage_collection)
    damage_df.set_index('timestamp', drop=True, inplace=True)
    return BurstDamageCollection(damage_df, search_window.duration)


def compute_time_averaged_dps(damage_report, 
                              start_time: int, 
                              end_time: int, 
                              step_size: int, 
                              time_range: int):

    average_dps = []
    
    current_time = start_time
    min_time = max(current_time - time_range, start_time)
    max_time = min(current_time + time_range, end_time)

    # sum up all 
    while current_time < end_time:
        time_delta = (max_time - min_time)/1000

        active_events = damage_report.loc[lambda df: (df['timestamp'] <= max_time) & (df['timestamp'] >= min_time)]
        step_damage = active_events['amount'].sum()

        average_dps.append({
            'timestamp': current_time,
            'dps': step_damage/time_delta,
        })

        current_time += stepSize
        min_time = max(current_time - time_range, start_time)
        max_time = min(current_time + time_range, end_time)

    return pd.DataFrame(average_dps)