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

from cardcalc_fflogsapi import get_card_draw_events, get_card_play_events, get_actor_lists, get_fight_info, get_damage_events

from cardcalc_damage import calc_snapshot_damage, compute_total_damage, search_burst_window, compute_remove_card_damage

"""
For the initial version of this the following simple rules are use.
Every event starts with one of the following and ends with the same:
 (1) Draw
 (2) Sleeve Draw
 (3) Divination
Redraws and plays are ignored
"""
def _handle_draw_events(card_events, start_time, end_time):

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

def _handle_play_events(card_events, start_time, end_time):
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
            card.end = min(card.start + 15000, end_time)

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

# removes cards "played" on pets or non-player entities
def _clean_up_cards(cards, actors):
    new_cards = []
    for card in cards:
        if card.target in actors.players:
            new_cards.append(card)

    return new_cards

def _handle_card_play(card, cards, damage_report, actors, fight_info):
    if card is None:
        return {
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
    else:
        # compute damage done during card play window
        (_, damages, _) = compute_total_damage(damage_report, card.start, card.end, actors)
        
        # check what multiplier should be used to remove the damage bonus
        mult = 0
        if actors.players[card.target].role == card.role:
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

            if card.role != actors.players[pid].role:
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
        card_damage_table = pd.DataFrame(corrected_damage)
        card_damage_table.set_index('id', inplace=True, drop=False)
        card_damage_table.sort_values(by='adjustedDamage', ascending=False, inplace=True)

        # get the highest damage target that isn't LimitBreak
        optimal_target = card_damage_table[ (card_damage_table['role'] != 'LimitBreak') & (card_damage_table['hasCard'] == 'No')]['adjustedDamage'].idxmax()

        if optimal_target is None:
            optimal_target = 'Nobody?'
        else:
            optimal_target = actors.players[optimal_target].name

        correct = False
        if optimal_target == actors.players[card.target].name:
            correct = True

        return {
            'cardPlayTime': fight_info.ToString(time=card.start),
            'cardDuration': timedelta(milliseconds=card.end-card.start).total_seconds(),                
            'cardPlayed': card.name,
            'cardSource': card.source,
            'cardTarget': card.target,
            'cardDamageTable': card_damage_table.to_dict(orient='records'),
            'cardOptimalTarget': optimal_target,
            'cardCorrect': correct,
        }

def _get_active_card(cards, draw):
    for c in cards:
        # check if the card was played during the draw window
        if c.start > draw.start and c.start < draw.end:
            return c
    return None

def _handle_draw_play_damage(draw_window_damage_collection, draw_window_duration, fight_info):
    draw_damage = []

    data_count = 0
    collected_count = 0
    examined_count = 0

    if draw_window_duration < 4.0:
        data_count = 3
    elif draw_window_duration < 10.0:
        data_count = 5
    elif draw_window_duration < 20.0:
        data_count = 8
    else:
        data_count = 10

    sorted_damage_list = sorted(draw_window_damage_collection.df.unstack().to_dict().items(), key=lambda x: x[1], reverse=True)

    # I suspect this is one of the most inefficient pieces of the code
    # but it might lose out to the burst window search
    current_item = sorted_damage_list[examined_count]
    examined_count += 1
    (target_opt, time_opt, damage_opt) = (current_item[0][0], current_item[0][1], current_item[1])
    
    collected_count += 1
    draw_damage.append({
        'count': collected_count,
        'id': target_opt,
        'damage': damage_opt,
        'timestamp': time_opt,
        'time': fight_info.ToString(time=time_opt)[:5],
    })
    
    current_damage = damage_opt
    while collected_count < data_count and examined_count < len(sorted_damage_list):
        # get the next lowest damage instance
        current_item = sorted_damage_list[examined_count]
        examined_count += 1
        (target_new, time_new, damage_new) = (current_item[0][0], current_item[0][1], current_item[1])

        # update the max damage value we've looked up
        current_damage = damage_new

        # if it's the same player in a window that's already 
        # recorded skip it
        ignore_entry = False
        for table_entry in draw_damage:
            if target_new == table_entry['id'] and abs(time_new - table_entry['timestamp']) < 4000:
                ignore_entry = True
            
        if ignore_entry:
            continue

        # if the max damage is greater than 0 then add an entry:
        if damage_new > 0:
            collected_count += 1
            draw_damage.append({
                'count': collected_count,
                'id': target_new,
                'damage': damage_new,
                'timestamp': time_new,
                'time': fight_info.ToString(time=time_new)[:5],
            })

    draw_damage_table = pd.DataFrame(draw_damage)
    draw_damage_table.set_index('id', inplace=True, drop=False)
    draw_damage_table.sort_values(by='damage', inplace=True, ascending=False)

    return draw_damage_table, time_opt, target_opt, damage_opt

def cardcalc(report, fight_id, token):
    """
    Reads an FFLogs report and solves for optimal Card Usage
    """
    # get fight info
    fight_info = get_fight_info(report, fight_id, token)
    
    # get actors
    actors = get_actor_lists(fight_info, token)
    
    # Build the list of card plays and draw windows
    card_events = get_card_play_events(fight_info, token)
    draw_events = get_card_draw_events(fight_info, token)

    cards = _handle_play_events(card_events, fight_info.start, fight_info.end)
    draws = _handle_draw_events(draw_events, fight_info.start, fight_info.end)
    
    # Get all damage event and then sum tick events into snapshot damage events
    damage_events = get_damage_events(fight_info, token)
    damage_report = calc_snapshot_damage(damage_events)
    non_card_damage_report = compute_remove_card_damage(damage_report, cards, actors)

    if not cards:
        raise CardCalcException("No cards played in fight")
    if not draws:
        raise CardCalcException("No draw events in fight")

    # remove cards given to pets since the owner's card will account for that
    cards = _clean_up_cards(cards, actors)
            
    # go through each draw windows and calculate the following
    # (1.) Find the card played during this window and get the damage dealt by
    #      each player during that play window
    # (2.) Remove damage bonuses from any active cards during the current
    #      window
    # (3.) Loop through possible play windows form the start of the draw
    #      window
    #      to the end in 1s increments and calculate damage done
    # (4.) Return the following:
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
    count = 0
    for draw in draws:
        count += 1
        # find if there was a card played in this window
        card = _get_active_card(cards, draw)

        # only handle the play window if there was a card played
        card_play_data = _handle_card_play(card, cards, damage_report, actors, fight_info)
        
        # now we can begin compiling data for the draw window as a whole
        card_draw_data = {}

        # 15s search window corresponding to possible card plays 
        # during the draw window and then search it 
        search_window = SearchWindow(draw.start, draw.end, 15000, 1000)
        draw_window_damage_collection = search_burst_window(non_card_damage_report, search_window, actors)

        draw_window_duration = timedelta(milliseconds=(draw.end-draw.start)).total_seconds()

        draw_damage_table, time_opt, target_opt, damage_opt = _handle_draw_play_damage(draw_window_damage_collection, draw_window_duration, fight_info)

        card_draw_data = {
            'startTime': fight_info.ToString(time=draw.start),
            'endTime': fight_info.ToString(time=draw.end),
            'startEvent': draw.startEvent,
            'endEvent': draw.endEvent,
            'drawDamageTable': draw_damage_table.to_dict(orient='records'),
            'drawOptimalTime': fight_info.ToString(time=time_opt),
            'drawOptimalTarget': actors.players[target_opt].name,
            'drawOptimalDamage': damage_opt,
            'count': count,
        }

        # finally combine the two sets of data and append it to the collection
        # of data for each draw window/card play
        combined_data = card_draw_data | card_play_data
        cardcalc_data.append(combined_data)

    encounter_info = {
        'enc_name': fight_info.name,
        'enc_time': fight_info.ToString(),
        'enc_kill': fight_info.kill,
    }
    return cardcalc_data, actors.to_dict(), encounter_info