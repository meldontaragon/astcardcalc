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
import pandas as pd

from cardcalc_data import Player, Pet, CardPlay, BurstWindow, DrawWindow, FightInfo, BurstDamageCollection, CardCalcException, ActorList, SearchWindow

from fflogsapi import get_card_draw_events, get_card_play_events, get_actor_lists, get_fight_info, get_damage_events

from damagecalc import calculate_tick_snapshot_damage, calculate_total_damage, search_burst_window

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
    last_event = DrawWindow.GetName(0)
    current_source = 0
    draw_windows = []

    for event in card_events:
        # check if cast and if it's draw/sleeve/div
        if event['type'] == 'cast' and event['abilityGameID'] in [3590, 16552, 7448]:
            current_source = event['sourceID']
            draw_windows.append(DrawWindow(current_source, last_time, event['timestamp'], last_event, DrawWindow.GetName(event['abilityGameID'])))

            last_time = event['timestamp']
            last_event = DrawWindow.GetName(event['abilityGameID'])
    
    draw_windows.append(DrawWindow(current_source, last_time, end_time, last_event, DrawWindow.GetName(-1)))

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

"""
TODO: this might just need to rewritten mostly from scratch because of all the 
changes I've made to the backend it's interacting with
"""

def cardcalc(report, fight_id, token):
    """
    Reads an FFLogs report and solves for optimal Card Usage
    """
    # get fight info
    fight_info = get_fight_info(report, fight_id, token)
    
    # get actors
    actors = get_actor_lists(fight_info, token)

    # Build the list of card plays and draw windows
    cards = get_card_play_events(fight_info, token)
    draws = get_card_draw_events(fight_info, token)
    
    # Get all damage event and then sort out tick event into snapshot damage events
    damage_events = get_damage_events(fight_info, token)
    damage_report = calculate_tick_snapshot_damage(damage_events)

    if not cards:
        raise CardCalcException("No cards played in fight")
    if not draws:
        raise CardCalcException("No draw events in fight")

    # remove cards given to pets since the owner's card will account for that
    for card in cards:
        if card['target'] in actors.pets:
            cards.remove(card)

    # go through each draw windows and calculate the following
    # (1.) Find the card played during this window and get the damage dealt by
    #      each player during that play window
    # (2.) Loop through possible play windows form the start of the draw window
    #      to the end in 1s increments and calculate damage done
    # (3.) Return the following:
    #      (a) table of players/damage done in play window
    #      (b) table of top damage windows
    #          i. include top 3/5/8/10 for draw window lasting at least
    #             0/4/10/20 seconds
    #          ii. don't include the same player twice in the same 4s interval
    #      (c) start/end time of draw window
    #      (d) start/end events of draw window
    #      (e) card play time (if present)
    #      (f) source/target
    #      (g) correct target in play window
    #      (h) card played

    cardcalc_data = []

    for draw in draws:
        # find if there was a card played in this window
        card = None
        for c in cards:
            if c.start > draw.start and c.start < draw.end:
                card = c
                break
        
        # only handle the play window if there was a card played
        card_play_data = {}
        if card is not None:
            # compute damage done during card play window
            (damages, _, _) = calculate_total_damage(damage_report, card.start, card.end, actors)

            # check what multiplier should be used to remove the damage bonus
            mult = 0
            if Player.GetRole(actors.players[card.target].type) == card.role:
                mult = card.bonus
            else:
                mult = 1 + ((card.bonus-1.0)/2.0)

            # Correct damage by removing card bonus from player with card
            if card.target in damages:
                damages[card.target] = int(damages[card.target] / mult)

            # now adjust the damage for incorrect roles 
            corrected_damage = []
            active_cards = [prev_card for prev_card in cards 
                                if prev_card.start < card.start
                                and prev_card.end > card.start]

            for pid, dmg in damages.items():
                mod_dmg = dmg
                has_card = 'No'
                for prev_card in active_cards:
                    if prev_card.start < card.start and prev_card.end > card.start and prev_card.target == pid:
                        has_card = 'Yes'

                if card.type != actors.players[pid].role:
                    mod_dmg = int(dmg/2)
                
                corrected_damage.append({
                    'id': pid,
                    'hasCard': has_card,
                    'realDamage': dmg,
                    'adjustedDamage': mod_dmg,
                    'role': actors.players[pid].role,
                    'job': actors.players[pid].job,
                })

            # convert to dataframe
            damage_table = pd.DataFrame(corrected_damage, index='id')
            # get the highest damage target that isn't LimitBreak
            optimal_target = damage_table[damage_table['role'] != 'LimitBreak']['adjustedDamage'].idxmax()

            if optimal_target is None:
                optimal_target = 'Nobody?'
            else:
                optimal_target = actors.players[optimal_target].name

            correct = False
            if optimal_target == actors.players[card.target].name:
                correct = True

            card_play_data = {
                'cardPlayTime': card.start,
                'cardTiming': str(timedelta(milliseconds=card.start-fight_info.start))[2:11],
                'cardDuration': timedelta(milliseconds=card.end-card.start).total_seconds(),                
                'cardPlayed': card.name,
                'cardSource': card.source,
                'cardTarget': card.target,
                'cardDamageTable': damage_table,
                'cardOptimalTarget': optimal_target,
                'cardCorrect': correct,
            }
        else:
            card_play_data = {
                'cardPlayTime': 0,
                'cardTiming': 'N/A',
                'cardDuration': 0,
                'cardPlayed': 'None',
                'cardSource': 0,
                'cardTarget': 0,
                'cardDamageTable': None,
                'cardOptimalTarget': 0,
                'cardCorrect': False,
            }
        
        # now we can begin compiling data for the draw window as a whole
        card_draw_data = {}

        # creates a search window from the start of the draw window to the end
        # with a 15s duration and 1s step size
        search_window = SearchWindow(draw.start, draw.end, 15000, 1000)
        draw_window_damage_collection = search_burst_window(damage_report, search_window, actors)

        draw_window_duration = timedelta(milliseconds=(draw.end-draw.start)).total_seconds()

        draw_damage_table = []

        data_count = 0
        if draw_window_duration < 4.0:
            data_count = 3
        elif draw_window_duration < 10.0:
            data_count = 5
        elif draw_window_duration < 20.0:
            data_count = 8
        else:
            data_count = 10

        (timestamp, pid, damage) = draw_window_damage_collection.GetMax()
        collected_count = 1
        draw_damage_table.append({
            'count': collected_count,
            'id': pid,
            'damage': damage,
            'time': timestamp,
        })

        optimal_time = timestamp
        optimal_target = actors.players[pid].name
        optimal_damage = damage
        optimal_timing = str(timedelta(milliseconds=(timestamp - fight_info.start)))[2:11]
        
        current_damage = damage
        while (collected_count < data_count and current_damage > draw_window_damage_collection.df.min(axis=0).min()):
            # get the next lowest damage instance
            (time_new, pid_new, damage_new) = draw_window_damage_collection.GetMax(limit=current_damage)

            # update the max damage value we've looked up
            current_damage = damage_new

            # if it's the same player in a window that's already 
            # recorded skip it
            ignore_entry = False
            for table_entry in draw_damage_table:
                if pid_new == table_entry['id'] and abs(time_new - table_entry['time']) < 4:
                    ignore_entry = True
                
            if ignore_entry:
                continue

            # if the max damage is 0 then we're done and can exit
            if damage_new == 0:
                break

            # otherwise we should add the entry to the table
            collected_count += 1
            draw_damage_table.append({
                'count': collected_count,
                'id': pid_new,
                'damage': damage_new,
                'time': time_new,
            })

        card_draw_data = {
            'startTime': draw.start,
            'endTime': draw.end,
            'startEvent': draw.startEvent,
            'endEvent': draw.endEvent,
            'drawDamageTable': pd.DataFrame(draw_damage_table),
            'drawOptimalTime': optimal_time,
            'drawOptimalTarget': optimal_target,
            'drawOptimalTiming': optimal_timing,
            'drawOptimalDamage': optimal_damage,
        }

        # finally combine the two sets of data and append it to the collection
        # of data for each draw window/card play
        combined_data = card_draw_data | card_play_data
        cardcalc_data.append(combined_data)

    return cardcalc_data, actors
