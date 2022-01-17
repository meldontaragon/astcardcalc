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

from cardcalc_data import Player, Pet, CardPlay, DrawWindow, FightInfo, BurstDamageCollection, CardCalcException, ActorList, SearchWindow

from cardcalc_fflogsapi import get_card_draw_events, get_card_play_events, get_actor_lists, get_fight_info, get_damage_events

from cardcalc_damage import calc_snapshot_damage, compute_total_damage, search_burst_window, compute_remove_card_damage, cleanup_hit_data, cleanup_prepare_events

"""
For the initial version of this the following simple rules are use.
Every event starts with one of the following and ends with the same:
 (1) Draw
Redraws and plays are ignored
"""
def _handle_draw_events(card_events, start_time, end_time):

    active_window = DrawWindow(start = start_time, castId = 0)
    draw_windows = []

    # each event is handled by checking if it's a buff or a cast, searching to check if the same timestamp is already in the list or the active window
    # if so then update that and continue
    # otherwise 

    for event in card_events:
        # check if cast and draw
        # print(" >>> event: {} id: {} timestamp: {} time: {}".format(event['type'], event['abilityGameID'], event['timestamp'], str(timedelta(milliseconds=(event['timestamp']-start_time)))[2:11]))
        if event['type'] == 'cast' and event['abilityGameID'] in [3590]:
            # if event is attached to active window then just update that information
            if active_window.start == event['timestamp']:
                active_window.castId = event['abilityGameID']
                active_window.startId = event['abilityGameID']
                active_window.startEvent = DrawWindow.GetName(active_window.startId)
            # otherwise close out the old active window and make a new one
            else:
                if active_window.startId == 0:
                    active_window.source = event['sourceID']
                active_window.end = event['timestamp']
                active_window.endId = event['abilityGameID']
                active_window.endEvent = DrawWindow.GetName(active_window.endId)
                # print("Closing CAST at {}".format(str(timedelta(milliseconds=(event['timestamp']-start_time)))[2:11]))
                draw_windows.append(active_window)
                active_window = DrawWindow(start = event['timestamp'], source = event['sourceID'], castId = event['abilityGameID'])

            # search for previously closed windows that end at this timestamp
            # and thus are missing a proper end cast
            end_set = [ draw
                        for draw in draw_windows
                        if draw.source == event['sourceID'] and draw.end == event['timestamp']]

            if end_set:
                draw_end = end_set[0]
                draw_end.endId = event['abilityGameID']
                draw_end.endEvent = DrawWindow.GetName(draw_end.endId)
                # print("Fixing endId and endEvent at {} - {}".format(str(timedelta(milliseconds=(draw_end.end-start_time)))[2:11], draw_end.endId))

            # search for previously handled buff windows without a cast
            draw_set = [ draw
                        for draw in draw_windows
                        if draw.source == event['sourceID'] and draw.start == event['timestamp'] and draw.castId == 0]
            # if one is found then update it
            if draw_set:
                draw = draw_set[0]
                draw.castId = event['abilityGameID']
                draw.startEvent = DrawWindow.GetName(draw.castId)
                
        # if buff then perform similar checks
        elif event['type'] == 'applybuff' and event['abilityGameID'] in [1000913, 1000914, 1000915, 1000916, 1000917, 1000918]:
            # if event is attached to active window then just update that information
            if active_window.start == event['timestamp']:
                active_window.buffId = event['abilityGameID']
                active_window.cardDrawn = DrawWindow.GetCard(active_window.buffId)

            # search for previously handled draw windows without an attached buff and update them
            draw_set = [draw
                        for draw in draw_windows
                        if draw.source == event['sourceID'] and draw.start == event['timestamp'] and draw.buffId == 0]
            # if one is found then update it
            if draw_set:
                draw = draw_set[0]
                draw.buffId = event['abilityGameID']
                draw.cardDrawn = DrawWindow.GetCard(draw.buffId)
    
    active_window.end = end_time
    active_window.endEvent = DrawWindow.GetName(-1)
    active_window.endId = -1
    draw_windows.append(active_window)

    for draw in draw_windows:
        if draw.endEvent is None:
            draw.endEvent = 'Unknown'
            draw.endId = -2

    return draw_windows

def _handle_play_events(card_events, start_time, end_time):
    cards = []

    # Build list from events
    for event in card_events:
        # if the event is the cast for a play then add to the list
        if event['type'] == 'cast':
            cards.append(CardPlay(cast = event['timestamp'], source = event['sourceID'], target = event['targetID'], castId = event['abilityGameID'], start = None, end = None))
        # If applying a buff then try and find a matching card play cast and add the new data to that, otherwise make a new item
        elif event['type'] == 'applybuff':
            # TODO: I could potentially check that the buff start is close to the cast event but that shouldn't actually be required
            card_set = [card 
                        for card in cards
                        if card.target == event['targetID'] and card.source == event['sourceID'] and card.buffId == event['abilityGameID']and card.start is None]
            if card_set:
                card = card_set[0]
                card.start = event['timestamp']
            else: 
                # if there is no associated cast event then use the buff time as the cast time
                cards.append(CardPlay(cast = event['timestamp'], start = event['timestamp'], end = None, source = event['sourceID'], target = event['targetID'], buffId = event['abilityGameID']))
        # If removing the buff, add an end timestamp to the matching application
        # TODO: need to check for overwritten cards to both warn about these and properly calculate the damage separately for what could have been covered by the full 15s window
        elif event['type'] == 'removebuff':
            card_set = [card
                      for card in cards
                      if card.target == event['targetID'] and card.source == event['sourceID'] and card.buffId == event['abilityGameID'] and card.end is None]
            # add it to the discovered card play
            if card_set:
                card = card_set[0]
                card.end = event['timestamp']
            # if there is no start event, add one and set it to 15s prior
            else:
                cards.append(CardPlay(cast = max(event['timestamp'] - 15000, start_time), start = max(event['timestamp'] - 15000, start_time), end = event['timestamp'], source = event['sourceID'], target = event['targetID'], buffId = event['abilityGameID']))
        # special case for refresh buff which is treated like both apply and remove at the same time
        elif event['type'] == 'refreshbuff':
            # TODO: need to cleanup div/sleeve handling here as it's obsolete
            # first clean up the sleeve/divend event 
            card_set = [card
                      for card in cards
                      if card.target == event['targetID'] and card.source == event['sourceID'] and card.buffId == event['abilityGameID'] and card.end is None]
            # add it to the discovered card play
            if card_set:
                card = card_set[0]
                card.end = event['timestamp']
            # if there is no start event, add one and set it to 15s prior
            else:
                cards.append(CardPlay(cast = max(event['timestamp'] - 15000, start_time), start = max(event['timestamp'] - 15000, start_time), end = event['timestamp'], source = event['sourceID'], target = event['targetID'], buffId = event['abilityGameID']))

            # now we can do the same for the buff window following the refresh
            card_set = [card 
                        for card in cards
                        if card.target == event['targetID'] and card.source == event['sourceID'] and card.buffId == event['abilityGameID']and card.start is None]
            if card_set:
                card = card_set[0]
                card.start = event['timestamp']
            else: 
                # if there is no associated cast event then use the buff time as the cast time
                cards.append(CardPlay(cast = event['timestamp'], start = event['timestamp'], end = None, source = event['sourceID'], target = event['targetID'], buffId = event['abilityGameID']))

    
    # this might be the wrong thing but for now I'm gonna toss cards with cast events but no buff events
    valid_cards = [card 
                    for card in cards
                    if card.start is not None]

    # this sets end time for cards to 15s after the buff starts or the end of fight if there was no end event found
    for card in valid_cards:
        if card.end is None:
            card.end = min(card.start + 15000, end_time)

    return valid_cards

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
        (_, damages, _, _, hit_details) = compute_total_damage(damage_report, card.start, card.end, actors, detailedInfo=True)
        
        hit_percent = {}
        # compute percentages
        for p in hit_details:
            # either no hit details or no damage done
            if p not in hit_details or p not in damages or damages[p] == 0:
                hit_percent[p] = {
                    'normalPercent': 0,
                    'dhPercent': 0,
                    'critPercent': 0,
                    'cdhPercent': 0,
                    'dotPercent': 0,
                }
            # all damage was from dots
            elif damages[p] == hit_details[p]['dot']:
                hit_percent[p] = {
                    'normalPercent': 0,
                    'dhPercent': 0,
                    'critPercent': 0,
                    'cdhPercent': 0,
                    'dotPercent': 100,
                }
            # otherwise compute non dot damage spread
            else:
                hit_percent[p] = {
                    'normalPercent': round(100*hit_details[p]['normal'] / (damages[p] - hit_details[p]['dot']), 1),
                    'dhPercent': round(100*hit_details[p]['dh'] / (damages[p] - hit_details[p]['dot']), 1),
                    'critPercent': round(100*hit_details[p]['crit'] / (damages[p] - hit_details[p]['dot']), 1),
                    'cdhPercent': round(100*hit_details[p]['cdh'] / (damages[p] - hit_details[p]['dot']), 1),
                    'dotPercent': round(100*hit_details[p]['dot'] / damages[p], 1),
                }

        # adjust the damage for incorrect roles 
        corrected_damage = []
        active_cards = [prev_card for prev_card in cards 
                            if prev_card.start < card.start
                            and prev_card.end > card.start]

        for pid, dmg in damages.items():
            mod_dmg = dmg
            has_card = False
            has_card_remaining = 0

            for prev_card in active_cards:
                if prev_card.start < card.start and prev_card.end > card.start and prev_card.target == pid:
                    has_card = True
                    # this doesn't check for early cutoffs that would occur from
                    # playing another card on someone before the first one ends
                    has_card_remaining = prev_card.end - card.start

            if card.role != actors.players[pid].role:
                mod_dmg = int(dmg/2)
            
            corrected_damage.append({
                'id': pid,
                'hasCard': has_card,
                'remaining': round(timedelta(milliseconds=has_card_remaining).total_seconds(),1),
                'realDamage': dmg,
                'adjustedDamage': mod_dmg,
                'role': actors.players[pid].role,
                'job': actors.players[pid].job,
            } | hit_percent[pid])

        # convert to dataframe
        card_damage_table = pd.DataFrame(corrected_damage)
        card_damage_table.set_index('id', inplace=True, drop=False)
        card_damage_table.sort_values(by='adjustedDamage', ascending=False, inplace=True)

        # get the highest damage target that isn't LimitBreak
        optimal_target = card_damage_table[ (card_damage_table['role'] != 'LimitBreak') & (card_damage_table['hasCard'] == False) ]['adjustedDamage'].idxmax()

        if optimal_target is None:
            optimal_target = 'Nobody?'
        else:
            optimal_target = actors.players[optimal_target].name

        correct = False
        if optimal_target == actors.players[card.target].name:
            correct = True

        return {
            'cardPlayTime': fight_info.ToString(time=card.start)[:5],
            'cardDuration': timedelta(milliseconds=card.end-card.start).total_seconds(),                
            'cardPlayed': card.name,
            'cardId': card.castId,
            'cardSource': card.source,
            'cardTarget': card.target,
            'cardDamageTable': card_damage_table.to_dict(orient='records'),
            'cardOptimalTarget': optimal_target,
            'cardCorrect': correct,
        }

def _get_active_card(cards, draw):
    active_cards = []
    for c in cards:
        # check if the card was played during the draw window
        if c.cast > draw.start and c.cast <= draw.end:
            active_cards.append(c)
        if c.cast > draw.end:
            break
    return active_cards

def _handle_draw_play_damage(draw_window_damage_collection, draw_window_duration, fight_info, actors):
    melee_draw_damage = []
    ranged_draw_damage = []

    data_count = 0

    if draw_window_duration < 4.0:
        data_count = 2
    elif draw_window_duration < 10.0:
        data_count = 4
    elif draw_window_duration < 20.0:
        data_count = 6
    else:
        data_count = 8

    sorted_damage_list = pd.DataFrame((draw_window_damage_collection.df.unstack().to_dict().items()), columns=['combined', 'damage'])
    
    sorted_damage_list['id'] = sorted_damage_list['combined'].apply(lambda row: row[0])
    sorted_damage_list['timestamp'] = sorted_damage_list['combined'].apply(lambda row: row[1])
    sorted_damage_list.drop(columns=['combined'], inplace=True)
    sorted_damage_list.sort_values(by='damage', inplace=True, ascending=False)

    # separate out the ranged and melee instances
    sorted_damage_list['role'] = sorted_damage_list['id'].apply(lambda row: actors.players[row].role)

    melee_damage_list = sorted_damage_list.loc[lambda df: (df['role'] == 'melee')]
    ranged_damage_list = sorted_damage_list.loc[lambda df:(df['role'] == 'ranged')]

    collected_count = 0
    examined_count = 0

    while collected_count < data_count and examined_count < melee_damage_list['id'].size:
        # get the next lowest damage instance
        # current_item = melee_damage_list.iloc[examined_count]
        
        target_opt = melee_damage_list['id'].iloc[examined_count]
        time_opt = melee_damage_list['timestamp'].iloc[examined_count]
        damage_opt = melee_damage_list['damage'].iloc[examined_count]
        # ) = (current_item[0][0], current_item[0][1], current_item[1])

        examined_count += 1

        # check if the new entry we've selected is in a window of 4s as an entry from that player with higher damage
        ignore_entry = False
        for table_entry in melee_draw_damage:
            if target_opt == table_entry['id'] and abs(time_opt - table_entry['timestamp']) < 4000:
                ignore_entry = True
            
        if ignore_entry:
            continue

        # if the max damage is greater than 0 then add an entry:
        if damage_opt > 0:
            collected_count += 1
            melee_draw_damage.append({
                'count': collected_count,
                'id': target_opt,
                'damage': damage_opt,
                'timestamp': time_opt,
                'time': fight_info.ToString(time=int(time_opt))[:5],
            })

    collected_count = 0
    examined_count = 0

    while collected_count < data_count and examined_count < ranged_damage_list['id'].size:
        # get the next lowest damage instance
        target_opt = ranged_damage_list['id'].iloc[examined_count]
        time_opt = ranged_damage_list['timestamp'].iloc[examined_count]
        damage_opt = ranged_damage_list['damage'].iloc[examined_count]

        examined_count += 1
        # (target_opt, time_opt, damage_opt) = (current_item[0][0], current_item[0][1], current_item[1])

        # check if the new entry we've selected is in a window of 4s as an entry from that player with higher damage
        ignore_entry = False
        for table_entry in ranged_draw_damage:
            if target_opt == table_entry['id'] and abs(time_opt - table_entry['timestamp']) < 4000:
                ignore_entry = True
            
        if ignore_entry:
            continue

        # if the max damage is greater than 0 then add an entry:
        if damage_opt > 0:
            collected_count += 1
            ranged_draw_damage.append({
                'count': collected_count,
                'id': target_opt,
                'damage': damage_opt,
                'timestamp': time_opt,
                'time': fight_info.ToString(time=int(time_opt))[:5],
            })

    melee_draw_damage_table = pd.DataFrame(melee_draw_damage)

    if not melee_draw_damage_table.empty:
        melee_draw_damage_table.set_index('id', inplace=True, drop=False)
        melee_draw_damage_table.sort_values(by='damage', inplace=True, ascending=False)

    ranged_draw_damage_table = pd.DataFrame(ranged_draw_damage)
    
    if not ranged_draw_damage_table.empty:
        ranged_draw_damage_table.set_index('id', inplace=True, drop=False)
        ranged_draw_damage_table.sort_values(by='damage', inplace=True, ascending=False)

    return (melee_draw_damage_table, ranged_draw_damage_table)

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
    
    # Get all damage events
    damage_events = get_damage_events(fight_info, token)

    # Sum dot snapshots
    tick_report = calc_snapshot_damage(damage_events)
    # get correct timestamps from prepare events
    raw_report = cleanup_prepare_events(damage_events)
    # print(raw_report)

    damage_report = pd.concat([tick_report, raw_report], ignore_index=True)
    damage_report.sort_values(by='timestamp', inplace=True, ignore_index=True)

    # clean up hit types
    damage_report = cleanup_hit_data(damage_report)

    # compute data without card buffs
    damage_report = compute_remove_card_damage(damage_report, cards, actors)

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
        active_cards = _get_active_card(cards, draw)
        # for now we toss out other active cards
        card = active_cards[0] if len(active_cards) > 0 else None
        
        # only handle the play window if there was a card played
        card_play_data = _handle_card_play(card, cards, damage_report, actors, fight_info)
        
        # now we can begin compiling data for the draw window as a whole
        card_draw_data = {}

        # 15s search window corresponding to possible card plays 
        # during the draw window and then search it 
        search_window = SearchWindow(draw.start, draw.end, 15000, 1000)
        draw_window_damage_collection = search_burst_window(damage_report, search_window, actors)

        draw_window_duration = timedelta(milliseconds=(draw.end-draw.start)).total_seconds()

        (melee_draw_damage_table, ranged_draw_damage_table) = _handle_draw_play_damage(draw_window_damage_collection, draw_window_duration, fight_info, actors)

        if not ranged_draw_damage_table.empty:
            draw_optimal_time_ranged = fight_info.ToString(time=int(ranged_draw_damage_table['timestamp'].iloc[0]))[:5]
            draw_optimal_target_ranged = actors.players[ranged_draw_damage_table['id'].iloc[0]].name
            draw_optimal_damage_ranged = int(ranged_draw_damage_table['damage'].iloc[0])
        else:
            draw_optimal_time_ranged = 'None'
            draw_optimal_target_ranged = 'None'
            draw_optimal_damage_ranged = 0

        if not melee_draw_damage_table.empty:
            draw_optimal_time_melee = fight_info.ToString(time=int(melee_draw_damage_table['timestamp'].iloc[0]))[:5]
            draw_optimal_target_melee = actors.players[melee_draw_damage_table['id'].iloc[0]].name
            draw_optimal_damage_melee = int(melee_draw_damage_table['damage'].iloc[0])
        else:
            draw_optimal_time_melee = 'None'
            draw_optimal_target_melee = 'None'
            draw_optimal_damage_melee = 0


        card_draw_data = {
            'startTime': fight_info.ToString(time=draw.start)[:5],
            'endTime': fight_info.ToString(time=draw.end)[:5],
            'startEvent': draw.startEvent,
            'endEvent': draw.endEvent,
            'startId': int(draw.startId),
            'endId': int(draw.endId),
            'drawDamageTableMelee': melee_draw_damage_table.to_dict(orient='records'),
            'drawDamageTableRanged': ranged_draw_damage_table.to_dict(orient='records'),
            'drawOptimalTimeRanged': draw_optimal_time_ranged,
            'drawOptimalTargetRanged': draw_optimal_target_ranged,
            'drawOptimalDamageRanged': draw_optimal_damage_ranged,
            'drawOptimalTimeMelee': draw_optimal_time_melee,
            'drawOptimalTargetMelee': draw_optimal_target_melee,
            'drawOptimalDamageMelee': draw_optimal_damage_melee,
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