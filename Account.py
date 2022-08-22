#Account class with name and rating
class Account:
    def __init__(self, username, password, **kwargs):
        self.username = username                                            #Account username
        self.password = password                                            #account password
        self.isadmin = kwargs.get('isadmin',False)                          #Do they have admin priveliges
        self.rating = kwargs.get('rating',1500)                             #Elo rank
        self.bets = kwargs.get('bets',[])                                   #Bets made by this account 
        self.coin = kwargs.get('coin',0)                                    #Currency that can be bet on games
        self.coin_history = kwargs.get('coin_history',[])                   #History of bets over time
        self.rewards = kwargs.get('rewards',0)                              #Tally of redeemed coins for rewards
        self.tournaments = kwargs.get('tournaments',[])                     #List of tournaments participated in
        self.tournament_wins = kwargs.get('tournament_wins',0)              #How many overall wins of an entire tournament
        self.rating_history = kwargs.get('rating_history',[])               #Elo rank over time
        self.handicap = kwargs.get('handicap',0)                            #Player handicap
        self.handicap_history = kwargs.get('handicap_history',[])           #Handicap over time
        self.record = kwargs.get('record', [])                              #Wins and losses and who against
        self.show = kwargs.get('show',True)                                 #Switch to False to stop plotting
