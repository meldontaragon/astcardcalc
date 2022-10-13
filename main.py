from datetime import datetime
import os
import json
from collections import OrderedDict
from urllib.parse import urlparse, parse_qs

from flask import Flask, render_template, request, redirect, send_from_directory, url_for

from google.cloud import bigquery

from cardcalc_fflogsapi import decompose_url, get_bearer_token
from cardcalc_data import  CardCalcException
from cardcalc_cards import cardcalc

app = Flask(__name__)
LAST_CALC_DATE = datetime.fromtimestamp(1663886556)
token = get_bearer_token()

client = bigquery.Client('astcardcalc')
Reports = client.get_table('astcardcalc.Reports.Reports')
Counts = client.get_table('astcardcalc.Reports.Counts')


def get_count():
    count_query = client.query("SELECT * FROM `astcardcalc.Reports.Counts`;").result()
    
    report_count = next(count_query).get('total_reports')
    return report_count

def increment_count():
    report_count = get_count() + 1

    sql = """
UPDATE `astcardcalc.Reports.Counts`
SET total_reports = {}
WHERE total_reports > 0;
""".format(report_count)

    client.query(sql).result()
    return report_count

def prune_reports():
        Reports = client.get_table('astcardcalc.Reports.Reports')
        if Reports.num_rows > 10000:
            sql_get = """SELECT computed FROM `astcardcalc.Reports.Reports`
    ORDER BY computed ASC
    LIMIT 1 OFFSET 500"""
            time_query = client.query(sql_get).result()
            computed_cutoff = next(time_query).get('computed')
            sql_delete = """DELETE FROM `astcardcalc.Reports.Reports`
WHERE computed < {}""".format(computed_cutoff)
            client.query(sql_delete).result()

@app.route('/', methods=['GET', 'POST'])
def homepage():
    """Simple form for redirecting to a report, no validation"""
    if request.method == 'POST':
        report_url = request.form['report_url']
        try:
            report_id, fight_id = decompose_url(report_url, token)
        except CardCalcException as exception:
            return render_template('error.html', exception=exception)

        return redirect(url_for('calc', report_id=report_id, fight_id=fight_id))

    return render_template('home.html')

@app.route('/about')
def about():
    return render_template('about.html', report_count=get_count())

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/png')

@app.route('/<string:report_id>/<int:fight_id>')
def calc(report_id, fight_id):
    """The actual calculated results view"""
    # Very light validation, more for the db query than for the user
    if ( len(report_id) < 14 or len(report_id) > 24 ):
        return redirect(url_for('homepage'))

    sql_report = None
    report = None

    sql = """
SELECT * FROM `astcardcalc.Reports.Reports`
WHERE report_id='{}' AND fight_id={}
ORDER BY computed DESC;
""".format(report_id, fight_id)
    query_res = client.query(sql).result()

    if (query_res.total_rows > 0):
        sql_report = next(query_res)
        sql_report = dict(sql_report.items())
        
        report = {
            'report_id': sql_report['report_id'],
            'fight_id': sql_report['report_id'],
            'results': json.loads(sql_report['results']),
            'actors': json.loads(sql_report['actors']),
            'enc_name': sql_report['enc_name'],
            'enc_time': sql_report['enc_time'],
            'enc_kill': sql_report['enc_kill'],
            'computed': sql_report['computed'],
        }

    if sql_report is None:
        # Compute
        try:
            results, actors, encounter_info = cardcalc(report_id, fight_id, token)
        except CardCalcException as exception:
            return render_template('error.html', exception=exception)

        sql_report = {
            'report_id': report_id,
            'fight_id': fight_id,
            'results': json.dumps(results),
            'actors': json.dumps(actors),
            'enc_name': encounter_info['enc_name'],
            'enc_time': encounter_info['enc_time'],
            'enc_kill': encounter_info['enc_kill'],
            'computed': datetime.now().isoformat(),
        }
        report = {
            'report_id': report_id,
            'fight_id': fight_id,
            'results': results, 
            'actors': actors,
            'enc_name': encounter_info['enc_name'],
            'enc_time': encounter_info['enc_time'],
            'enc_kill': encounter_info['enc_kill'],
            'computed': datetime.now(),
        }

        row_result = client.insert_rows_json(Reports, [sql_report])
        print(row_result)
        increment_count()

    else:
        # Recompute if no computed timestamp
        if sql_report['computed'] < LAST_CALC_DATE:
            try:
                results, actors, encounter_info = cardcalc(report_id, fight_id, token)
            except CardCalcException as exception:
                return render_template('error.html', exception=exception)

            sql_report = {
                'report_id': report_id,
                'fight_id': fight_id,
                'results': json.dumps(results),
                'actors': json.dumps(actors),
                'enc_name': encounter_info['enc_name'],
                'enc_time': encounter_info['enc_time'],
                'enc_kill': encounter_info['enc_kill'],
                'computed': datetime.now().isoformat(),
            }
            report = {
                'report_id': report_id,
                'fight_id': fight_id,
                'results': results,
                'actors': actors,
                'enc_name': encounter_info['enc_name'],
                'enc_time': encounter_info['enc_time'],
                'enc_kill': encounter_info['enc_kill'],
                'computed': datetime.now(),
            }
            row_result = client.insert_rows_json(Reports, [sql_report])
            print(row_result)
    
    report['results'] = {int(k):v for k,v in report['results'].items()}
    report['actors'] = {int(k):v for k,v in report['actors'].items()}

    report['results'] = list( OrderedDict(sorted(report['results'].items())).values())
    actors = {int(k):v for k,v in report['actors'].items()}
    return render_template('calc.html', report=report)
