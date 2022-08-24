from datetime import date

#Tournament class to record the matches that were played and who won
class Tournament:
    def __init__(self, name, **kwargs):
        self.name = name                                                        #(string): unique name of the tournament
        self.date = kwargs.get('date', date.today().strftime('%d-%m-%Y') )      #(datetime): when the tournamnet was created
        self.live = kwargs.get('live', False )                                  #(bool): is the tournament live and ongoing
        self.active_participants = kwargs.get('active_participants', [] )       #(list): competitors in tournament
        self.passive_participants = kwargs.get('passive_participants', [] )     #(list): non-competitors who placed bets
        self.player_dict = kwargs.get('player_dict', {})                        #(dict): players and their index for DET
        self.winner = kwargs.get('winner', None )                               #(string): winner of whole tournamnet
        self.bracket = kwargs.get('bracket', None )                             #(string): match bracket structure
        self.matches = kwargs.get('matches', [] )                               #(list): matches completed
        self.match_bets = kwargs.get('match_bets', [] )                         #(list): bets placed on individual matches
        self.tournament_bets = kwargs.get('tournament_bets', [] )               #(list): bets placed on overall tournament winner
        self.DET = kwargs.get('DET', None )                                     #(DET): tournament object with the recorded matches and results
        self.initial_odds = kwargs.get('initial_odds', {})                      #(dict): players and their odds of winning the whole tournament
        self.log = kwargs.get('log', "")                                        #(string): log of all events that occured during a tournament