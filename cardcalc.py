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

from cardcalc_data import Player, Pet, CardPlay, BurstWindow, DrawWindow, FightInfo, BurstDamageCollection

from fflogsapi import 

class CardCalcException(Exception):
    pass

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
    last_event = DrawWindow.Name(0)
    draw_windows = []

    for events in card_events:
        # check if cast and if it's draw/sleeve/div
        if event['type'] == 'cast' and event['abilityGameID'] in [3590, 16552, 7448]:
            draw_windows.append(DrawWindow(last_time, event['timestamp'], last_event, DrawWindow.Name(event['abilityGameID'])))

            last_time = event['timestamp']
            last_event = DrawWindow.Name(event['abilityGameID'])
    
    draw_windows.append(DrawWindow(last_time, end_time, last_event, DrawWindow.Name(-1)))

    return draw_windows

def get_cards_played(card_events, start_time, end_time):
    cards = []

    # Build list from events
    for event in card_events:
        # If applying the buff, add an item to the list of
        # cards played
        if event['type'] == 'applybuff':
            cards.append(CardPlay(event['timestamp'], None, event['sourceID'], event['targetID'], event['abilityGameID']))
        # If removing the buff, add an end timestamp to the matching application
        elif event['type'] == 'removebuff':
            card_set = [card
                      for card in cards
                      if card.target == event['targetID'] and card.source == event['sourceID'] and card.id == event['abilityGameID'] and card.end is None]
            # add it to the discovered tether
            if card_set:
                card = card_set[0]
                card.end = event['timestamp']
            # if there is no start event, add one and set it to 15s prior
            else:
                cards.append(CardPlay(max(event['timestamp'] - 15000, start_time), event['timestamp'], event['sourceID'], event['targetID'], event['abilityGameID']))
    for card in cards:
        if card.end is None:
            card.end = min(card['start'] + 15000, end_time)

    return cards

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