from datetime import timedelta
import pandas as pd

class CardCalcException(Exception):
    pass

class Player:
    def __init__(self, id, name, job):
        self.id = id
        self.name = name
        self.job = job
        self.role = Player.GetRole(job)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'job': self.job,
            'role': self.role,
            'owner': self.id,
        }

    @staticmethod
    def GetRole(job):
        if job in {'DarkKnight', 'Gunbreaker', 'Warrior','Paladin', 'Dragoon', 'Samurai', 'Ninja', 'Monk', 'Reaper'}:
            return 'melee'
        if job in {'Machinist', 'Dancer', 'Bard', 'WhiteMage', 'Scholar', 'Astrologian', 'Summoner', 'BlackMage', 'RedMage', 'Sage'}:
            return 'ranged'
        if job in {'LimitBreak', 'Limit Break'}:
            return 'LimitBreak'
        return 'n/a'

class Pet:
    def __init__(self, id, name, owner):
        self.id = id
        self.name = name
        self.owner = owner

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'job': 'pet',
            'role': 'pet',
            'owner': self.owner
        }

class ActorList:
    def __init__(self, players: dict, pets: dict):
        self.players = players
        self.pets = pets

        actors = []
        for _, player in players.items():
            actors.append(player.to_dict())
        
        for _, pet in pets.items():
            actors.append(pet.to_dict())
        
        self.actors = pd.DataFrame(actors)
        self.actors.set_index('id', drop=False, inplace=True)

    def to_dict(self):
        return self.actors.to_dict(orient='index')

    def PrintAll(self):
        tabular = '{:<24}{:>4}  {}'
        print('Players')
        print(tabular.format('Name','ID','Job'))
        print('-'*40)
        for _, p in self.players.items():
            print(tabular.format(p.name, p.id, p.job))

        print('\n')
        print('Pets')
        print(tabular.format('Name','ID','Owner'))
        print('-'*40)
        for _, p in self.pets.items():
            print(tabular.format(p.name, p.id, self.players[p.owner].name))

    def PrintPlayers(self):
        tabular = '{:<24}{:>4}  {}'
        print('Players')
        print(tabular.format('Name','ID','Job'))
        print('-'*40)
        for _, p in self.players.items():
            print(tabular.format(p.name, p.id, p.job))

    def PrintPets(self):
        tabular = '{:<24}{:>4}  {:>5}  {}'
        print('Pets')
        print(tabular.format('Name','ID','OID','Owner'))
        print('-'*40)
        for _, p in self.pets.items():
            print(tabular.format(p.name, p.id, p.owner, self.players[p.owner].name))

    def GetPlayerID(self, name):
        for i, p in self.players.items():
            if p.name == name:
                return i
        return -1

class CardPlay:
    def __init__(self, cast: int = 0, start: int = 0, end: int = 0, source: int = 0, target: int = 0, buffId: int = 0, castId: int = 0):        
        self.cast = cast
        self.start = start
        self.end = end
        self.source = source
        self.target = target

        if buffId != 0:
            self.buffId = buffId
            self.castId = CardPlay.ConvertID(buffId = buffId)
        elif castId != 0:
            self.castId = castId
            self.buffId = CardPlay.ConvertID(castId = castId)
        else:
            self.buffId = buffId
            self.castId = castId

        self.id = self.buffId

        self.name = CardPlay.GetName(self.id)
        self.role = CardPlay.GetRole(self.id)
        self.bonus = CardPlay.GetBonus(self.id)

    def __str__(self):
        return f'{self.source} played {self.name} on {self.target} at {self.start}'

    def to_dict(self): 
        return {
            'source': self.source,
            'target': self.target,
            'type': 'play',
            'cast': self.cast,
            'start': self.start,
            'end': self.end,
            'id': self.id,
            'name': self.name,
            'role': self.role,
            'bonus': self.bonus,
        }

    def String(self, player_list, start_time):
        return '{} played {} on {} at {}'.format(player_list[self.source]['name'], self.name, player_list[self.target]['name'], str(timedelta(milliseconds=(self.start-start_time)))[2:11])

    @staticmethod
    def ConvertID(buffId = 0, castId = 0):
        if buffId == 0 and castId == 0:
            return 0
        elif buffId != 0:
            return {
                1001882: 4401,
                1001883: 4404,
                1001884: 4402,
                1001885: 4403,
                1001886: 4405,
                1001887: 4406,
                0: 'None',
            } [buffId]
        elif castId != 0:
            return {
                4401: 1001882,
                4404: 1001883,
                4402: 1001884,
                4403: 1001885,
                4405: 1001886,
                4406: 1001887,
                0: 'None',
            } [castId] 
        else:
            return 0

    @staticmethod
    def GetName(buffId, castId = 0):
        if buffId == 0 or castId != 0:
            return {
                4401: 'The Balance',
                4402: 'The Arrow',
                4403: 'The Spear',
                4404: 'The Bole',
                4405: 'The Ewer',
                4406: 'The Spire',
                0: 'None',
            } [castId]
        else:
            return {
                1001882: 'The Balance',
                1001884: 'The Arrow',
                1001885: 'The Spear',
                1001883: 'The Bole',
                1001886: 'The Ewer',
                1001887: 'The Spire',
                0: 'None',
            } [buffId]

    @staticmethod
    def GetRole(id):
        return {
            1001882: 'melee',
            1001884: 'melee',
            1001885: 'melee',
            1001883: 'ranged',
            1001886: 'ranged',
            1001887: 'ranged',
            0: 'none',
        } [id]

    @staticmethod
    def GetBonus(id):
        return {
            1001882: 1.06,
            1001884: 1.06,
            1001885: 1.06,
            1001883: 1.06,
            1001886: 1.06,
            1001887: 1.06,
            0: 0,
        } [id]

class SearchWindow:
    def __init__(self, start, end, duration, step):
        self.start = start
        self.end = end
        self.duration = duration
        self.step = step

class DrawWindow:
    def __init__(self, source = 0, start = 0, end = 0, castId = -2, buffId = 0):
        self.source = source
        self.start = start
        self.end = end

        self.castId = castId
        self.buffId = buffId

        self.startEvent = None
        self.endEvent = None
        
        if self.buffId != 0:
            self.cardDrawn = DrawWindow.GetCard(self.buffId)
        if self.buffId != 0 and self.castId == -2:
            # print("BuffID set but no CastID set at {}".format(self.start))
            self.startEvent = DrawWindow.GetBuff(self.buffId)
        if self.castId != -2:
            self.startEvent = DrawWindow.GetName(self.castId)

        if self.castId != -2:
            self.startId = self.castId
        elif buffId != 0:
            self.startId = DrawWindow.ConvertID(self.buffId)
        else:
            self.startId = -1
        
        self.endId = None
        
    def __str__(self):
        return f'From {self.startEvent} at {self.start} to {self.endEvent} at {self.end}'

    def to_dict(self): 
        return {
            'source': self.source,
            'type': 'draw',
            'start': self.start,
            'end': self.end,
            'startEvent': self.startEvent,
            'endEvent': self.endEvent
        }

    def Duration(self):
        return(timedelta(self.end-self.start).total_seconds)

    @staticmethod
    def GetName(id):
        return {
            -1: 'Fight End',
            0: 'Fight Start',
            3590: 'Draw',
            16552: 'Divination',
            3593: 'Redraw', # TODO: Need to check if this is still the correct ID for Redraw
        }[id]

    @staticmethod
    def GetCard(buffId):
        return {
            1000913: 'The Balance',
            1000914: 'The Bole',
            1000915: 'The Arrow',
            1000916: 'The Spear',
            1000917: 'The Ewer',
            1000918: 'The Spire'
        }[buffId]

    @staticmethod
    def ConvertID(buffId):
        return {
            1000913: 4401,
            1000914: 4404,
            1000915: 4402,
            1000916: 4403,
            1000917: 4405,
            1000918: 4406,
        }[buffId]

    @staticmethod
    def GetBuff(buffId):
                return {
            1000913: 'Balance Drawn',
            1000914: 'Bole Drawn',
            1000915: 'Arrow Drawn',
            1000916: 'Spear Drawn',
            1000917: 'Ewer Drawn',
            1000918: 'Spire Drawn'
        }[buffId]

class FightInfo:
    def __init__(self, report_id, fight_number, start_time, end_time, name, kill):
        self.id = report_id
        self.index = fight_number
        self.start = start_time
        self.end = end_time
        self.kill = kill
        self.name = name

    def to_dict(self):
        return {
            'id': self.id,
            'index': self.index,
            'start': self.start,
            'end': self.end,
            'kill': self.kill,
            'name': self.name,
            'duration': self.Duration(),
            'length': self.ToString(),
        }

    def Duration(self, time = None):
        if time is not None:
            return timedelta(milliseconds=(time-self.start)).total_seconds()
        else:
            return timedelta(milliseconds=(self.end-self.start)).total_seconds()

    def ToString(self, time = None):
        if time is not None:
            return str(timedelta(milliseconds=(time-self.start)))[2:11]
        else:
            return str(timedelta(milliseconds=(self.end-self.start)))[2:11]

    def PrintDamageObject(self, actor_list, damage_obj):
        format_string = '{:>9}   {:<25}...{:>9}'
        print(format_string.format(self.TimeElapsed(damage_obj[0]), actor_list.actors.loc[damage_obj[1], 'name'], damage_obj[2] ))

    def TimeElapsed(self, time = None):
        if time is not None:
            return time-self.start
        else:
            return self.end-self.start

    def TimeDelta(self, time):
        return timedelta(milliseconds=(time - self.start))

class BurstDamageCollection:
    def __init__(self, df, duration):
        self.df = df
        self.duration = duration

    # this returns a tuple with the (timestamp, id, damage) set which is the
    # max 
    def get_max(self, pid=None, time=None, limit=0):
        # Options:
        # (1) if there is no time and no id then find overall max
        # (2) if there is no time but an id then find max for that id
        # (3) if a time is specified then check if it's valid and find the
        #     overall max at that time
        # (4) if there is a time and a player then return their damage at that
        #     timestamp assuming it's valid

        # if a limit is provided (limit > 0) then only search values less than the limit
        # TODO: this is actually really slow, would like to improve it
        if limit > 0:
            # array = np.array(self.df.values.tolist())
            # mod_df = pd.DataFrame(np.where(array > limit, 0, array).tolist(), index=self.df.index, columns=self.df.columns)
            mod_df = self.df.apply(lambda x: [y if y < limit else 0 for y in x])
        else:
            mod_df = self.df

        max_dmg = 0
        if time is None and pid is None:
            # get overall max damage, person, and time
            pid = mod_df.max(axis=0).idxmax()
            time = mod_df.max(axis=1).idxmax()
            max_dmg = mod_df.loc[time, pid]
        elif pid is None and time is not None and time in mod_df.index.values:
            # get max damage and the person for this time
            pid = mod_df.loc[time, :].idxmax()
            max_dmg = mod_df.loc[time, pid]
        elif pid is not None and pid in mod_df.columns.values and time is None:
            # get the max damage done by this person and at what time
            time = mod_df[pid].idxmax()
            max_dmg = mod_df.loc[time, pid]
        elif pid is not None and pid in mod_df.columns.values and time is not None and time in mod_df.index.values:
            # return the damage at time done by the given player
            max_dmg = mod_df.loc[time, pid]
        else:
            # some error
            time = 0
            pid = 0
            max_dmg = 0

        return [int(time), int(pid), int(max_dmg)]