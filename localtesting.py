from datetime import datetime
import os
from urllib.parse import urlparse, parse_qs

from cardcalc import cardcalc, get_last_fight_id, CalcCalcException, print_results, get_cards_played, fflogs_api, timedelta

LAST_CALC_DATE = datetime.fromtimestamp(1563736200)

def decompose_url(url):
    parts = urlparse(url)

    report_id = [segment for segment in parts.path.split('/') if segment][-1]
    try:
        fight_id = parse_qs(parts.fragment)['fight'][0]
    except KeyError:
        raise CardCalcException("Fight ID is required. Select a fight first")

    if fight_id == 'last':
        fight_id = get_last_fight_id(report_id)

    fight_id = int(fight_id)

    return report_id, fight_id


# local testing here:

# USE THIS: https://www.fflogs.com/reports/qBxNr4V12gmZz63R#fight=12&type=damage-done

# Call Order:
# (1) cardcalc

#zeke's e12s 100: https://www.fflogs.com/reports/r7tnPLDhJb6KYVaf#fight=19&type=damage-done
# report = 'r7tnPLDhJb6KYVaf'
# fight = 19

#marielle's recent e9s run: https://www.fflogs.com/reports/byLqHjz8MnphQP3r#fight=1&type=damage-done
# report = 'byLqHjz8MnphQP3r'
# fight = 1

#x's e10s #1 parse (1/14/21): https://www.fflogs.com/reports/JkCGX4pqW1N2Fm9h#fight=21&type=damage-done
# report = 'JkCGX4pqW1N2Fm9h'
# fight = 21

#zeke's best e10s parse (1/14/21): https://www.fflogs.com/reports/Cpbh94KWTRPtHdam#fight=7&type=damage-done
report = 'Cpbh94KWTRPtHdam'
fight = 7

(results, friends, encounter_info, cards) = cardcalc(report='Cpbh94KWTRPtHdam', fight_id=7)

(results, friends, encounter_info, cards) = cardcalc(report, fight)


# for card in cards:
#     card['duration'] = timedelta(milliseconds=card['end']-card['start']).total_seconds()
#     print(card)

# for res in results:
#     print(res['cardtype'])
#     for dam in res['damages']:
#         print(dam)
#     print()

print_results(results, friends, encounter_info)
# for result in results