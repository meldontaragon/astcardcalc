from cardcalc_data import Player, Pet, SearchWindow, FightInfo, BurstDamageCollection, ActorList

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

    damage_report = {
        'rawDamage': damage_events['rawDamage'],
        'snapshotDamage': sorted_tick_damage,
        'combinedDamage': sorted(sorted_tick_damage + damage_events['rawDamage'], key=lambda tick: tick['timestamp'])
    }
    
    return damage_report

def calculate_total_damage(damage_report, start_time, end_time, actors: ActorList):
    combined_damage = {}

    # add all raw damage events
    for event in damage_report['combinedDamage']:
        if event['timestamp'] > start_time and event['timestamp'] < end_time:
            if event['sourceID'] in combined_damage:
                combined_damage[event['sourceID']] += event['amount']
            else:
                combined_damage[event['sourceID']] = event['amount']                
        # assume order events and if the current event is after 
        # the end time then we're done
        if event['timestamp'] > end_time:
            break

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
    # start searching at the start
    interval_start = search_window.start
    interval_end = interval_start + search_window.duration

    damage_collection = {}

    while interval_start < search_window.end:
        (total_damage, _, _) = calculate_total_damage(damage_report, interval_start, interval_end, actors)
        
        # sorted_damage = sorted(total_damage.items(), key=lambda dmg: dmg[1])
        
        # add all values to the collection at this timestamp
        damage_collection[interval_start] = {}
        for ind in total_damage:
            damage_collection[interval_start][ind] = total_damage[ind]

        interval_start += search_window.step
        interval_end = interval_start + search_window.duration
    
    return BurstDamageCollection(damage_collection, search_window.duration)