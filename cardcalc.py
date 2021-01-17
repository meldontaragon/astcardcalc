"""
Calculates the optimal AST Card Usage
"""

"""
I want to 
CURRENT GOAL: reach goal but could be interesting 
    to check if there was a better person/time to play
    the card in the window between draws
ADDTL REACH GOAL: create a timeline of damage snapshot in 
    the next X seconds (15s for card but could be useful 
    for other tools to have this variable)
"""

from datetime import timedelta
import os

# Make sure we have the requests library
try:
    import requests
except ImportError:
    raise ImportError("FFlogs parsing requires the Requests module for python."
                      "Run the following to install it:\n    python -m pip install requests")

class CardCalcException(Exception):
    pass

def fflogs_fetch(api_url, options):
    """
    Gets a url and handles any API errors
    """
    # for now hard card the api key
    options['api_key'] = os.environ['FFLOGS_API_KEY']
    options['translate'] = True

    response = requests.get(api_url, params=options)

    # Handle non-JSON response
    try:
        response_dict = response.json()
    except:
        raise CardCalcException('Could not parse response: ' + response.text)

    # Handle bad request
    if response.status_code != 200:
        if 'error' in response_dict:
            raise CardCalcException('FFLogs error: ' + response_dict['error'])
        else:
            raise CardCalcException('Unexpected FFLogs response code: ' + response.status_code)

    return response_dict

def fflogs_api(call, report, options={}):
    """
    Makes a call to the FFLogs API and returns a dictionary
    """
    if call not in ['fights', 'events/summary', 'tables/damage-done']:
        return {}

    api_url = 'https://www.fflogs.com:443/v1/report/{}/{}'.format(call, report)
    
    data = fflogs_fetch(api_url, options)

    # If this is a fight list, we're done already
    if call in ['fights', 'tables/damage-done']:
        return data

    # If this is events, there might be more. Fetch until we have all of it
    while 'nextPageTimestamp' in data:
        # Set the new start time
        options['start'] = data['nextPageTimestamp']

        # Get the extra data
        more_data = fflogs_fetch(api_url, options)

        # Add the new events to the existing data
        data['events'].extend(more_data['events'])

        # Continue the loop if there's more
        if 'nextPageTimestamp' in more_data:
            data['nextPageTimestamp'] = more_data['nextPageTimestamp']
        else:
            del data['nextPageTimestamp']
            break

    # Return the event data
    return data

"""
# Cards:
#
# Melee:
# Lord of Crowns    id#1001876
# The Balance       id#1001882
# The Arrow         id#1001884
# The Spear         id#1001885
#
# Ranged:
# Lady of Crowns    id#1001877
# The Bole          id#1001883
# The Ewer          id#1001886
# The Spire         id#1001887
"""
def card_to_string(card, start_time):
    return '{} played {} on {} at {}'.format(card['source'], card['name'], card['target'], str(timedelta(milliseconds=(card['start']-start_time)))[2:11])

def card_type(guid):
    return {
        1001876: 'melee',
        1001877: 'ranged',
        1001882: 'melee',
        1001884: 'melee',
        1001885: 'melee',
        1001883: 'ranged',
        1001886: 'ranged',
        1001887: 'ranged',
    } [guid]

def card_name(guid):
    return {
        1001876: 'Lord of Crowns',
        1001877: 'Lady of Crowns',
        1001882: 'The Balance',
        1001884: 'The Arrow',
        1001885: 'The Spear',
        1001883: 'The Bole',
        1001886: 'The Ewer',
        1001887: 'The Spire',
    } [guid]

def card_bonus(guid):
    return {
        1001876: 1.08,
        1001877: 1.08,
        1001882: 1.06,
        1001884: 1.06,
        1001885: 1.06,
        1001883: 1.06,
        1001886: 1.06,
        1001887: 1.06,
    } [guid]

def get_draws_divinations(report, start, end):
    """
    Gets a list of the card draw events
    """
    # x card drawn buffs
    #'filter': 'ability.id in (1000915, 1000913, 1000914, 1000917, 1000916, 1000918)',
    options = {
        'start': start,
        'end': end,
        'filter': 'ability.id in (3590, 7448, 3593, 16552, 1000915, 1000913, 1000914, 1000917, 1000916, 1000918)',
    }

    event_data = fflogs_api('events/summary', report, options)

    draws = []

    for event in event_data['events']:
        # if applybuff then create/modify event with the 
        # card drawn
        if event['type'] == 'applybuff':
            draw_set = [draw 
                    for draw in draws 
                    if draw['source'] == event['sourceID'] 
                    and draw['time'] == event['timestamp'] 
                    and 'card' not in draw]
            if draw_set:
                draw = draw_set[0]
                draw['card'] = event['ability']['name']
                draw['id'] = event['ability']['guid']
            else:
                draws.append({
                    'source': event['sourceID'],
                    'time': event['timestamp'],
                    'card': event['ability']['name'],
                    'id': event['ability']['guid'],
                })
        # if cast then create/modify even with the draw type
        # from (draw, redraw, sleevedraw)
        elif event['type'] == 'cast' and event['ability']['name'] != 'Divination':
            draw_set = [draw 
                    for draw in draws 
                    if draw['source'] == event['sourceID'] 
                    and draw['time'] == event['timestamp'] 
                    and 'type' not in draw]
            if draw_set:
                draw = draw_set[0]
                draw['type'] = event['ability']['name']
            else:
                draws.append({
                    'source': event['sourceID'],
                    'time': event['timestamp'],
                    'type': event['ability']['name'],
                })

    divinations = []
    for event in event_data:
        if event['ability']['name'] == 'Divination':
            divinations.append({
                'source': event['sourceID'],
                'time': event['timestamp'],
                'type': event['ability']['name'],
            })            

    return (draws, divinations)

def get_cards_played(report, start, end):
    """
    Gets a list of cards played
    """
    options = {
        'start': start,
        'end': end,
        'filter': 'ability.id in (1001877, 1001883, 1001886, 1001887, 1001876, 1001882, 1001884, 1001885)'
    }

    # print('API Call: https://www.fflogs.com:443/v1/report/{}/{}'.format('events/summary',report))
    # print('Start: {}'.format(options['start']))
    # print('End: {}'.format(options['end']))
    # print('Filter: {}'.format(options['filter']))
    
    event_data = fflogs_api('events/summary', report, options)

    cards = []

    # Build list from events
    for event in event_data['events']:
        # If applying the buff, add an item to the tethers
        if event['type'] == 'applybuff':
            cards.append({
                'source': event['sourceID'],
                'target': event['targetID'],
                'start': event['timestamp'],
                'type': card_type(event['ability']['guid']),
                'name': card_name(event['ability']['guid']),
                'bonus': card_bonus(event['ability']['guid']),                
                'id': event['ability']['guid'],                
            })
        # If removing the buff, add an end timestamp to the matching application
        elif event['type'] == 'removebuff':
            card_set = [card
                      for card in cards
                      if card['target'] == event['targetID'] and card['source'] == event['sourceID'] and card['id'] == event['ability']['guid'] and 'end' not in card]
            # add it to the discovered tether
            if card_set:
                card = card_set[0]
                card['end'] = event['timestamp']
            # if there is no start event, add one and set it to 15s prior
            else:
                cards.append({
                    'source': event['sourceID'],
                    'target': event['targetID'],
                    'start': max(event['timestamp'] - 15000, start),
                    'end': event['timestamp'],
                    'type': card_type(event['ability']['guid']),
                    'name': card_name(event['ability']['guid']),
                    'bonus': card_bonus(event['ability']['guid']),                
                    'id': event['ability']['guid'],                
                })
    for card in cards:
        if 'end' not in card:
            # print('Card is missing end')
            card['end'] = min(card['start'] + 15000, end)

    return cards

def get_damages(report, start, end):
    """
    Gets non-tick, non-pet damage caused between start and end
    """
    options = {
        'start': start,
        'end': end,
        'filter': 'isTick="false"'
    }

    damage_data = fflogs_api('tables/damage-done', report, options)

    damages = {}

    for damage in damage_data['entries']:
        damages[damage['id']] = damage['total']

    return damages

def get_tick_damages(report, version, start, end):
    """
    Gets the damage each player caused between start and 
    end from tick damage that was snapshotted in the 
    start-end window
    """
    # Set up initial options to count ticks
    options = {
        'start': start,
        'end': end + 60000, # 60s is the longest dot
        'filter': """
            ability.id not in (1000493, 1000819, 1000820, 1001203, 1000821, 1000140, 1001195, 1001291, 1001221)
            and (
                (
                    type="applydebuff" or type="refreshdebuff" or type="removedebuff"
                ) or (
                    isTick="true" and
                    type="damage" and
                    target.disposition="enemy" and
                    ability.name!="Combined DoTs"
                ) or (
                    (
                        type="applybuff" or type="refreshbuff" or type="removebuff"
                    ) and (
                        ability.id=1000190 or ability.id=1000749 or ability.id=1000501 or ability.id=1001205
                    )
                ) or (
                    type="damage" and ability.id=799
                )
            )
        """
        # Filter explanation:
        # 1. exclude non-dot debuff events like foe req that spam event log to minimize requests
        # 2. include debuff events
        # 3. include individual dot ticks on enemy
        # 4. include only buffs corresponding to ground effect dots
        # 5. include radiant shield damage
    }

    tick_data = fflogs_api('events/summary', report, options)

    # Active debuff window. These will be the debuffs whose damage will count, because they
    # were applied within the tether window. List of tuples (sourceID, abilityID)
    active_debuffs = []

    # These will be how much tick damage was applied by a source, only counting
    # debuffs applied during the window
    tick_damage = {}

    # Wildfire instances. These get special handling afterwards, for stormblood logs
    wildfires = {}

    for event in tick_data['events']:
        # Fix rare issue where full source is reported instead of just sourceID
        if 'sourceID' not in event and 'source' in event and 'id' in event['source']:
            event['sourceID'] = event['source']['id']

        action = (event['sourceID'], event['ability']['guid'])

        # Record wildfires but skip processing for now. Only for stormblood logs
        if event['ability']['guid'] == 1000861 and version < 20:
            if event['sourceID'] in wildfires:
                wildfire = wildfires[event['sourceID']]
            else:
                wildfire = {}

            if event['type'] == 'applydebuff':
                if 'start' not in wildfire:
                    wildfire['start'] = event['timestamp']
            elif event['type'] == 'removedebuff':
                if 'end' not in wildfire:
                    # Effective WF duration is 9.25
                    wildfire['end'] = event['timestamp'] - 750
            elif event['type'] == 'damage':
                if 'damage' not in wildfire:
                    wildfire['damage'] = event['amount']

            wildfire['target'] = event['targetID']

            wildfires[event['sourceID']] = wildfire
            continue

        # Debuff applications inside window
        if event['type'] in ['applydebuff', 'refreshdebuff', 'applybuff', 'refreshbuff'] and event['timestamp'] < end:
            # Add to active if not present
            if action not in active_debuffs:
                active_debuffs.append(action)

        # Debuff applications outside window
        elif event['type'] in ['applydebuff', 'refreshdebuff', 'applybuff', 'refreshbuff'] and event['timestamp'] > end:
            # Remove from active if present
            if action in active_debuffs:
                active_debuffs.remove(action)

        # Debuff fades don't have to be removed. Wildfire (ShB) will 
        # occasionally log its tick damage after the fade event, so faded 
        # debuffs that deal damage should still be included as implicitly 
        # belonging to the last application

        # Damage tick
        elif event['type'] == 'damage':
            # If this is radiant shield, add to the supportID
            if action[1] == 799 and event['timestamp'] < end:
                if event['supportID'] in tick_damage:
                    tick_damage[event['supportID']] += event['amount']
                else:
                    tick_damage[event['supportID']] = event['amount']

            # Add damage only if it's from a snapshotted debuff
            elif action in active_debuffs:
                if event['sourceID'] in tick_damage:
                    tick_damage[event['sourceID']] += event['amount']
                else:
                    tick_damage[event['sourceID']] = event['amount']

    # Wildfire handling. This part is hard
    # There will be no wildfires for shadowbringers logs, since they are handled
    # as a normal DoT tick.
    for source, wildfire in wildfires.items():
        # If wildfire never went off, set to 0 damage
        if 'damage' not in wildfire:
            wildfire['damage'] = 0

        # If entirely within the window, just add the real value
        if ('start' in wildfire and
                'end' in wildfire and
                wildfire['start'] > start and
                wildfire['end'] < end):
            if source in tick_damage:
                tick_damage[source] += wildfire['damage']
            else:
                tick_damage[source] = wildfire['damage']

        # If it started after the window, ignore it
        elif 'start' in wildfire and wildfire['start'] > end:
            pass

        # If it's only partially in the window, calculate how much damage tether would've affected
        # Shoutout to [Odin] Lynn Nuvestrahl for explaining wildfire mechanics to me
        elif 'end' in wildfire:
            # If wildfire started before dragon sight, the start will be tether start
            if 'start' not in wildfire:
                wildfire['start'] = start
            # If wildfire ended after dragon sight, the end will be tether end
            if wildfire['end'] > end:
                wildfire['end'] = end

            # Set up query for applicable mch damage
            options['start'] = wildfire['start']
            options['end'] = wildfire['end']

            # Only damage on the WF target by the player, not the turret
            options['filter'] = 'source.type!="pet"'
            options['filter'] += ' and source.id=' + str(source)
            options['filter'] += ' and target.id=' + str(wildfire['target'])

            wildfire_data = fflogs_api('tables/damage-done', report, options)

            # If there's 0 damage there won't be any entries
            if not len(wildfire_data['entries']):
                pass

            # Filter is strict enough that we can just use the number directly
            elif source in tick_damage:
                tick_damage[source] += int(0.25 * wildfire_data['entries'][0]['total'])
            else:
                tick_damage[source] = int(0.25 * wildfire_data['entries'][0]['total'])

    return tick_damage

def get_real_damages(damages, tick_damages, pets):
    """
    Combines the two arguments, since cards work with pet damage
    this also needs to add in the tick damage from pets
    """
    real_damages = {}
    for source in damages.keys():
        if source in tick_damages:
            real_damages[source] = damages[source] + tick_damages[source]
        else:
            real_damages[source] = damages[source]

    # search through pets for those owned by anyone in the damage 
    # sources (this isn't elegant but it works for now)
    for pet in pets:
        if pets[pet]['petOwner'] in damages.keys() and pet in tick_damages:
            real_damages[pets[pet]['petOwner']] += tick_damages[pet]

    return real_damages

def get_blocked_damage_totals(report, start, end, interval=1, duration=15):
    """
    Okay, here's the really complicated and slow process

    I want to go from the start of the fight to the end of the fight in some interval size (default: 1) and check how much damage would be snapshot for a buff of a given duration (default: 15) if played at the start of that interval

    Then combine all of these values for each actor so this information can be parsed/plotted/etc (I don't know, this is gonna be a massive amount of data parsing and ultimately I can't afford to actually make this many API requests so I'm gonna need to grab the whole fight at once and slowly parse it?????)
    """

def print_results(results, friends, encounter_info):
    """
    Prints the results of the tether calculations
    """

    tabular = '{:<22}{:<13}{:>9}{:>12}   {:<8}{:<9}{:>7}'
    # {:>10}'
    for result in results:
        print("{} played {} on {} at {} (Duration: {:>4}s)".format(
            friends[result['source']]['name'],
            result['card'],
            friends[result['target']]['name'],
            result['timing'],
            str(round(result['duration'],1))
            ))

        # Get the correct target
        # correct = ''
        # if result['damages'][0]['id'] == result['source']:
        #     correct = friends[result['damages'][1]['id']]['name']
        # else:
        #     correct = friends[result['damages'][0]['id']]['name']

        print("The correct target was {}".format(result['correct']))

        # Print table
        print(tabular.format("Player", "Job", "Damage", "Raw Damage",  "JobType", "Has Card", "Bonus"))
        # , "rDPS Gain"))
        print("-" * 80)
        for damage in result['damages']:
            # Ignore limits
            # if friends[damage['id']]['type'] == 'LimitBreak':
            #     continue

            print(tabular.format(
                friends[damage['id']]['name'],
                friends[damage['id']]['type'],
                damage['damage'],
                damage['rawdamage'],
                damage['jobtype'],
                damage['prevcard'],
                int(damage['bonus']),
            ))
        print()

def job_type(job_name):
    if job_name in {'DarkKnight', 'Gunbreaker', 'Warrior','Paladin',
    'Dragoon', 'Samurai', 'Ninja', 'Monk'}:
        return 'melee'
    if job_name in {'Machinist', 'Dancer', 'Bard', 'WhiteMage', 'Scholar', 'Astrologian', 'Summoner', 'BlackMage', 'RedMage'}:
        return 'ranged'
    return 'n/a'

def cardcalc(report, fight_id):
    """
    Reads an FFLogs report and solves for optimal Card Usage
    """

    report_data = fflogs_api('fights', report)

    version = report_data['logVersion']

    fight = [fight for fight in report_data['fights'] if fight['id'] == fight_id][0]

    if not fight:
        raise CardCalcException("Fight ID not found in report")

    encounter_start = fight['start_time']
    encounter_end = fight['end_time']

    encounter_timing = timedelta(milliseconds=fight['end_time']-fight['start_time'])

    encounter_info = {
        'enc_name': fight['name'],
        'enc_time': str(encounter_timing)[2:11],
        'enc_kill': fight['kill'] if 'kill' in fight else False,
        # 'enc_dur': int(encounter_timing.total_seconds()),
    }

    friends = {friend['id']: friend for friend in report_data['friendlies']}
    pets = {pet['id']: pet for pet in report_data['friendlyPets']}

    # Build the list of tether timings
    cards = get_cards_played(report, encounter_start, encounter_end)

    if not cards:
        raise CardCalcException("No cards played in fight")

    results = []

    # remove cards given to pets since the owner damage includes that
    for card in cards:
        if card['target'] in pets:
            # print('Removed pet with ID: {}'.format(card['target']))
            cards.remove(card)

    for card in cards:
        # Easy part: non-dot damage done in window
        damages = get_damages(report, card['start'], card['end'])

        # Hard part: snapshotted dot ticks, including wildfire for logVersion <20
        tick_damages = get_tick_damages(report, version, card['start'], card['end'])

        # Pet Tick damage needs to be added to the owner tick damage
        # TODO: I think there's a better way to handle this but this
        # works for now
        # for tick in tick_damages:
        #     if tick in pets:
        #         if pets[tick]['petOwner'] in tick_damages:
        #             tick_damages[pets[tick]['petOwner']] += tick_damages[tick]
        #         else:
        #             tick_damages[pets[tick]['petOwner']] = tick_damages[tick]

        # Combine the two
        real_damages = get_real_damages(damages, tick_damages, pets)

        # check the type of card and the type of person who received it
        mult = 0
        correct_type = False

        if not (card['target'] in friends):
            # print('Another pet found, ID: {}'.format(card['target']))
            cards.remove(card)
            continue

        if job_type(friends[card['target']]['type']) == card['type']:
            mult = card['bonus']
            correct_type = True
        else:
            mult = 1 + ((mult-1.0)/2.0)
            correct_type = False

        # Correct damage by removing card bonus from player with card
        if card['target'] in real_damages:
            real_damages[card['target']] = int(real_damages[card['target']] / mult)

        damage_list = sorted(real_damages.items(), key=lambda dmg: dmg[1], reverse=True)

        # correct possible damage from jobs with incorrect 
        # type by dividing their 'available' damage in half
        # 
        # also checks if anyone in the list already has a card
        # and makes a note of it (the damage bonus from that card
        # can't be properly negated but this allows the user to 
        # ignore that individual or at least swap the card usages
        # if the damage difference is large enough between the two 
        # windows)
        corrected_damage = []
        
        active_cards = [prev_card for prev_card in cards 
                            if prev_card['start'] < card['start'] 
                            and prev_card['end'] > card['start']]

        for damage in damage_list:
            mod_dmg = 0
            
            has_card = 'No'
            for prev_card in active_cards:
                if prev_card['start'] < card['start'] and prev_card['end'] > card['start'] and prev_card['target'] == damage[0]:
                    has_card = 'Yes'

            if card['type'] == job_type(friends[damage[0]]['type']):
                mod_dmg = damage[1]
            else:
                mod_dmg = int(damage[1]/2.0)
            corrected_damage.append({
            'id': damage[0],
            'damage': mod_dmg,
            'rawdamage': damage[1],
            'jobtype': job_type(friends[damage[0]]['type']),
            'bonus': int(mod_dmg * (card['bonus'] - 1)),
            'prevcard': has_card,
            })

        corrected_damage_list = sorted(corrected_damage, key=lambda dmg: dmg['damage'], reverse=True)

        # Add to results
        timing = timedelta(milliseconds=card['start']-encounter_start)

        # Determine the correct target, the top non-self non-limit combatant
        for top in corrected_damage_list:
            if friends[top['id']]['type'] != 'LimitBreak' and friends[top['id']]['type'] != 'Limit Break' and top['prevcard'] == 'No':
                correct = friends[top['id']]['name']
                break

        if not correct:
            correct = 'Nobody?'
        
        results.append({
            'damages': corrected_damage_list,
            'timing': str(timing)[2:11],
            'duration': timedelta(milliseconds=card['end']-card['start']).total_seconds(),
            'source': card['source'],
            'target': card['target'],
            'card': card['name'],
            'cardtype': card['type'],
            'correct': correct,
            'correctType': correct_type,        
        })
        

    # results['duration'] = encounter_info['enc_dur']
    return results, friends, encounter_info, cards

def get_last_fight_id(report):
    """Get the last fight in the report"""
    report_data = fflogs_api('fights', report)

    return report_data['fights'][-1]['id']

def get_friends_and_pets(report, fight_id):
    """
    Reads an FFLogs report and solves for optimal Card Usage
    """

    report_data = fflogs_api('fights', report)

    version = report_data['logVersion']

    fight = [fight for fight in report_data['fights'] if fight['id'] == fight_id][0]

    if not fight:
        raise CardCalcException("Fight ID not found in report")

    encounter_start = fight['start_time']
    encounter_end = fight['end_time']

    encounter_timing = timedelta(milliseconds=fight['end_time']-fight['start_time'])

    encounter_info = {
        'enc_name': fight['name'],
        'enc_time': str(encounter_timing)[2:11],
        'enc_kill': fight['kill'] if 'kill' in fight else False,
        # 'enc_dur': int(encounter_timing.total_seconds()),
    }

    friends = {friend['id']: friend for friend in report_data['friendlies']}
    pets = {pet['id']: pet for pet in report_data['friendlyPets']}

    return (friends, pets)