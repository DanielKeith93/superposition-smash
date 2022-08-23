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
from werkzeug.security import generate_password_hash, check_password_hash

current_dir = os.getcwd()

#run by typing "python -m flask run" in terminal
app = Flask(__name__)
app.secret_key = "There is rain outside"
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
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
    account = db.Column(db.PickleType(), nullable=True)

    def __init__(self, name, account):
        self.name = name
        self.account = account

db.create_all()

'''
# How to: add details to database
# Create user
adder = Account_db('Daniel', ExampleObject(3,4))
# adder.add_python_object(ExampleObject(3,4))

# Add to database
db.session.add(adder)
db.session.commit()

# Retrieve python object
account = Account_db.query.filter_by(name='Daniel').first()
result = account.account.does_something_from_storage()

print( account.name, result )
'''

######### HTML routes
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                          'favicon.ico',mimetype='image/vnd.microsoft.icon')

@app.route("/", methods=['GET', 'POST'])
def index():
    user_name = request.form.get("user_name", "").lower()
    password = request.form.get("password", "")
    if user_name and password:
        txt = login_account( user_name, password )
        if txt=='Login successful':
            session['user_name'] = user_name
            return account_stats( user_name )
        else:
            return render_template('index.html', debug_message=txt )
    else:
        return render_template('index.html')

#show a list of previous and active touornaments that can be viewed or joined respectively
@app.route("/<user_name>/tournaments_list", methods=['GET', 'POST'])
def tournaments_list( user_name ):

    check_if_logged_in( user_name )

    kwargs = dict()
    kwargs['user_name'] = user_name

    new_tournament_name = request.form.get("new_tournament_name", "")
    if new_tournament_name:
        txt = create_tournament( new_tournament_name )
        kwargs['debug_message'] = txt

    kwargs['live_tourns'] = get_all_live_tournaments()
    kwargs['previous_tourns'] = get_all_previous_tournaments()

    #only allow to manage accounts if user is admin
    account = load_account( user_name )
    if account.isadmin:
        kwargs['visibility']="visible"
    else:
        kwargs['visibility']="hidden"

    return render_template('tournaments_list.html', **kwargs)

#show details for a specific tournament
@app.route("/<user_name>/<tournament_name>/live", methods=['GET', 'POST'])
def live_tournament_details( user_name, tournament_name ):

    check_if_logged_in( user_name )

    kwargs = dict()
    kwargs['user_name'] = user_name
    account = load_account( user_name )
    kwargs['tournament'] = load_tournament( tournament_name )
    kwargs['tournament_name'] = kwargs['tournament'].name

    if "submit_button" in request.form:
        if request.form['submit_button']=="active":
            if kwargs['user_name'] not in kwargs['tournament'].active_participants:
                kwargs['tournament'].active_participants.append( kwargs['user_name'] )
            if kwargs['user_name'] in kwargs['tournament'].passive_participants:
                kwargs['tournament'].passive_participants.remove( kwargs['user_name'] )

        elif request.form['submit_button']=="passive":
            if kwargs['user_name'] not in kwargs['tournament'].passive_participants:
                kwargs['tournament'].passive_participants.append( kwargs['user_name'] )
            if kwargs['user_name'] in kwargs['tournament'].active_participants:
                kwargs['tournament'].active_participants.remove( kwargs['user_name'] )

        elif request.form['submit_button']=="start_tournament":
            if len(kwargs['tournament'].active_participants)>1:
                kwargs['tournament'] = start_tournament( kwargs['tournament'] )
                kwargs['tournament'] = calculate_tournament_odds( kwargs['tournament'] )
            else:
                kwargs['debug_message'] = f"Not enough active participants! ({len(kwargs['tournament'].active_participants)})"

        elif request.form['submit_button']=="new_match_result" and kwargs['tournament'].DET is not None:
            kwargs['debug_message'], kwargs['tournament'] = enter_new_match_result( request.form, kwargs['tournament'] )

        elif request.form['submit_button']=="close_tournament":
            kwargs['tournament'].live = False

    kwargs['tournament_odds_txt'] = ""
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

    kwargs['active_match_txts'], kwargs['stats'], kwargs['left_txts'], kwargs['right_txts'] = [""], [""], [""], [""]
    kwargs['active_players'] = []
    if kwargs['tournament'].DET is not None:
        kwargs['active_players'] = get_active_players( kwargs['tournament'] )
        txts, stats, left_txts, right_txts = get_active_matches_and_stats( kwargs['tournament'] )
        kwargs['active_match_txts'] = txts
        kwargs['stats'] = stats
        kwargs['left_txts'] = left_txts
        kwargs['right_txts'] = right_txts

    kwargs['passive_participants'] = [ cap_name(x) for x in kwargs['tournament'].passive_participants ]
    kwargs['active_participants'] = [ cap_name(x) for x in kwargs['tournament'].active_participants ]

    save_tournament( kwargs['tournament'] )        

    #decide what is to be shown in the live tournament template
    kwargs['admin_visibility'] = "hidden"
    kwargs['close_visibility'] = "hidden"
    if account.isadmin:
        kwargs['admin_visibility'] = "visible"
        if kwargs['tournament'].winner:
            kwargs['close_visibility'] = "visible"
            kwargs['admin_visibility'] = "hidden"

    return render_template('live_tournament_details.html', **kwargs)

#show details for a specific tournament
@app.route("/<user_name>/<tournament_name>/previous", methods=['GET', 'POST'])
def previous_tournament_details( user_name, tournament_name ):

    check_if_logged_in( user_name )

    kwargs = dict()
    kwargs['user_name'] = user_name
    kwargs['tournament'] = load_tournament( tournament_name )
    kwargs['tournament_name'] = kwargs['tournament'].name

    tb_txt = ""
    tb = kwargs['tournament'].tournament_bets
    name_set = set([ x[0] for x in tb ])
    for n in name_set:
        tb_txt += f'<strong>{cap_name(n)}</strong><br>'
        for x in tb:
            if x[0]==n:
                tb_txt += f'{cap_name(x[1])}: {x[2]}<br>'
        tb_txt += '<br>' 

    mb_txt = ""
    ms = kwargs['tournament'].matches
    mb = kwargs['tournament'].match_bets
    for idx, m in enumerate(ms):
        mb_txt += f"<strong>{cap_name(m[0])} def {cap_name(m[1])} (MOV: {m[2]})</strong><br>"
        if mb:
            for b in mb[idx]:
                mb_txt += f'{cap_name(b[0])} ({cap_name(b[1])}): {b[2]}<br>'
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

    return render_template('previous_tournament_details.html', **kwargs)

#Remove the user account from the session and logout
@app.route('/logout', methods=['GET', 'POST'])
def logout():
   # remove the username from the session if it is there
   session.pop('user_name', None)
   return redirect(url_for('index'))

@app.route("/<user_name>", methods=['GET', 'POST'])
def account_stats( user_name ):

    check_if_logged_in( user_name )

    kwargs = dict()
    kwargs['debug_message']=''
    account = load_account( user_name )

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
            save_account( account )
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

    check_if_logged_in( user_name )

    kwargs = dict()
    kwargs['user_name'] = user_name
    kwargs['debug_message'] = ''

    kwargs['account_list'] = get_account_list()

    account_name = request.form.get("account_name", "")
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

    if account_name!="":
        account = load_account( account_name )

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

        save_account( account )

    elif new_account_name != "":

        if not account_exist( new_account_name ):
            new_account = create_account( new_account_name, password='password' )
        else:
            kwargs['debug_message'] = f'Account already exists: {new_account_name}'

    return render_template('manage_accounts.html', **kwargs )


####### Account and login functions
#check the session to see if the user has logged in
def check_if_logged_in( user_name ):
    if 'user_name' not in session:
        return redirect(url_for('index'))
    elif session['user_name'] != user_name:
        return redirect(url_for('index'))

#create a new account
def create_account( username, password ):
    username = username.lower()
    password = generate_password_hash(password)
    if not account_exist( username ): #check whether username already exists
        account = Account( username, password )
        save_account( account )
        return "Account created successfully"
    else:
        return "Account already exists"

#check whether account already exists
def account_exist( username ):
    for filename in os.listdir('accounts'): #check the username of all existing accounts
        f = os.path.join('accounts', filename)
        if os.path.isfile(f):
            account = load_account( filename[:-4] )
            if username == account.username:
                return True
    return False

#check whether password is correct for particular account
def password_correct( username, password ):
    account = load_account( username )
    if username==account.username and check_password_hash( account.password, password ):
        return True
    return False

#login into existing account
def login_account( username, password ):
    username = username.lower()
    if account_exist( username ): #make sure account exists
        if password_correct( username, password ):
            return "Login successful"
        else:
            return "Incorrect password!"
    else:
        return f"Account does not exist: {username}!"

#return the class object for a given account username
def load_account( username ):
    with open( f'accounts/{username}.txt', 'rb' ) as file:
        username = pickle.load( file )
    return username

#overwrite textfile with updated account stats and attributes
def save_account( account ):
    with open( f'accounts/{account.username}.txt', 'wb' ) as file:
        pickle.dump(account, file)

#get list of all the names of existing accounts
def get_account_list():
    accounts_list = [ f[:-4] for f in os.listdir('accounts/') ]
    return accounts_list

#calculate win rate for a given pair of players
def exp_winrate( player1, player2 ):
    difference = ( player1.rating + 50 * player1.handicap ) - ( player2.rating + 50 * player2.handicap )
    return 1 / ( 1 + 10 ** ( - difference / 400 ) )


######### Tournament functions
#check whether tournament already exists
def tournament_exist( name ):
    for filename in os.listdir('tournaments'): #check the name of all existing tournaments
        f = os.path.join('tournaments', filename)
        if os.path.isfile(f):
            tournament = load_tournament( filename[:-4] )
            if name == tournament.name:
                return True
    return False

#create a new tournament
def create_tournament( name ):
    if not tournament_exist( name ): #check whether username already exists
        tournament = Tournament( name, live=True )
        save_tournament( tournament )
        return "Tournament created successfully"
    else:
        return f"Tournament already exists! ({name})"

#return the class object for a given tournament name
def load_tournament( name ):
    with open( f'tournaments/{name}.txt', 'rb' ) as file:
        name = pickle.load( file )
    return name

def rangeBase1(length):
    return [i + 1 for i in range(length)]

def start_tournament( tournament ):
    names = tournament.active_participants
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
            player_i = load_account( player_dict[i+1] )
            player_j = load_account( player_dict[j+1] )
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

#overwrite textfile with updated tournament data
def save_tournament( tournament ):
    with open( f'tournaments/{tournament.name}.txt', 'wb' ) as file:
        pickle.dump(tournament, file)

def get_all_previous_tournaments():
    previous_tourns = []
    directory = 'tournaments/'
    for filename in os.listdir(directory):
        name = filename[:-4]
        tourn = load_tournament( name )
        if not tourn.live:
            previous_tourns.append(tourn)
    previous_tourns.sort(key=lambda x: datetime.datetime.strptime(x.date, '%d-%m-%Y')) #sort by chronological order
    return previous_tourns[::-1]

def get_all_live_tournaments():
    live_tourns = []
    directory = 'tournaments/'
    for filename in os.listdir(directory):
        name = filename[:-4]
        tourn = load_tournament( name )
        if tourn.live:
            live_tourns.append(tourn)
    live_tourns.sort(key=lambda x: datetime.datetime.strptime(x.date, '%d-%m-%Y')) #sort by chronological order
    return live_tourns[::-1]


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
    for m in active_matches:
        player1 = load_account( player_dict[m.get_participants()[0].get_competitor()] )
        player2 = load_account( player_dict[m.get_participants()[1].get_competitor()] )
        txts.append( f"<strong>{cap_name(player1.username)}</strong> vs <strong>{cap_name(player2.username)}</strong><br>" )

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

    if tourn.get_winners():
        txts.append( f'{ player_dict[tourn.get_winners()[0]] } won the tournament!' )
        stats.append( "" )
        left_txts.append( "" )
        right_txts.append( "" )
    
    return txts, stats, left_txts, right_txts

#Enter new results to progress the tournament
def enter_match( tournament, winner, loser, mov ):
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
    
    check_if_new_tournament( tournament, winner )
    check_if_new_tournament( tournament, loser )

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
            tournament.matches.append( [ cap_name(winner.username) ,cap_name(loser.username), mov ] )
            #if end of the tournament -> add tournament win
            if det.get_winners():
                winner.tournament_wins += 1
                tournament.winner = cap_name(winner.username)

    tournament.DET = det

    save_account( winner )
    save_account( loser )

    return tournament

def enter_new_match_result( form, tourn ):
    debug = ""
    winner = form.get("new_winner", "").lower()
    if winner!="":
        winner = load_account( winner )
        loser = form.get("new_loser", "").lower()
        if loser!="":
            loser = load_account( loser )
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
    elif player.tournaments[-1]!=tourn.name:
        is_new_tournament = True
    else:
        is_new_tournament = False 
    if is_new_tournament:
        player.tournaments.append(tourn.name)
        player.coin_history.append([])
        player.handicap_history.append([])
        player.rating_history.append([])
        player.record.append([])
    return player

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