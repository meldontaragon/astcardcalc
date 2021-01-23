from datetime import timedelta

class Player:
    def __init__(self, id, name, job):
        self.id = id
        self.name = name
        self.job = job

class Pet:
    def __init__(self, id, name, owner):
        self.id = id
        self.name = name
        self.owner = owner

class ActorList:
    def __init__(self, players: dict, pets: dict):
        self.players = players
        self.pets = pets

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

    def GetPlayerID(self, name):
        for i, p in self.players.items():
            if p.name == name:
                return i
        return -1

class CardPlay:
    def __init__(self, start: int, end: int, source: int, target: int, id: int):
        self.start = start
        self.end = end
        self.source = source
        self.target = target
        self.id = id

        self.name = CardPlay.Name(id)
        self.type = CardPlay.Type(id)
        self.bonus = CardPlay.Bonus(id)

    def __str__(self):
        return '{} played {} on {} at {}'.format(self.source, self.name, self.target, self.start)

    def String(self, player_list, start_time):
        return '{} played {} on {} at {}'.format(player_list[self.source]['name'], self.name, player_list[self.target]['name'], str(timedelta(milliseconds=(self.start-start_time)))[2:11])


    @staticmethod
    def Name(id):
        return {
            1001876: 'Lord of Crowns',
            1001877: 'Lady of Crowns',
            1001882: 'The Balance',
            1001884: 'The Arrow',
            1001885: 'The Spear',
            1001883: 'The Bole',
            1001886: 'The Ewer',
            1001887: 'The Spire',
        } [id]

    @staticmethod
    def Type(id):
        return {
            1001876: 'melee',
            1001877: 'ranged',
            1001882: 'melee',
            1001884: 'melee',
            1001885: 'melee',
            1001883: 'ranged',
            1001886: 'ranged',
            1001887: 'ranged',
        } [id]

    @staticmethod
    def Bonus(id):
        return {
            1001876: 1.08,
            1001877: 1.08,
            1001882: 1.06,
            1001884: 1.06,
            1001885: 1.06,
            1001883: 1.06,
            1001886: 1.06,
            1001887: 1.06,
        } [id]

class SearchWindow:
    def __init__(self, start, end, duration, step):
        self.start = start
        self.end = end
        self.duration = duration
        self.step = step

class BurstWindow:
    def __init__(self, start, end):
        self.start = start
        self.end = end

class DrawWindow(BurstWindow):
    def __init__(self, start, end, startEvent, endEvent):
        self.start = start
        self.end = end
        self.startEvent = startEvent
        self.endEvent = endEvent

    def Duration(self):
        return(timedelta(self.end-self.start).total_seconds)

    @staticmethod
    def Name(id):
        return {
            -1: 'Fight End',
            0: 'Fight Start',
            3590: 'Draw',
            16552: 'Divination',
            7448: 'Sleeve Draw',
            3593: 'Redraw',
        }[id]

class FightInfo:
    def __init__(self, report_id, fight_number, start_time, end_time):
        self.id = report_id
        self.index = fight_number
        self.start = start_time
        self.end = end_time

    def Duration(self, time = None):
        if time is not None:
            return timedelta(milliseconds=(time-self.start)).total_seconds()
        else:
            return timedelta(milliseconds=(self.end-self.start)).total_seconds()

    def TimeElapsed(self, time = None):
        if time is not None:
            return str(timedelta(milliseconds=(time-self.start)))[2:11]
        else:
            return str(timedelta(milliseconds=(self.end-self.start)))[2:11]

class BurstDamageCollection:
    def __init__(self, list, duration):
        self.list = list
        self.duration = duration

    # this returns a tuple with the (timestamp, id, damage) set which is the
    # max 
    def GetMax(self, id=None, time=None):
        # if an ID is given then return the max damage done 
        # by that person over the duration defined by the collection

        if time is not None:
            if time in self.list:
                if id is not None:
                    # print('Getting max value for {} at {}'.format(id,time))
                    return (time, id, self.list[time][id])
                else:
                    # print('Getting max value for any actor at {}'.format(time))
                    max_item = sorted(self.list[time].items(), key=lambda dmg: dmg[1], reverse=True )[0]
                    return(time, max_item[0], max_item[1])
            else:
                return (time, 0, 0)
        else:
            if id is not None:
                # get the timestamp where they did the most damage
                # print('Getting max value for {}'.format(id))
                max_item = sorted(self.list.items(), key=lambda dmg: dmg[1][id], reverse=True)[0]
            # otherwise return the max damage done by anyone
            else:
                # print('Getting max value for any actor')
                # get the timestamp where the most damage was done by anyone
                max_item = sorted(self.list.items(), key=lambda dmg: sorted(dmg[1].items(), key=lambda ids: ids[1], reverse=True)[0][1], reverse=True)[0]
                # get the id of the person who did the most damage at that time
                id = sorted(max_item[1].items(), key=lambda item: item[1], reverse=True)[0][0]
            return (max_item[0], id, max_item[1][id])