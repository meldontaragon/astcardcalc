from datetime import datetime
import os
from urllib.parse import urlparse, parse_qs

from flask import Flask, render_template, request, redirect, send_from_directory, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError

from cardcalc_fflogsapi import decompose_url, get_bearer_token
from cardcalc_data import  CardCalcException
from cardcalc_cards import cardcalc

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] =  os.environ['DATABASE_URL']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

LAST_CALC_DATE = datetime.fromtimestamp(1642454356)

token = get_bearer_token()

class Report(db.Model):
    report_id = db.Column(db.String(16), primary_key=True)
    fight_id = db.Column(db.Integer, primary_key=True)
    results = db.Column(db.JSON)
    actors = db.Column(db.JSON)
    enc_name = db.Column(db.String(64))
    enc_time = db.Column(db.String(9))
    enc_kill = db.Column(db.Boolean)
    computed = db.Column(db.DateTime, server_default=db.func.now())

class Count(db.Model):
    count_id = db.Column(db.Integer, primary_key=True)
    total_reports = db.Column(db.Integer)

def increment_count(db):
    count = Count.query.get(1)

    # TODO: Fix this
    try:
        count.total_reports = count.total_reports + 1
    except:
        print('Count db error')
        print(os.path.dirname(os.path.realpath(__file__)))
        count = Count(count_id = 1, total_reports = 1)
        db.session.add(count)
    db.session.commit()

def prune_reports(db):
    if Report.query.count() > 9500:
        # Get the computed time of the 500th report
        delete_before = Report.query.order_by('computed').offset(500).first().computed

        # Delete reports before that
        Report.query.filter(Report.computed < delete_before).delete()
        db.session.commit()

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
    # TODO: Fix this
    try:
        count = Count.query.get(1)
    except:
        print('Count db error.')
        print(os.path.dirname(os.path.realpath(__file__)))        
        # db.create_all()
        # db.session.add(count)
        # db.session.commit()
        count = Count(count_id = 1, total_reports = 1)

    return render_template('about.html', report_count=count.total_reports)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/png')

@app.route('/<string:report_id>/<int:fight_id>')
def calc(report_id, fight_id):
    """The actual calculated results view"""
    # Very light validation, more for the db query than for the user
    if len(report_id) != 16:
        return redirect(url_for('homepage'))

    # TODO: Fix this
    try:
        report = Report.query.filter_by(report_id=report_id, fight_id=fight_id).first()
    except:
        print('Report db error')
        print(os.path.dirname(os.path.realpath(__file__)))        
        db.create_all()
        report = Report.query.filter_by(report_id=report_id, fight_id=fight_id).first()

    if report:
        # Recompute if no computed timestamp
        if not report.computed or report.computed < LAST_CALC_DATE:
            try:
                results, actors, encounter_info = cardcalc(report_id, fight_id, token)
            except CardCalcException as exception:
                return render_template('error.html', exception=exception)

            report.results = results
            report.actors = actors
            report.enc_name = encounter_info['enc_name']
            report.enc_time = encounter_info['enc_time']
            report.enc_kill = encounter_info['enc_kill']
            report.computed = datetime.now()

            db.session.commit()

        # TODO: this is gonna cause some issues
        # These get returned with string keys, so have to massage it some
        actors = {int(k):v for k,v in report.actors.items()}

    else:
        try:
            results, actors, encounter_info = cardcalc(report_id, fight_id, token)
        except CardCalcException as exception:
            return render_template('error.html', exception=exception)

        report = Report(
            report_id=report_id,
            fight_id=fight_id,
            results=results,
            actors=actors,
            **encounter_info
            )
        try:
            # Add the report
            db.session.add(report)
            db.session.commit()

            # Increment count
            increment_count(db)

            # Make sure we're not over limit
            prune_reports(db)

        except IntegrityError as exception:
            # This was likely added while cardcalc was running,
            # in which case we don't need to do anything besides redirect
            pass

    return render_template('calc.html', report=report, actors=actors)
