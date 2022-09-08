from Account import Account
from Tournament import Tournament
import base64
import datetime
from DET import DET
from flask import Flask, render_template, redirect, request, send_from_directory, session, url_for
from flask_sqlalchemy import SQLAlchemy
import io
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np
import os
import pickle
import random
import sys
from werkzeug.security import generate_password_hash, check_password_hash

current_dir = os.getcwd()

#run by typing "python -m flask run" in terminal
app = Flask(__name__)

app.secret_key = "There is rain outside"
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

'''#For running the database over google coud services
# Google Cloud SQL
USER = "root"
PASSWORD = "<V=caF~>zL<:\"hHx"
PUBLIC_IP_ADDRESS = "34.116.115.25"
DBNAME = "superposition-smash"
PROJECT_ID = "superposition-smash"
INSTANCE_NAME = "superposition-smash:australia-southeast1:superposition-smash"

app.config["SQLALCHEMY_DATABASE_URI"] = f"mysql+pymysql://{USER}:{PASSWORD}@/{DBNAME}?unix_socket=/cloudsql/{INSTANCE_NAME}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)
'''

#For database on local memory
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + current_dir + '\\db.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Account_db(db.Model):
    """ User Model for storing user related details """
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    account = db.Column(db.PickleType(), nullable=True)

    def __init__(self, name, account):
        self.name = name
        self.account = account

class Tournament_db(db.Model):
    """ User Model for storing user related details """
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    tournament = db.Column(db.PickleType(), nullable=True)

    def __init__(self, name, tournament):
        self.name = name
        self.tournament = tournament

db.create_all()

#return the class object for a given account username
def load_account( username ):
    with open( f'accounts/{username}.txt', 'rb' ) as file:
        username = pickle.load( file )
    return username

#return the class object for a given tournament name
def load_tournament( name ):
    with open( f'tournaments/{name}.txt', 'rb' ) as file:
        name = pickle.load( file )
    return name

#if the entries are not in the database, then add them
directory = 'accounts/'
for filename in os.listdir(directory):
    account_name = filename[:-4]
    exists = db.session.query(db.exists().where(Account_db.name == account_name)).scalar()
    if not exists:
        object = load_account( account_name )
        new_entry = Account_db( account_name, object )
        db.session.add(new_entry)
        db.session.commit()

directory = 'tournaments/'
for filename in os.listdir(directory):
    tourn_name = filename[:-4]
    object = load_tournament( tourn_name )
    tourn_name = object.name
    exists = db.session.query(db.exists().where(Tournament_db.name == tourn_name)).scalar()
    if not exists:
        new_entry = Tournament_db( tourn_name, object )
        db.session.add(new_entry)
        db.session.commit()

######### HTML routes
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                          'favicon.ico',mimetype='image/vnd.microsoft.icon')

@app.route("/", methods=['GET', 'POST'])
def index():
    if 'user_names' not in session:
        session['user_names'] = []
    user_name = request.form.get("user_name", "").lower()
    password = request.form.get("password", "")
    if user_name and password:
        txt = login_account( user_name, password )
        if txt=='Login successful':
            if user_name not in session['user_names']:
                session['user_names'].append(user_name)
                session.modified = True
            return account_stats( user_name )
        else:
            return render_template('index.html', debug_message=txt )
    else:
        return render_template('index.html')

#show a list of previous and active touornaments that can be viewed or joined respectively
@app.route("/<user_name>/tournaments_list", methods=['GET', 'POST'])
def tournaments_list( user_name ):

    x = check_if_logged_in( user_name )
    if x=='redirect':
        return redirect(url_for('index'))

    kwargs = dict()
    kwargs['user_name'] = user_name

    account = load_account_from_db( user_name )

    new_tournament_name = request.form.get("new_tournament_name", "")
    if new_tournament_name:
        if account.isadmin:
            txt = create_tournament_in_db( new_tournament_name )
            kwargs['debug_message'] = txt
        else:
            kwargs['debug_message'] = 'Admin required to create tournament!'

    kwargs['live_tourns'] = get_all_live_tournaments_in_db()
    kwargs['previous_tourns'] = get_all_previous_tournaments_in_db()

    #only allow to manage accounts if user is admin
    account = load_account_from_db( user_name )
    if account.isadmin:
        kwargs['visibility']="visible"
    else:
        kwargs['visibility']="hidden"

    return render_template('tournaments_list.html', **kwargs)

#show details for a specific tournament
@app.route("/<user_name>/<tournament_name>/live", methods=['GET', 'POST'])
def live_tournament_details( user_name, tournament_name ):

    x = check_if_logged_in( user_name )
    if x=='redirect':
        return redirect(url_for('index'))

    kwargs = dict()
    kwargs['user_name'] = user_name
    account = load_account_from_db( user_name )
    kwargs['tournament'] = load_tournament_from_db( tournament_name )
    kwargs['tournament_name'] = kwargs['tournament'].name

    if "submit_button" in request.form:
        if request.form['submit_button']=="active":
            if kwargs['user_name'] not in kwargs['tournament'].active_participants:
                account, is_new = check_if_new_tournament( kwargs['tournament'], account )
                if is_new:
                    kwargs['debug_message'] = 'New tournament: 1000 awarded'
                kwargs['tournament'].active_participants.append( kwargs['user_name'] )
            if kwargs['user_name'] in kwargs['tournament'].passive_participants:
                kwargs['tournament'].passive_participants.remove( kwargs['user_name'] )

        elif request.form['submit_button']=="passive":
            if kwargs['user_name'] not in kwargs['tournament'].passive_participants:
                account, is_new = check_if_new_tournament( kwargs['tournament'], account )
                if is_new:
                    kwargs['debug_message'] = 'New tournament: 1000 awarded'
                kwargs['tournament'].passive_participants.append( kwargs['user_name'] )
            if kwargs['user_name'] in kwargs['tournament'].active_participants:
                kwargs['tournament'].active_participants.remove( kwargs['user_name'] )

        elif request.form['submit_button']=="start_tournament":
            if account.isadmin:
                if len(kwargs['tournament'].active_participants)>1:
                    if request.form['seed'] and isint(request.form['seed']):
                        kwargs['tournament'].seed = int(request.form['seed'])
                    else:
                        kwargs['tournament'].seed = random.randrange(sys.maxsize)
                    kwargs['tournament'] = start_tournament( kwargs['tournament'] )
                    kwargs['tournament'] = calculate_tournament_odds( kwargs['tournament'] )
                else:
                    kwargs['debug_message'] = f"Not enough active participants! ({len(kwargs['tournament'].active_participants)})"
            else:
                kwargs['debug_message'] = 'Admin required to start tournament!'

        elif request.form['submit_button']=="new_match_result" and kwargs['tournament'].DET is not None:
            if account.isadmin:
                kwargs['debug_message'], kwargs['tournament'] = enter_new_match_result( request.form, kwargs['tournament'] )
            else:
                kwargs['debug_message'] = 'Admin required to enter match result!'

        elif request.form['submit_button']=="close_tournament":
            if account.isadmin:
                kwargs['tournament'].live = False
            else:
                kwargs['debug_message'] = 'Admin required to start tournament!'

        elif request.form['submit_button']=='redeem':
            if account.coin<3000:
                kwargs['debug_message'] = f'Insufficient funds to redeem ({account.coin:.2f})!'
            else:
                kwargs['debug_message'] = f'Gained 1 reward'
                redeem( account )

        elif request.form['submit_button']=='tournament_bet':
            if kwargs['tournament'].DET is not None:
                bet_target = request.form.get("tourn_bet_target", "")
                #stop tournament betting if a match result has already been entered or closed
                proceed = True
                if kwargs['tournament'].matches:
                    for m in kwargs['tournament'].matches:
                        if m[2] is not None:
                            proceed = False
                if proceed:
                    if account.username in kwargs['tournament'].passive_participants or account.username in kwargs['tournament'].active_participants:
                        if bet_target:
                            if request.form['tourn_bet_amount'] and isfloat(request.form['tourn_bet_amount']):
                                kwargs['debug_message'], kwargs['tournament'] = make_tournament_bet( tourn=kwargs['tournament'], bet_maker=account, bet_target=bet_target, bet_amount=request.form['tourn_bet_amount'] )
                            else:
                                kwargs['debug_message'] = 'Specify tournament bet amount!'
                        else:
                            kwargs['debug_message'] = 'Specify tournament bet target!'
                    else:
                        kwargs['debug_message'] = 'Please join as spectator first!'
                else:
                    kwargs['debug_message'] = 'Tournament betting has been closed!'
            else:
                kwargs['debug_message'] = 'Tournament has not started!'

        elif request.form['submit_button']=='match_bet':
            bet_target = request.form.get("match_bet_target", "")
            proceed = True
            if kwargs['tournament'].matches:
                for m in kwargs['tournament'].matches:
                    print('closed', bet_target, m)
                    if bet_target in m and m[2]=='closed':
                        proceed = False
            if proceed:
                if account.username in kwargs['tournament'].passive_participants or account.username in kwargs['tournament'].active_participants:
                    if bet_target:
                        if request.form['match_bet_amount'] and isfloat(request.form['match_bet_amount']):
                            kwargs['debug_message'], kwargs['tournament'] = make_match_bet( tourn=kwargs['tournament'], bet_maker=account, bet_target=bet_target, bet_amount=request.form['match_bet_amount'] )
                        else:
                            kwargs['debug_message'] = 'Specify match bet amount!'
                    else:
                        kwargs['debug_message'] = 'Specify match bet target!'
                else:
                    kwargs['debug_message'] = 'Please join as spectator first!'
            else:
                kwargs['debug_message'] = 'Betting has been closed for this match!'

        elif request.form['submit_button'][:15]=='close_match_bet':
            if account.isadmin:
                idx = int(request.form['submit_button'].split('_')[-1])
                m = kwargs['tournament'].DET.get_active_matches()[idx]
                player_dict = kwargs['tournament'].player_dict
                zero = cap_name(player_dict[m.get_participants()[0].get_competitor()].lower())
                one = cap_name(player_dict[m.get_participants()[1].get_competitor()].lower())
                for i, match in enumerate(kwargs['tournament'].matches):
                    if one in match and zero in match and match[2]==None:
                        kwargs['tournament'].matches[i][2] = 'closed'
            else:
                kwargs['debug_message'] = 'Admin required to start close match bet!'

    account = load_account_from_db( user_name )
    kwargs['personal_rating'] = f'{account.rating:.0f}'
    kwargs['personal_handicap'] = account.handicap
    kwargs['personal_coin'] = f'{account.coin:.2f}'
    kwargs['personal_rewards'] = f'{account.rewards}'

    kwargs['tournament_odds_txt'] = "Player (Win %): Odds<br>"
    if kwargs['tournament'].initial_odds:
        for key in kwargs['tournament'].initial_odds:
            odds = kwargs["tournament"].initial_odds[key]
            winrate = round( 100/odds, 2 )
            kwargs['tournament_odds_txt'] += f'{cap_name(key)} ({winrate}%): {odds}<br>'

    kwargs['winners_bracket_txt'] = ""
    kwargs['losers_bracket_txt'] = ""
    if kwargs['tournament'].bracket:
        kwargs['tournament'] = update_bracket( kwargs['tournament'] )
        kwargs['winners_bracket_txt'], kwargs['losers_bracket_txt'] = kwargs['tournament'].bracket[0], kwargs['tournament'].bracket[1]

    kwargs['active_match_txts'], kwargs['stats'], kwargs['left_txts'], kwargs['right_txts'], kwargs['match_bet_txts'] = [""], [""], [""], [""], [""]
    kwargs['active_players'] = []
    if kwargs['tournament'].DET is not None:
        kwargs['active_players'] = get_active_players( kwargs['tournament'] )
        txts, stats, left_txts, right_txts, match_bet_txts = get_active_matches_and_stats( kwargs['tournament'] )
        kwargs['active_match_txts'] = txts
        kwargs['stats'] = stats
        kwargs['left_txts'] = left_txts
        kwargs['right_txts'] = right_txts
        kwargs['match_bet_txts'] = match_bet_txts

    kwargs['seed'] = kwargs['tournament'].seed

    kwargs['passive_participants'] = [ cap_name(x) for x in kwargs['tournament'].passive_participants ]
    kwargs['active_participants'] = [ cap_name(x) for x in kwargs['tournament'].active_participants ]

    save_tournament_to_db( kwargs['tournament'] )        

    #decide what is to be shown in the live tournament template
    kwargs['admin_visibility'] = "hidden"
    kwargs['close_visibility'] = "hidden"
    kwargs['tourn_visibility'] = "hidden"
    kwargs['tourn_bet_visibility'] = "visible"
    if account.isadmin:
        kwargs['admin_visibility'] = "visible"
        if kwargs['tournament'].winner:
            kwargs['close_visibility'] = "visible"
            kwargs['admin_visibility'] = "hidden"
    if kwargs['tournament'].DET:
        kwargs['tourn_visibility'] = "visible"
    if not kwargs['tournament'].DET:
        kwargs['tourn_bet_visibility'] = "hidden"
    if kwargs['tournament'].matches:
        for m in kwargs['tournament'].matches:
            if m[2] is not None:
                kwargs['tourn_bet_visibility'] = "hidden"

    kwargs['tournament_log'] = []
    if kwargs['tournament'].log:
        kwargs['tournament_log'] = kwargs['tournament'].log.split('\n')

    kwargs['tournament_bets'] = []
    if kwargs['tournament'].tournament_bets:
        for tb in kwargs['tournament'].tournament_bets:
            kwargs['tournament_bets'].append( f'{cap_name(tb[0])} ({cap_name(tb[1])}): {tb[2]:.2f}' )

    return render_template('live_tournament_details.html', **kwargs)

#show details for a specific tournament
@app.route("/<user_name>/<tournament_name>/previous", methods=['GET', 'POST'])
def previous_tournament_details( user_name, tournament_name ):

    x = check_if_logged_in( user_name )
    if x=='redirect':
        return redirect(url_for('index'))

    kwargs = dict()
    kwargs['user_name'] = user_name
    kwargs['tournament'] = load_tournament_from_db( tournament_name )
    kwargs['tournament_name'] = kwargs['tournament'].name
    kwargs['seed'] = kwargs['tournament'].seed

    tb_txt = ""
    tb = kwargs['tournament'].tournament_bets
    name_set = set([ x[1] for x in tb ])
    for n in name_set:
        tb_txt += f'To win: <strong>{cap_name(n)}</strong><br>Bets:<br>'
        for x in tb:
            if x[1]==n:
                tb_txt += f'    - {cap_name(x[0])}: {float(x[2]):.2f}<br>'
        tb_txt += '<br>' 

    mb_txt = ""
    ms = kwargs['tournament'].matches
    mb = kwargs['tournament'].match_bets
    for idx, m in enumerate(ms):
        mb_txt += f"Match: <strong>{cap_name(m[0])} def {cap_name(m[1])} (MOV: {m[2]})</strong><br>Bets:<br>"
        if mb:
            for b in mb[idx]:
                if b[2]=='all':
                    mb_txt += f'    - {cap_name(b[0])} ({cap_name(b[1])}): All in<br>'
                else:
                    mb_txt += f'    - {cap_name(b[0])} ({cap_name(b[1])}): {float(b[2]):.2f}<br>'
        mb_txt += '<br>'

    kwargs['tournament_bet_txt'] = tb_txt
    kwargs['match_txt'] = mb_txt

    if kwargs['tournament'].bracket:
        kwargs['winners_bracket_txt'], kwargs['losers_bracket_txt'] = kwargs['tournament'].bracket[0], kwargs['tournament'].bracket[1]

    kwargs['tournament_odds_txt'] = ""
    if kwargs['tournament'].initial_odds:
        for key in kwargs['tournament'].initial_odds:
            odds = kwargs["tournament"].initial_odds[key]
            winrate = round( 100/odds, 2 )
            kwargs['tournament_odds_txt'] += f'{cap_name(key)} ({winrate}%): {odds}<br>'

    kwargs['tournament_log'] = []
    if kwargs['tournament'].log:
        kwargs['tournament_log'] = kwargs['tournament'].log.split('\n')    

    return render_template('previous_tournament_details.html', **kwargs)

#Remove the user account from the session and logout
@app.route('/<user_name>/logout', methods=['GET', 'POST'])
def logout( user_name ):
    # remove the username from the session if it is there
    if user_name in session['user_names']:
        session['user_names'].remove(user_name)
        session.modified = True
    return redirect(url_for('index'))

#Printed instructions for users and admins
@app.route('/<user_name>/info', methods=['GET', 'POST'])
def info( user_name ):

    x = check_if_logged_in( user_name )
    if x=='redirect':
        return redirect(url_for('index'))

    kwargs = dict()
    kwargs['debug_message']=''
    account = load_account_from_db( user_name )
    kwargs['user_name'] = account.username

    #only allow admin specific information if user is admin
    if account.isadmin:
        kwargs['visibility']="visible"
    else:
        kwargs['visibility']="hidden"

    return render_template('info.html', **kwargs)

@app.route("/<user_name>", methods=['GET', 'POST'])
def account_stats( user_name ):

    x = check_if_logged_in( user_name )
    if x=='redirect':
        return redirect(url_for('index'))

    kwargs = dict()
    kwargs['debug_message']=''
    account = load_account_from_db( user_name )

    #only allow to manage accounts if user is admin
    if account.isadmin:
        kwargs['visibility']="visible"
    else:
        kwargs['visibility']="hidden"

    kwargs['user_name'] = account.username
    if account.isadmin:
        kwargs['printed_username'] = cap_name( kwargs['user_name'] ) + ' (Admin)'
    else:
        kwargs['printed_username'] = cap_name( kwargs['user_name'] )

    old_password = request.form.get("old_password", "")
    new_password = request.form.get("new_password", "")
    if old_password and new_password:
        kwargs['debug_message'] = login_account( kwargs['user_name'], old_password )
        if kwargs['debug_message']=='Login successful':
            account.password = generate_password_hash(new_password)
            save_account_to_db( account )
            kwargs['debug_message']='Password updated'
        else:
            kwargs['debug_message']='Invalid password!'

    #get statistics for the logged in account
    kwargs['rewards'] = account.rewards
    kwargs['tournaments_played'] = len(account.tournaments)
    kwargs['tournaments_won'] = account.tournament_wins
    kwargs['tournament_win_percent'] = round( 100 * kwargs['tournaments_won'] / kwargs['tournaments_played'] , 2 ) if kwargs['tournaments_played']>0 else 0
    kwargs['games_played'] = sum( [ len(x) for x in account.record ] )
    kwargs['games_won'] = flatten( flatten( account.record ) ).count( 'W' ) #one flatten for each of the two dimensions
    kwargs['game_win_percent'] = round( 100 * kwargs['games_won'] / kwargs['games_played'] , 2 ) if kwargs['games_played']>0 else 0
    kwargs['recent_record'] = ' '.join(  [ x[0] for x in flatten(account.record) ][-10:] )

    kwargs['rating'] = round(account.rating,2)
    kwargs['rating_history'] = flatten(account.rating_history)
    kwargs['rating_max'], kwargs['rating_min'] = round(max(kwargs['rating_history']),2) if len(kwargs['rating_history'])>0 else 0, round(min(kwargs['rating_history']),2) if len(kwargs['rating_history'])>0 else 0

    kwargs['coin'] = round(account.coin,2)
    kwargs['coin_history'] = flatten(account.coin_history)
    kwargs['coin_max']= round(max(kwargs['coin_history']),2) if len(kwargs['coin_history'])>0 else 0

    kwargs['handicap'] = int(account.handicap)
    kwargs['handicap_history'] = flatten(account.handicap_history)
    kwargs['handicap_max'], kwargs['handicap_min'] = int(max(kwargs['handicap_history'])) if len(kwargs['handicap_history'])>0 else 0, int(min(kwargs['handicap_history'])) if len(kwargs['handicap_history'])>0 else 0

    bets = account.bets

    kwargs['total_match_bets'] = int(sum( [b[0]=='match' for b in bets] ))
    kwargs['match_bets_won'] = int(sum( [b[0]=='match' and b[4]=='W' for b in bets] ))
    kwargs['match_bets_percent'] = round(100*kwargs['match_bets_won']/kwargs['total_match_bets'], 2) if kwargs['total_match_bets']!=0 else 0
    kwargs['average_match_bet'] = round(sum( [ b[2] for b in bets if b[0]=='match' ] )/kwargs['total_match_bets'],2) if kwargs['total_match_bets']!=0 else 0
    kwargs['average_match_odds'] = round(sum( [ b[3] for b in bets if b[0]=='match' ] )/kwargs['total_match_bets'],2) if kwargs['total_match_bets']!=0 else 0
    kwargs['match_profit_loss'] = round(sum( [ b[2]*(b[3]-1) for b in bets if b[0]=='match' and b[4]=='W' ] ) - sum( [ b[2] for b in bets if b[0]=='match' and b[4]=='L' ] ),2)
    kwargs['favourite_match_pick'] = 'None' if not set([b[1] for b in bets if b[0]=='match']) else max(set([b[1] for b in bets if b[0]=='match']), key=[b[1] for b in bets if b[0]=='match'].count)

    kwargs['total_tournament_bets'] = int(sum( [b[0]=='tournament' for b in bets] ))
    kwargs['tournament_bets_won'] = int(sum( [b[0]=='tournament' and b[4]=='W' for b in bets] ))
    kwargs['tournament_bets_percent'] = round(100*kwargs['tournament_bets_won']/kwargs['total_tournament_bets'], 2) if kwargs['total_tournament_bets']!=0 else 0
    kwargs['average_tournament_bet'] = round(sum( [ b[2] for b in bets if b[0]=='tournament' ] )/kwargs['total_tournament_bets'],2) if kwargs['total_tournament_bets']!=0 else 0
    kwargs['average_tournament_odds'] = round(sum( [ b[3] for b in bets if b[0]=='tournament' ] )/kwargs['total_tournament_bets'],2) if kwargs['total_tournament_bets']!=0 else 0
    kwargs['tournament_profit_loss'] = round(sum( [ b[2]*(b[3]-1) for b in bets if b[0]=='tournament' and b[4]=='W' ] ) - sum( [ b[2] for b in bets if b[0]=='tournament' and b[4]=='L' ] ),2)
    kwargs['favourite_tournament_pick'] = 'None' if not set([b[1] for b in bets if b[0]=='tournament']) else max(set([b[1] for b in bets if b[0]=='tournament']), key=[b[1] for b in bets if b[0]=='tournament'].count)

    rating_fig = generate_hist_plot( account, 'rating' )
    coin_fig = generate_hist_plot( account, 'coin' )
    handicap_fig = generate_hist_plot( account, 'handicap' )
    matchup_fig = matchup_plot( account )

    kwargs['rating_image'] = convert_fig_to_png( rating_fig )
    kwargs['coin_image'] = convert_fig_to_png( coin_fig )
    kwargs['handicap_image'] = convert_fig_to_png( handicap_fig )
    kwargs['matchup_image'] = convert_fig_to_png( matchup_fig )

    return render_template('account_stats.html', **kwargs)

@app.route("/<user_name>/manage_accounts", methods=['GET', 'POST'])
def manage_accounts( user_name ):

    account = load_account_from_db( user_name )

    x = check_if_logged_in( user_name )
    if x=='redirect' or not account.isadmin:
        return redirect(url_for('index'))

    kwargs = dict()
    kwargs['user_name'] = user_name
    kwargs['debug_message'] = ''

    account_name = request.form.get("account_name", "")
    account_to_delete = request.form.get("account_to_delete", "")
    tournament_to_delete = request.form.get("tournament_to_delete", "")
    isadmin = request.form.get("isadmin", "")
    rating = request.form.get("rating", "")
    rating_history = request.form.get("rating_history", "")
    coin = request.form.get("coin", "")
    coin_history = request.form.get("coin_history", "")
    rewards = request.form.get("rewards", "")
    tournaments = request.form.get("tournaments", "")
    tournament_wins = request.form.get("tournament_wins", "")
    handicap = request.form.get("handicap", "")
    handicap_history = request.form.get("handicap_history", "")
    record = request.form.get("record", "")
    show = request.form.get("show", "")

    new_account_name = request.form.get("new_account_name", "")
    deposit_amount = request.form.get("deposit_amount", "")

    if "submit_button" in request.form:
        if request.form['submit_button']=="update":
            if account_name!="":
                account = load_account_from_db( account_name )

                #Quick and dirty check of the inputs and then update each attribute
                attributes = [[isadmin,'isadmin',isbool,'Admin must be boolean<br>'], 
                        [rating,'rating',isfloat,'Rating must be float<br>'],
                        [rating_history,'rating_history',islist,'Rating history must be list/list of lists of floats<br>'],
                        [coin,coin,'isfloat','Coin must be float<br>'],
                        [coin_history,'coin_history',islist,'Coin history must be list/list of lists of floats<br>'],
                        [rewards,'rewards',isint,'Rewards must be int<br>'],
                        [tournaments,'tournaments',islist,'Tournaments must be list of strings<br>'],
                        [tournament_wins,'tournament_wins',isint,'Tournament wins must be int<br>'],
                        [handicap,'handicap',isint,'Handicap must be int<br>'],
                        [handicap_history,'handicap_history',islist,'Handicap history must be list/list of lists of ints<br>'],
                        [record,'record',islist,'Record must be list/list of lists of strings<br>'],
                        [show,'show',isbool,'Show must be boolean<br>']]

                for attribute in attributes:
                    if attribute[0]!="":
                        if attribute[2](attribute[0]):
                            setattr( account, attribute[1], eval(attribute[0]) )
                        else:
                            kwargs['debug_message']+=attribute[3]

                save_account_to_db( account )

        elif request.form['submit_button']=="create":
            if new_account_name:
                txt = create_account_in_db( new_account_name, password='password' )
                kwargs['debug_message'] = txt

        elif request.form['submit_button']=="delete_account":
            if account_to_delete:
                del_account_from_db( account_to_delete )
                kwargs['debug_message'] = f'Account successfully deleted: {account_to_delete}'

        elif request.form['submit_button']=="delete_tournament":
            if tournament_to_delete:
                del_tournament_from_db( tournament_to_delete )
                kwargs['debug_message'] = f'Tournament successfully deleted: {account_to_delete}'

        elif request.form['submit_button']=="deposit":
            if deposit_amount and isfloat( deposit_amount ):
                deposit_amount = round( float( deposit_amount ), 2 )
                bank = load_account_from_db( 'bank' )
                transfer( bank, deposit_amount )
                kwargs['debug_message'] = f'Deposited {deposit_amount} to bank'
            else:
                kwargs['debug_message'] = f'Specify amount to deposit!'

    kwargs['account_list'] = get_account_list_in_db()
    kwargs['tournament_list'] = [t.name for t in get_all_live_tournaments_in_db() + get_all_previous_tournaments_in_db()]

    bank = load_account_from_db( 'bank' )
    kwargs['bank_total'] = f'{bank.coin:.2f}'

    return render_template('manage_accounts.html', **kwargs )


####### Account and login functions
#check the session to see if the user has logged in
def check_if_logged_in( user_name ):
    if 'user_names' not in session:
        session['user_names'] = []
        return 'redirect' #redirect(url_for('index'))
    elif user_name not in session['user_names']:
        return 'redirect' #redirect(url_for('index'))
    return None

#create a new account
def create_account_in_db( username, password ):
    username = username.lower()
    password = generate_password_hash(password)
    if not account_exist_in_db( username ): #check whether username already exists
        account = Account( username, password )
        new_entry = Account_db( username, account )
        db.session.add(new_entry)
        db.session.commit()
        return "Account created successfully"
    else:
        return "Account already exists"

#check whether account already exists
def account_exist_in_db( username ):
    exists = db.session.query(db.exists().where(Account_db.name == username)).scalar()
    return exists

#check whether password is correct for particular account
def password_correct( username, password ):
    account = load_account_from_db( username )
    if username==account.username and check_password_hash( account.password, password ):
        return True
    return False

#login into existing account
def login_account( username, password ):
    username = username.lower()
    if account_exist_in_db( username ): #make sure account exists
        if password_correct( username, password ):
            return "Login successful"
        else:
            return "Incorrect password!"
    else:
        return f"Account does not exist: {username}!"

#return the class object for a given account username
def load_account_from_db( username ):
    username = username.lower()
    account = db.session.query(Account_db).filter(Account_db.name==username).scalar()
    return account.account

#overwrite textfile with updated account stats and attributes
def save_account_to_db( updated_account ):
    account = db.session.query(Account_db).filter(Account_db.name==updated_account.username).scalar()
    account.account = updated_account
    db.session.commit()

#get list of all the names of existing accounts
def get_account_list_in_db():
    accounts = Account_db.query.all()
    accounts_list = [ cap_name(a.name) for a in accounts ]
    accounts_list.sort()
    return accounts_list

#calculate win rate for a given pair of players
def exp_winrate( player1, player2 ):
    difference = ( player1.rating + 50 * player1.handicap ) - ( player2.rating + 50 * player2.handicap )
    return 1 / ( 1 + 10 ** ( - difference / 400 ) )

#Permanently delete account from database
def del_account_from_db( name ):
    name = name.lower()
    db.session.query(Account_db).filter(Account_db.name==name).delete()
    db.session.commit()


######### Tournament functions
#check whether tournament already exists
def tournament_exist_in_db( name ):
    exists = db.session.query(db.exists().where(Tournament_db.name == name)).scalar()
    return exists

#create a new tournament
def create_tournament_in_db( name ):
    if not tournament_exist_in_db( name ): #check whether username already exists
        tournament = Tournament( name, live=True )
        new_entry = Tournament_db( name, tournament )
        db.session.add(new_entry)
        db.session.commit()
        return "Tournament created successfully"
    else:
        return f"Tournament already exists! ({name})"

def rangeBase1(length):
    return [i + 1 for i in range(length)]

def start_tournament( tournament ):
    random.seed(tournament.seed)
    names = tournament.active_participants
    names.sort()
    num_players = len(names)
    n = names
    random.shuffle(n)
    player_dict = {}
    for i in range(len(names)):
        player_dict[i+1] = cap_name(n[i])
    tournament.player_dict = player_dict
    tournament.DET = DET(rangeBase1(num_players))
    tournament = update_bracket( tournament )
    return tournament

# functions to go along with double elimination tournament generator
def add_win(det, competitor):
    det.add_win(det.get_active_matches_for_competitor(competitor)[0], competitor)

def calculate_tournament_odds( tournament ):
    player_dict = tournament.player_dict
    num_players = len(player_dict)
    p_win = np.zeros([num_players, num_players])
    for i in range(num_players):
        for j in range(i+1,num_players):
            player_i = load_account_from_db( player_dict[i+1].lower() )
            player_j = load_account_from_db( player_dict[j+1].lower() )
            p_win[i][j] = exp_winrate( player_i, player_j )
            p_win[j][i] = 1 - p_win[i][j]

    reps = 10000
    winners = []
    for _ in range(reps):
        det = DET(rangeBase1(num_players))
        
        while det.get_active_matches():
            match = det.get_active_matches()[0]
            players = [ p.competitor for p in match.get_participants() ]
            rand = random.uniform(0,1)
            if rand <= p_win[players[0]-1][players[1]-1]:
                add_win(det, players[0])
            else:
                add_win(det, players[1])
        winners.append(det.get_winners()[0])

    win_rates = [ 100 * winners.count(i+1) / reps for i in range(num_players) ]

    tournament.initial_odds = {}
    for i in range(num_players):
        tournament.initial_odds[player_dict[i+1]] = round( 100 / win_rates[i] , 2 )

    return tournament

#Generate latest tournament bracket
def update_bracket( tournament ):
    player_dict = tournament.player_dict
    tourn = tournament.DET
    match_winners = [ i.get_winner_participant().get_competitor() for i in tourn.get_matches() ]
    match_losers = [ i.get_loser_participant().get_competitor() for i in tourn.get_matches() ]
    det = DET(rangeBase1(len(player_dict)))
    names = dict( player_dict )

    winners_side = [ k for k in player_dict.keys() ]

    winners_bracket = '<strong>Winners</strong> <br>'
    losers_bracket = '<strong>Losers</strong> <br>'

    games_ref = [ g for g in det.get_matches() ]
    games_order = []

    while det.get_active_matches() != []:
        am = det.get_active_matches()

        for m in am:
            games_order.append(m)
            participants = m.get_participants()
            left, right = participants[0].get_competitor(), participants[1].get_competitor()
            if left in winners_side or right in winners_side:
                
                if left==match_winners[games_ref.index(m)] or right==match_winners[games_ref.index(m)]:
                    winners_bracket += '{}:['.format(games_order.index(m)+1)
                    winners_bracket += cap_name(names[match_winners[games_ref.index(m)]]) + ' <b>def</b> '
                    winners_bracket += cap_name(names[match_losers[games_ref.index(m)]]) + '], '
                
                else:
                    winners_bracket += '{}:['.format(games_order.index(m)+1)
                    winners_bracket += cap_name(names[left]) + ' vs '
                    winners_bracket += cap_name(names[right]) + '], '
        if '>' not in winners_bracket[-2:]:
            winners_bracket = winners_bracket[:-2]
        winners_bracket += '<br>'
        
        for m in am:
            participants = m.get_participants()
            left, right = participants[0].get_competitor(), participants[1].get_competitor()

            if left not in winners_side and right not in winners_side:

                if left==match_winners[games_ref.index(m)] or right==match_winners[games_ref.index(m)]:
                    losers_bracket += '{}:['.format(games_order.index(m)+1)
                    losers_bracket += cap_name(names[match_winners[games_ref.index(m)]]) + ' <b>def</b> '
                    losers_bracket += cap_name(names[match_losers[games_ref.index(m)]]) + '], '
                
                else:
                    losers_bracket += '{}:['.format(games_order.index(m)+1)
                    losers_bracket += cap_name(names[left]) + ' vs '
                    losers_bracket += cap_name(names[right]) + '], '
        
        if '>' not in losers_bracket[-2:]:
            losers_bracket = losers_bracket[:-2]
        losers_bracket += '<br>'
        
        for m in am:
            
            if match_winners[games_ref.index(m)] is not None:
                add_win( det, match_winners[games_ref.index(m)] )
                games_ref = [ g for g in det.get_matches() ]

                if match_losers[games_ref.index(m)] in winners_side:
                    winners_side.remove(match_losers[games_ref.index(m)])
                    
            else:
                left, right = m.get_participants()[0].get_competitor(), m.get_participants()[1].get_competitor()
                add_win( det, left )
                games_ref = [ g for g in det.get_matches() ]
                names[left] = 'W{}'.format(games_order.index(m)+1)
                names[right] = 'L{}'.format(games_order.index(m)+1)

                if right in winners_side:
                    winners_side.remove(right)

    tournament.bracket = [ winners_bracket, losers_bracket ]
    return tournament

def load_tournament_from_db( name ):
    tourn = db.session.query(Tournament_db).filter(Tournament_db.name==name).scalar()
    return tourn.tournament

#overwrite textfile with updated tournament data
def save_tournament_to_db( updated_tournament ):
    tourn = db.session.query(Tournament_db).filter(Tournament_db.name==updated_tournament.name).scalar()
    tourn.tournament = updated_tournament
    db.session.commit()

def get_all_previous_tournaments_in_db():
    tournaments = Tournament_db.query.all()
    prev_tournaments_list = [ t.tournament for t in tournaments if not t.tournament.live ]
    prev_tournaments_list.sort(key=lambda x: datetime.datetime.strptime(x.date, '%d-%m-%Y')) #sort by chronological order
    return prev_tournaments_list[::-1]

def get_all_live_tournaments_in_db():
    tournaments = Tournament_db.query.all()
    live_tournaments_list = [ t.tournament for t in tournaments if t.tournament.live ]
    live_tournaments_list.sort(key=lambda x: datetime.datetime.strptime(x.date, '%d-%m-%Y')) #sort by chronological order
    return live_tournaments_list[::-1]

#Delete tournament from database
def del_tournament_from_db( name ):
    db.session.query(Tournament_db).filter(Tournament_db.name==name).delete()
    db.session.commit()


######### Match functions
#gets all the active matches from a tournament
def get_active_matches_and_stats( tournament ):
    
    tourn = tournament.DET
    player_dict = tournament.player_dict
    active_matches = tourn.get_active_matches()
    
    txts = []
    stats = []
    left_txts = []
    right_txts = []
    match_bet_txts = []
    for m in active_matches:
        player1 = load_account_from_db( player_dict[m.get_participants()[0].get_competitor()].lower() )
        player2 = load_account_from_db( player_dict[m.get_participants()[1].get_competitor()].lower() )
        if [ cap_name(player1.username) ,cap_name(player2.username), None ] not in tournament.matches and [ cap_name(player1.username) ,cap_name(player2.username), 'closed' ] not in tournament.matches:
            tournament.matches.append( [ cap_name(player1.username) ,cap_name(player2.username), None ] )
            tournament.match_bets.append( [] ) #empty list to add match bets to later, should have same index as the corresponding matches list
        txts.append( f"<strong>{cap_name(player1.username)}</strong> vs <strong>{cap_name(player2.username)}</strong><br>" )

        match_idx = None
        for i, match in enumerate(tournament.matches):
            if cap_name(player1.username) in match and cap_name(player2.username) in match and (match[2]==None or match[2]=='closed'):
                match_idx = i
        if match_idx is not None:
            match_bets = tournament.match_bets[match_idx]
            txt = ""
            if tournament.matches[match_idx][2]=='closed':
                txt += "(Closed)<br>"
            else:
                txt += "(Open)<br>"
            for mb in match_bets:
                txt += f'{cap_name(mb[0])} ({cap_name(mb[1])}): {mb[2]:.2f}<br>'
        else:
            txt = ""

        h1 = player1.handicap
        h2 = player2.handicap
        if h1 >= h2:
            h2 = int(50 * ( h1 - h2 ))
            h1 = 0
        else:
            h1 = int(50 * (h2 - h1 ))
            h2 = 0
        wr = exp_winrate( player1, player2 )
        o1 = round( 1 / wr, 2 )
        wr = exp_winrate( player2, player1 )
        o2 = round( 1 / wr, 2 )

        g1 = len(flatten(player1.record))
        t1 = player1.tournament_wins
        w1 = len([g for g in flatten(player1.record) if g[0]=='W'])
        p1 = 0 if w1==0 else w1/g1*100
        r1 = ' '.join([ r[0] for r in flatten(player1.record)[-6:] ])
        ga1 = len([ r[0] for r in flatten(player1.record) if r[1]==cap_name(player2.username) ])
        wa1 = len([ r[0] for r in flatten(player1.record) if r[1]==cap_name(player2.username) and r[0]=='W' ])
        wp1 = 0 if wa1==0 else (wa1/ga1)*100
        m1 = ' '.join([ r[0] for r in flatten(player1.record) if r[1]==cap_name(player2.username) ][-6:])

        g2 = len(flatten(player2.record))
        t2 = player2.tournament_wins
        w2 = len([g for g in flatten(player2.record) if g[0]=='W'])
        p2 = 0 if w2==0 else (w2/g2)*100
        r2 = ' '.join([ r[0] for r in flatten(player2.record)[-6:] ])
        ga2 = len([ r[0] for r in flatten(player2.record) if r[1]==cap_name(player1.username) ])
        wa2 = len([ r[0] for r in flatten(player2.record) if r[1]==cap_name(player1.username) and r[0]=='W' ])
        wp2 = 0 if wa2==0 else (wa2/ga2)*100
        m2 = ' '.join([ r[0] for r in flatten(player2.record) if r[1]==cap_name(player1.username) ][-6:])

        stats.append( 'Name:&nbsp<br>Handicap:&nbsp<br>Odds:&nbsp<br>Games:&nbsp<br>Tournament Wins:&nbsp<br>Wins:&nbsp<br>Win Percentage:&nbsp<br>Recent Performance:&nbsp<br>Games Against:&nbsp<br>Wins Against:&nbsp<br>Win Percentage Against:&nbsp<br>Recent Results Against:&nbsp' )
        left_txts.append( '{}<br>{}%<br>{}<br>{}<br>{}<br>{}<br>{:.2f}%<br>{}<br>{}<br>{}<br>{:.2f}%<br>{}'.format( cap_name(player1.username), h1, o1, g1, t1, w1, p1, r1, ga1, wa1, wp1, m1 ) )
        right_txts.append( '{}<br>{}%<br>{}<br>{}<br>{}<br>{}<br>{:.2f}%<br>{}<br>{}<br>{}<br>{:.2f}%<br>{}'.format( cap_name(player2.username), h2, o2, g2, t2, w2, p2, r2, ga2, wa2, wp2, m2 ) )
        match_bet_txts.append( txt )

    if tourn.get_winners():
        txts.append( f'{ player_dict[tourn.get_winners()[0]] } won the tournament!' )
        stats.append( "" )
        left_txts.append( "" )
        right_txts.append( "" )
        match_bet_txts.append( "" )
    
    return txts, stats, left_txts, right_txts, match_bet_txts

#Enter new results to progress the tournament
def enter_match( tournament, winner, loser, mov ):

    for i, m in enumerate(tournament.matches):
        if cap_name(winner.username) in m and cap_name(loser.username) in m and (m[2]==None or m[2]=='closed'):
            match_idx = i
    mbets = tournament.match_bets[match_idx]
    print( 'mbets', mbets )
    winner_bets, loser_bets = enter_bets( winner, loser, mbets )
    tournament.log += f'match( SSBU, \'{cap_name(winner.username)}\', \'{cap_name(loser.username)}\', MOV={mov}, {winner_bets}, {loser_bets} )\n'

    k = 32                            #number of points available for each match, how much the rating changes after each game
    
    p1 = winner.rating                #get old rating for players
    p2 = loser.rating
    
    corr_m = 1.0                      #take autocorrelation into account if there is a big win
    if mov >= 2:
        corr_m = 2.2 / ((p1 - p2)*.001 + 2.2)
    
    rp1 = 10 ** (p1/400)              #calculating expected win rates
    rp2 = 10 ** (p2/400)
    exp_p1 = rp1 / float(rp1 + rp2)
    exp_p2 = rp2 / float(rp1 + rp2)

    new_p1 = p1 + mov * corr_m * k * (1 - exp_p1)        #assigning new rating values
    new_p2 = p2 + mov * corr_m * k * ( -exp_p2 )

    winner.rating = new_p1
    winner.rating_history[-1].append(new_p1)
    loser.rating = new_p2
    loser.rating_history[-1].append(new_p2)

    winner = update_handicap( winner )
    loser = update_handicap( loser )

    winner.record[-1].append(['W',cap_name(loser.username)])
    loser.record[-1].append(['L',cap_name(winner.username)])

    det = tournament.DET
    pd = tournament.player_dict
    for match in det.get_active_matches():
        competitors = [ pd[p.get_competitor()] for p in match.get_participants()]
        potential_players = [[cap_name(winner.username),cap_name(loser.username)],
                            [cap_name(loser.username),cap_name(winner.username)]]
        if competitors in potential_players:
            add_win( det, list(pd.keys())[list(pd.values()).index(cap_name(winner.username))] )
            
            #update matches attribute with the result
            for i, m in enumerate(tournament.matches):
                #only one result should match this condition
                if m==[ cap_name(winner.username) ,cap_name(loser.username), None ] or m==[ cap_name(loser.username) ,cap_name(winner.username), None ] or m==[ cap_name(winner.username) ,cap_name(loser.username), 'closed' ] or m==[ cap_name(loser.username) ,cap_name(winner.username), 'closed' ]:
                    tournament.matches[i] = [ cap_name(winner.username) ,cap_name(loser.username), mov ]

            #if end of the tournament -> add tournament win
            if det.get_winners():
                winner.tournament_wins += 1
                tournament.winner = cap_name(winner.username)
                tournament.log += f'tourn_win( SSBU, \'{tournament.winner}\')\n'
                save_account_to_db( winner )
                save_account_to_db( loser )
                payout_tournament_bets( tournament )

    tournament.DET = det

    save_account_to_db( winner )
    save_account_to_db( loser )

    return tournament

#collect the results for a new match and check whether valid
def enter_new_match_result( form, tourn ):
    debug = ""
    winner = form.get("new_winner", "").lower()
    if winner!="":
        winner = load_account_from_db( winner )
        loser = form.get("new_loser", "").lower()
        if loser!="":
            loser = load_account_from_db( loser )
            mov = form.get("new_mov", 0 ).lower()
            if isint(mov) and mov!='':
                mov = int(mov)
                active_matches = [ [tourn.player_dict[p.competitor] for p in am.get_participants()] for am in tourn.DET.get_active_matches() ]
                valid_match = False
                for am in active_matches:
                    winner_name, loser_name = cap_name(winner.username), cap_name(loser.username)
                    if (winner_name==am[0] and loser_name==am[1]) or (loser_name==am[0] and winner_name==am[1]):
                        tourn = enter_match( tourn, winner, loser, mov ) #to do - will need to pass on bets here as well
                        valid_match=True
                if not valid_match:
                    debug = f'Players are not in an active match! ({cap_name(winner.username)} and {cap_name(loser.username)})'
            else:
                debug = f'MOV must be an integer! ({mov})'
        else:
            debug = f'Invalid loser!'
    else:
        debug = f'Invalid winner!'
    return debug, tourn

#return a list of the players involved in the current active tournament matches
def get_active_players( tournament ):
    tourn = tournament.DET
    active_matches = [ [tournament.player_dict[p.competitor] for p in am.get_participants()] for am in tourn.get_active_matches() ]
    active_players = []
    for am in active_matches:
        active_players.append(am[0])
        active_players.append(am[1])
    return active_players

def check_if_new_tournament( tourn, player ):
    if player.tournaments==[]:
        is_new_tournament = True
    elif tourn.name not in player.tournaments:
        is_new_tournament = True
    else:
        is_new_tournament = False 
    if is_new_tournament:
        player.tournaments.append(tourn.name)
        player.coin_history.append([player.coin])
        player.handicap_history.append([player.handicap])
        player.rating_history.append([player.rating])
        player.record.append([])
        transfer( player, 1000 )
        save_account_to_db( player )
    return load_account_from_db( player.username ), is_new_tournament


######### Betting functions
#enter match bets and passes on the text for logging
def enter_bets( winner, loser, bets ):
    winner = load_account_from_db( winner.username )
    loser = load_account_from_db( loser.username )
    bank = load_account_from_db( 'bank' )
    wb = 'winner_bets={'
    lb = 'loser_bets={'
    err_txt = ""
    
    for b in bets:
        print('b', b)
        print( 'winner', winner.username )
        print( 'loser', loser.username )
        if b[1] == winner.username:
            wb += '\'' + cap_name(b[0]) + '\':'
            player = load_account_from_db( b[0] )
            amount = round(float(b[2]),2)
            wb += str(amount) + ','

            winnings = round( amount*(b[3]-1),2 )
            transfer( player, str(winnings) )
            player.bets.append(['match',cap_name(b[1]),amount,b[3],'W',False])
        
        elif b[1] == loser.username:
            lb += '\'' + cap_name(b[0]) + '\':'
            player = load_account_from_db( b[0] )
            amount = round(float(b[2]),2)
            lb += str(amount) + ','

            transfer( player, str(-amount) )
            player.bets.append(['match',cap_name(b[1]),amount,b[3],'L',False])
    
    if wb[-1]==',':
        wb = wb[:-1]
    if lb[-1]==',':
        lb = lb[:-1]
    wb += '}'
    lb += '}'
    return wb, lb

#Either give money to bank, or take from bank and give it to account
def transfer( player, amount ):
    if cap_name(player.username)=='Bank':
        bank = player
        bank.coin = round( float(amount), 2 ) + round( float(bank.coin), 2 )
        save_account_to_db( bank )
    else:
        bank = load_account_from_db( 'bank' )
        player.coin = round( float(amount), 2) + round( float(player.coin), 2 )
        bank.coin = -round( float(amount), 2) + round( float(bank.coin), 2 )
        player.coin_history[-1].append(player.coin)
        save_account_to_db( player )
        save_account_to_db( bank )

#Redeem coins for a reward
def redeem( account ):
    account.coin-=3000
    account.rewards+=1
    save_account_to_db( account )
    return

#Enter a new tournament bet
def make_tournament_bet( tourn, bet_maker, bet_target, bet_amount ):
    err_txt = ""

    bet_amount = round( float(bet_amount), 2 )
    existing_tbets = tourn.tournament_bets
    bet_target_set = set([ t[1] for t in existing_tbets if t[0]==bet_maker.username ])
    players_existing_tbets = len( bet_target_set )
    t_odds = tourn.initial_odds

    if sum([ t[2] for t in existing_tbets if t[0]==bet_maker.username and t[1]==bet_target.lower() ])+bet_amount<=500:
        if players_existing_tbets<3 or bet_target.lower() in bet_target_set:
            if round( bet_maker.coin, 2)>=bet_amount:
                tourn.tournament_bets.append( [ bet_maker.username, bet_target.lower(), bet_amount, t_odds[bet_target] ] )
                tourn.log += f'tournament_bet( SSBU, \'{cap_name(bet_maker.username)}\', \'{cap_name(bet_target)}\', {bet_amount:.2f}, {t_odds[bet_target]:.2f} )\n'
                transfer( bet_maker, -bet_amount )
                bet_maker = load_account_from_db( bet_maker.username )
                err_txt = f'Tournament bet placed'
                for target in bet_target_set:
                    s = sum( [ t[2] for t in existing_tbets if t[0]==bet_maker.username and t[1]==target.lower() ] )
                    if round( s, 2 )==0:
                        tourn.tournament_bets = [ tb for tb in tourn.tournament_bets if tb[0]!=bet_maker.username or tb[1]!=target.lower() ]
                        err_txt = f'Tournament bets cancelled ({cap_name(target)})'
            else:
                err_txt = f'Insufficient funds ({round( bet_maker.coin, 2)})!'
        else:
            err_txt = f'Maximum 3 tournament bets!'
    else:
        err_txt = f'Tournament bet must be 500 or less ({sum([ t[2] for t in existing_tbets if t[0]==bet_maker.username and t[1]==bet_target.lower() ])+bet_amount:.2f})!'

    save_account_to_db( bet_maker )

    return err_txt, tourn

#AT the end of a tournament give the winning bets their payout
def payout_tournament_bets( tournament ):
    tbets = tournament.tournament_bets
    winner = tournament.winner.lower()
    for tb in tbets:
        if tb[1]==winner:
            winnings = round( tb[2]*tb[3], 2 )
            better = load_account_from_db( tb[0] )
            transfer( better, winnings )

#Enter a new match bet
def make_match_bet( tourn, bet_maker, bet_target, bet_amount ):
    err_txt = ""

    bet_amount = round( float(bet_amount), 2 )
    for i, m in enumerate(tourn.matches):
        if bet_target in m and (m[2]==None or m[2]=='closed'):
            match_idx = i
            if bet_target==m[0]:
                bet_opponent = load_account_from_db( m[1] )
            else:
                bet_opponent = load_account_from_db( m[0] )

    existing_mbets = tourn.match_bets[match_idx]
    players_existing_mbets = [ t for t in existing_mbets if t[0]==bet_maker.username ]
    bet_target_account = load_account_from_db( bet_target )
    m_winrate = exp_winrate( bet_target_account, bet_opponent )
    m_odds = round( 1 / m_winrate, 2 )

    if bet_opponent.username!=bet_maker.username:
        proceed=False
        if not players_existing_mbets:
            proceed=True
        elif players_existing_mbets[0][1]==bet_target.lower():
            proceed=True
        if proceed:
            if sum([mb[2] for mb in players_existing_mbets])+bet_amount<=1000:
                if round( bet_maker.coin, 2)>=bet_amount:
                    if players_existing_mbets and sum([mb[2] for mb in players_existing_mbets])+bet_amount==0:
                        tourn.match_bets[match_idx] = [ mb for mb in tourn.match_bets[match_idx] if mb[0]!=bet_maker.username or mb[1]!=bet_target.lower() ]
                        transfer( bet_maker, -bet_amount )
                        err_txt = f'Match bets cancelled ({cap_name(bet_target)})'
                    else:
                        if tourn.DET.get_active_matches()[-1] in tourn.DET.get_matches()[-2:]:
                            for tb in tourn.tournament_bets:
                                if tb[0]==bet_maker.username and tb[1] in [bet_target.lower, bet_opponent.username]:
                                    proceed=False
                        if proceed:
                            tourn.match_bets[match_idx].append( [ bet_maker.username, bet_target.lower(), bet_amount, m_odds ] )
                            transfer( bet_maker, -bet_amount )
                            bet_maker = load_account_from_db( bet_maker.username )
                            err_txt = f'Match bet placed'
                        else:
                            err_txt = 'You can not bet on a final with an active tournament bet!'
                else:
                    err_txt = f'Insufficient funds ({round( bet_maker.coin, 2)})!'
            else:
                err_txt = f'Match bet must be 1000 or less ({sum([mb[2] for mb in players_existing_mbets])+bet_amount:.2f})!'
        else:
            err_txt = f'Can not bet on more than one player in the same match!'
    else:
        err_txt = f'Can not bet against yourself!'

    save_account_to_db( bet_maker )

    return err_txt, tourn


######### Handicap functions
#get the thist for a players recent handicap record
def update_handicap(player):
    h = flatten(player.rating_history)
    p1 = h[-2] if len(h)>1 else 1500
    p2 = h[-1]
    
    if ( p1 - 50 ) // 100 != ( p2 - 50 ) // 100:

        if p2 > p1 and p2 > 1550 and ( get_max_history( player ) - 50 ) // 100 < ( p2 - 50 ) // 100:
            player.handicap -= ( ( p2 - 50 ) // 100 - max( ( p1 - 50 ) // 100 , 14 ) )
        
        if p2 < p1 and p2 < 1450 and ( get_min_history( player ) - 50 ) // 100 > ( p2 - 50 ) // 100:
            player.handicap += ( ( p1 - 50 ) // 100 - min( ( p2 - 50 ) // 100 , 15 ) )
    
    player.handicap_history[-1].append( player.handicap )
    return player

def get_min_history( player ):
    rh = flatten(player.rating_history)

    y = rh[::-1]
    thresh = 1550
    ratings = []
    for idx, val in enumerate(y):
        if val < 1550:
            ratings.append(val)
        else:
            break
    if ratings==[]:
        return 1550
    else:
        return min(ratings)

def get_max_history( player ):
    rh = flatten(player.rating_history)

    y = rh[::-1]
    thresh = 1450
    ratings = []
    for idx, val in enumerate(y):
        if val < 1450:
            ratings.append(val)
        else:
            break
    if ratings==[]:
        return 1450
    else:
        return max(ratings)


######### Check functions
#check whether string is of a float
def isfloat(s):
    if s=='':
        return True
    try:
        float(s)
        return True
    except ValueError:
        return False

def isint(s):
    if s=='':
        return True
    try:
        int(s)
        return True
    except ValueError:
        return False

def isbool(s):
    if s=='':
        return True

    if s=='True' or s=='False':
        return True
    else:
        return False

def islist(s):
    if s=='':
        return True
    if s[0]=='[' and s[-1]==']':
        return True
    else:
        return False


######## General functions
#need this to flatten the lists the data is stored as
def flatten(t):
    return [item for sublist in t for item in sublist]


######### Plotting functions
#can generate plot for any history attribute an account may have
def generate_hist_plot( account, attrname ):
    fig = plt.figure()
    ax = fig.add_subplot(111)
    
    h = getattr(account, f'{attrname}_history' )
    tourns = account.tournaments

    length = max(map(len, h)) if len(h)>0 else 0
    h=np.array([xi+[np.nan]*(length-len(xi)) for xi in h])
    h = h.flatten()
    xs = np.arange(len(h))
    hmask = np.isfinite(h)
    
    if len(h)>0:
        ax.plot( xs[hmask], h[hmask], color = 'b'  )
        plt.xticks(np.arange(0, len(tourns)*(length), length), labels=tourns, rotation='vertical')
    ax.set_ylabel( attrname, fontsize=20)
    plt.grid(linestyle='--')
    plt.tight_layout()
    return fig    

#plot the game played and the win percentage against any other account they have played against
def matchup_plot( account ):

    record = flatten(account.record)  
    name_set = list(set(m[1] for m in record))
    win_rates = []
    games_played = []
    
    for _, name in enumerate(name_set):
        wins=0
        games=0
        for m in record:
            if m[1]==name:
                games+=1
                if m[0]=='W':
                    wins+=1
        win_rates.append( 0 if games==0 else 100*wins/games )
        games_played.append( games )
        
    name_set_sorted = [x for _, x in sorted(zip(win_rates, name_set))]
    games_played_sorted = [ games_played[name_set.index(name)] for name in name_set_sorted]
    win_rates_sorted = [ win_rates[name_set.index(name)] for name in name_set_sorted]
    
    fig = plt.figure()
    _ = fig.add_subplot(211)
    plt.bar( name_set_sorted, games_played_sorted )
    plt.ylabel('Games played')
    plt.xticks(rotation=90)
    plt.grid(linestyle='--')

    _ = fig.add_subplot(212)
    plt.plot( name_set_sorted, win_rates_sorted )
    plt.ylabel( 'Your win percentage (%)' )
    plt.xticks(rotation=90)
    plt.grid(linestyle='--')
    plt.xlabel('Played against')
    plt.tight_layout()
    
    return fig

#pass the fig to html in a way it can plot it
#don't really understand but copied from stackoverflow
def convert_fig_to_png( fig ):
    pngImage = io.BytesIO()
    FigureCanvas(fig).print_png(pngImage)
    
    # Encode PNG image to base64 string
    pngImageB64String = "data:image/png;base64,"
    pngImageB64String += base64.b64encode(pngImage.getvalue()).decode('utf8')
    return pngImageB64String

#different colours for text
class colour:
   PURPLE = '\033[95m'
   CYAN = '\033[96m'
   DARKCYAN = '\033[36m'
   BLUE = '\033[94m'
   GREEN = '\033[92m'
   YELLOW = '\033[93m'
   RED = '\033[91m'
   BOLD = '\033[1m'
   UNDERLINE = '\033[4m'
   END = '\033[0m'

def cap_name( name ):
    s = name.split('-')
    s = [ x.capitalize() for x in s ]
    return "-".join(s)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)