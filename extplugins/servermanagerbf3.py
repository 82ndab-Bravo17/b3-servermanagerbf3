# -*- coding: utf-8 -*-
#
# Vehicle Control BF3 Plugin for BigBrotherBot(B3) (www.bigbrotherbot.net)
# Copyright (C) 2011 Freelander (freelander@fps-gamer.net)
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
#
# CHANGELOG
#
# 1.0.0   - Initial release

__version__ = '1.0.0'
__author__  = '82ndab.Bravo17'

import b3
import b3.events
from b3.plugin import Plugin
import time
import random
import b3.cron
from b3.plugin import Plugin
from b3.parsers.frostbite2.protocol import CommandFailedError
from b3.parsers.bf3 import GAME_MODES_NAMES

BF3_MAP_NAMES = {
    "Grand Bazaar": "MP_001",
    "Teheran Highway": "MP_003",
    "Caspian Border": "MP_007",
    "Seine Crossing": "MP_011",
    "Operation Firestorm": "MP_012",
    "Damavand Peak": "MP_013",
    "Noshahr Canals": "MP_017",
    "Kharg Island": "MP_018",
    "Operation Metro": "MP_Subway",
    "Strike At Karkand": "XP1_001",
    "Gulf of Oman": "XP1_002",
    "Sharqi Peninsula": "XP1_003",
    "Wake Island": "XP1_004",
    }



class Servermanagerbf3Plugin(Plugin):

    def __init__(self, console, config=None):
        self._breakpoints = 0
        self._current_rotation_no = 2
        self._rotations = {}
        self._autorotation = True
        self._randomize_rotation = True
        self._adjust_players_settings = True
        self._max_players = 64
        self._current_players_setting = 16
        self._player_counts = {}
        self._delay_player_check = True
        self._breakpoints = 0
        self._ticket_configs = 0
        self._gametype_mults = {}
        self._max_tickets = 100
        self._use_mult = 100
        self._autotickets = True
        self._idle_kick_disable = False
        self._idle_player_count = 0
        self._current_tickets = 0
        self._bps = {}
        self._next_gametype = ''
        self._next_map_name = ''
        self._easy_map_names = {}
        Plugin.__init__(self, console, config)

################################################################################################################
#
#    Plugin interface implementation
#
################################################################################################################

    def onLoadConfig(self):
        """\
        This is called after loadConfig(). Any plugin private variables loaded
        from the config need to be reset here.
        """
        for easy, hard in BF3_MAP_NAMES.iteritems():
            self._easy_map_names[hard] = easy
        configok1 = self._load_map_rotations()
        configok2 = self._load_rotation_settings()
        configok3 = self._load_player_no_settings()
        configok4 = self._load_tickets_settings()
        configok5 = self._load_idle_player_settings()
        
        if configok1 and configok2 and configok3 and configok4 and configok5:
            self.debug('Player manager configs OK')
        else:
            self.debug('Error in Player Manager xml - Please fix')
            self.console.die()
            
        
        
    def startup(self):
        """\
        Initialize plugin settings
        """
        # get the admin plugin so we can register commands
        self._adminPlugin = self.console.getPlugin('admin')
        if not self._adminPlugin:
            # something is wrong, can't start without admin plugin
            self.error('Could not find admin plugin')
            return False
        self._registerCommands()
        # Register our events
        self.registerEvent(b3.events.EVT_GAME_ROUND_START)
        self.registerEvent(b3.events.EVT_GAME_ROUND_END)
        self.registerEvent(b3.events.EVT_CLIENT_AUTH)
        self.registerEvent(b3.events.EVT_CLIENT_DISCONNECT)
        self.debug('Starting player check  delay timer')
        secs =int(time.strftime('%S'))
        mins = 1 + int(time.strftime('%M'))
        if mins > 59:
            mins -= 60
        self._cronTab_delay = b3.cron.OneTimeCronTab(self._start_delay, minute=mins, second=secs)
        self.console.cron + self._cronTab_delay
        self.set_players_setting(self._max_players)
        
    def onEvent(self, event):
        """\
        Handle intercepted events
        """
            
        if event.type == b3.events.EVT_GAME_ROUND_END:
            if self._adjust_players_settings:
                self.set_players_setting(self._max_players)
                
            if not self._delay_player_check:
                self._check_players()
            else:
                self.setticketcount(self._max_tickets)
            
        
        elif event.type == b3.events.EVT_GAME_ROUND_START:
            if self._adjust_players_settings and not self._delay_player_check:
                new_players_setting = self.get_new_players_setting()
                if new_players_setting != self._current_players_setting:
                    self.set_players_setting(new_players_setting)
                    
            if self._autorotation:
                secs = 15 + int(time.strftime('%S'))
                if secs > 59:
                    secs -= 60
                self._cronTab_rotation = b3.cron.OneTimeCronTab(self.show_current_settings, second=secs)
                self.console.cron + self._cronTab_rotation
                
            #reset ticket count to max tickets to avoid hud corruption
            self.setticketcount(self._max_tickets)
                
        elif event.type == b3.events.EVT_CLIENT_AUTH:
            if self._adjust_players_settings and not self._delay_player_check:
                new_players_setting = self.get_new_players_setting()
                if new_players_setting != self._current_players_setting:
                    self.set_players_setting(new_players_setting)
            elif self._idle_kick_disable:
                self._check_idle_setting()
                
        elif event.type == b3.events.EVT_CLIENT_DISCONNECT:
            if self._adjust_players_settings and not self._delay_player_check:
                new_players_setting = self.get_new_players_setting()
                if new_players_setting != self._current_players_setting:
                    self.set_players_setting(new_players_setting)
            elif self._idle_kick_disable:
                self._check_idle_setting()

################################################################################################################
#
#   Commands implementations
#
################################################################################################################

            

    def cmd_autorotation(self, data, client, cmd=None):
        """\
        Turn auto rotation mode on or off 
        """
        if not data:
            if self._autorotation:
                client.message("Auto rotation change is currently on, use !autorotation off to turn off")
            else:
                client.message("Auto rotation change is currently off, use !autorotation on to turn on")
        else:
            if data.lower() == 'off':
                self._autorotation = False
                client.message('Auto rotation change disabled')

            elif data.lower() == 'on':
                self._autorotation = True
                client.message('Auto rotation change is enabled')
        
    def cmd_autoplayercount(self, data, client, cmd=None):
        """\
        Turn auto player count mode on or off 
        """
        if not data:
            if self._adjust_players_settings:
                client.message("Auto adjusy player count is currently on, use !autoplayercount off to turn off")
            else:
                client.message("Auto adjust player count is currently off, use !autoplayercount on to turn on")
        else:
            if data.lower() == 'off':
                self._adjust_players_settings = False
                client.message('Auto adjust player count disabled')
                set_players_setting(self._max_players)

            elif data.lower() == 'on':
                self._adjust_players_settings = True
                client.message('Auto adjust player count is enabled')
                

    def cmd_tickets(self, data, client, cmd=None):
        """\
        Show current ticket count 
        """
        client.message('Current tickets %s' % self._current_tickets)
            

    def cmd_autotickets(self, data, client, cmd=None):
        """\
        Turn auto mode on or off 
        """
        if not data:
            if self._autotickets:
                client.message("Auto ticket count is currently on, use !autotickets off to turn off")
            else:
                client.message("Auto ticket count is currently off, use !autotickets on to turn on")
        else:
            if data.lower() == 'off':
                self._autotickets = False
                client.message('Auto ticket count disabled')
                set_tickets = self.setticketcount(self._max_tickets)
                if set_tickets:
                    self._current_tickets = set_tickets

            elif data.lower() == 'on':
                self._autotickets = True
                client.message('Auto ticket count is enabled')
        
    def cmd_settickets(self, data, client, cmd=None):
        """\
        Set new ticket count 
        """
        self._autotickets = False
        if not data:
            client.message('Invalid or missing data, try !help settickets')
        else:
            self.self._current_tickets = data
            
#################################################################################################################
#
#       Load from config
#
#################################################################################################################

    def _load_map_rotations(self):
        try:
            maps_ok = True
            self._breakpoints = self.config.getint('settings', 'map_rotations')
            self._current_rotation_no = self._breakpoints
            for rot in range(1, self._breakpoints + 1):
                map_configs = self.config.getint('rot_%s' % rot, 'map_count')
                self._rotations[rot] = (self.config.getint('rot_%s' % rot, 'player_count'), map_configs)
                
 
                for map_no in range(1, map_configs + 1):
                    map_info = self.config.get('rot_%s' % rot, 'map%s' % map_no)
                    if self.check_map_info(map_info):
                        self._rotations[rot] = self._rotations[rot] + (map_info,)
                    else:
                        maps_ok = False

            self.debug(self._rotations)
            
            if maps_ok:
                self.info('All map details are OK')
            else:
                self.info('There was an error in the rotation details')
                return False

            
        except Exception, msg:
            self.error('There is an error with your Map Rotations config %s' % msg)
            return False
            
        return True

    def _load_rotation_settings(self):
        try:
            self._autorotation = self.config.getboolean('settings', 'auto_rotation_adjust')
        except Exception, msg:
            self.error('There is an error with your Rotation Manager config %s' % msg)
            return False
            
        self.debug('Auto Rotation changes Enabled: %s' % self._autorotation)

        try:
            self._randomize_rotation = self.config.getboolean('settings', 'randomize')
        except Exception, msg:
            self.error('There is an error with your Rotation Manager config %s' % msg)
            return False
            
        self.debug('Auto Rotation Randomize: %s' % self._randomize_rotation)
        
        try:
            self._max_players = self.config.getint('settings', 'max_players')
        except Exception, msg:
            self.error('There is an error with your Rotation Manager config %s' % msg)
            return False
            
        self.debug('Max Players set to %s' % self._max_players)

        return True
        
    def _load_player_no_settings(self):
        try:
            self._adjust_players_settings = self.config.getboolean('settings', 'adjust_players')
        except Exception, msg:
            self.error('There is an error with your Adjust server player config %s' % msg)
            return False
            
        self.debug('Auto adjust player count set to: %s' % self._adjust_players_settings)

        try:
            player_counts = self.config.get('settings', 'player_counts')
            player_counts_split = player_counts.split(',')
            for ix in range(1, len(player_counts_split) + 1):
                cur_split = player_counts_split[ix-1]
                self._player_counts[ix] =  (cur_split.split(':'))
        except Exception, msg:
            self.error('There is an error with your Adjust server player config %s' % msg)
            return False
            
        self.debug('Player Counts splits set to %s:' % self._player_counts)

        return True
                
    def _load_tickets_settings(self):
        try:
            self._breakpoints = self.config.getint('settings', 'breakpoints')
            self._ticket_configs = self.config.getint('settings', 'ticket_configs')

            for bp in range(1, self._breakpoints + 1):
                self._bps[bp] = (self.config.getint('bp_%s' % bp, 'player_count'),)
                for tc in range(1, self._ticket_configs + 1):
                    self._bps[bp] = self._bps[bp] + (self.config.getint('bp_%s' % bp, 'ticket_multiplier_%s' % tc),)

            self._max_tickets = self.config.getint('settings', 'max_tickets')
            self._current_tickets = self._max_tickets
            self.setticketcount(self._max_tickets)
            self.debug(self._bps)
            self.debug('Using %s as max ticket count' % self._max_tickets)
            
        except Exception, msg:
            self.error('There is an error with your Variable Ticket config %s' % msg)
            return False

        try:
            self._autotickets = self.config.getboolean('settings', 'auto_tickets_adjust')
        except Exception, msg:
            self.error('There is an error with your Variable Ticket config %s' % msg)
            return False
            
        self.debug('Auto Ticket Count Enabled %s:' % self._autotickets)

        try:
            for gm in GAME_MODES_NAMES:
                self._gametype_mults[gm] = (self.config.getint('gtmultipliers', gm))
        except Exception, msg:
            self.error('There is an error with your Variable Ticket config %s' % msg)   
            return False
            
        self.debug(self._gametype_mults)
        
        return True
    
    def _load_idle_player_settings(self):
            
        try:
            self._idle_kick_disable = self.config.getboolean('settings', 'idle_kick_disable')
        except Exception, msg:
            self.error('There is an error with your Idle Kick config %s' % msg)
            return False
            
        self.debug('Idle-disable %s:' % self._idle_kick_disable)
        
        if self._idle_kick_disable:
            try:
                self._idle_player_count = self.config.getint('settings', 'idle_player_count')
            except Exception, msg:
                self.error('There is an error with your Idle Kick config %s' % msg)
                return False
            
            self.debug('Kick Idle player count %s:' % self._idle_player_count)
        
        return True
        

################################################################################################################
#
#    Other methods
#
################################################################################################################

    def _check_players(self):
        '''
        Gets player count and sets tickets based on it
        '''
        clients = self.console.clients.getList()
        _players = len(clients)
        
        if self._autorotation:
            cur_rot = 1
            for rot_num, rots in self._rotations.iteritems():
                if _players > rots[0]:
                    cur_rot = rot_num
                
            self.debug('Next rotation rot_%s' % cur_rot)
            if self._current_rotation_no != cur_rot:
                self.make_rotation(cur_rot)
    
        if self._autotickets:
            cur_bp = 1
            for bp_num, mults in self._bps.iteritems():
                if _players > mults[0]:
                    cur_bp = bp_num
                
            self.debug('Current bp %s' % cur_bp)
            tm_touse = self.get_gt_multiplier()
            self._use_mult = self._bps[cur_bp][tm_touse]
            self.debug('Use mult is %s' % self._use_mult)
                

 
            tickets = self._use_mult * self._max_tickets
            tickets = tickets / 100
            set_tickets = self.setticketcount(tickets)
            if set_tickets:
                self._current_tickets = set_tickets
        else:
            self.setticketcount(self._max_tickets)

    def _registerCommands(self):
        # register our commands
        if 'commands' in self.config.sections():
            for cmd in self.config.options('commands'):
                level = self.config.get('commands', cmd)
                sp = cmd.split('-')
                alias = None
                if len(sp) == 2:
                    cmd, alias = sp
                func = self._getCmd(cmd)
                if func:
                    self._adminPlugin.registerCommand(self, cmd, level, func, alias)
                    
    def _getCmd(self, cmd):
        cmd = 'cmd_%s' % cmd
        if hasattr(self, cmd):
            func = getattr(self, cmd)
            return func
        return None
        

    def make_rotation(self, rot_no):
        rotation_details = self._rotations[rot_no]
        map_count = rotation_details[1]
        # save current rotation
        self.console.write(('mapList.list',))
        no_error = True
        self.console.write(('mapList.clear',))
        index = []
        for ix in range(2, map_count+2):
            index.append(ix)
            
        if self._randomize_rotation:
            random.shuffle(index)
        
        for ix in index:
            rot_map = rotation_details[ix].split(',')
            if rot_map[2] < 1:
                rot_map[2] = 1
                
            try:
                try:
                    self.console.write(('mapList.add', rot_map[0], rot_map[1], rot_map[2]))
                except CommandFailedError, err:
                    if "InvalidMapName" in err.message:
                        try:
                            map_name = BF3_MAP_NAMES[rot_map[0]]
                            self.debug('Map Name %s is %s' % (rot_map[0], map_name))
                            self.console.write(('mapList.add', map_name, rot_map[1], rot_map[2]))
                        except Exception, msg:
                            self.debug('Incorrect Map Name %s in rotation set %s' % (rot_map[1], rot_no))
                            no_error = False
                            
                self.console.write(('mapList.setNextMapIndex', 0))
                            
            except Exception, msg:
                self.debug('Error %s' % msg)
                self.debug('There was an error in rotation element %s in rotation %s' % (ix, rot_no))
                no_error = False
                
        if no_error:
            self.console.write(('mapList.list',))
            self.console.say('Map Rotation set to Rotation %s' % rot_no)
            self._current_rotation_no = rot_no
            return
   
        self.console.say('Error in Rotation %s, Rotation is set to the server default' % rot_no)
        self._current_rotation = 0
        self.console.write(('mapList.load',))
        self.console.write(('mapList.list',))

    def set_players_setting(self, num_players):
        
        try:
            self.console.write(('vars.maxPlayers', num_players),)
            self._current_players_setting = num_players
            self.debug('Max players set to %s' %  num_players)
            self.console.say('Player count setting now %s' % num_players)
        except Exception, msg:
            self.debug('Error setting max players %s' %  num_players)
                
    def get_new_players_setting(self):
        clients = self.console.clients.getList()
        _players = len(clients)
        
        if _players < self._idle_player_count  and self._idle_kick_disable:
            self.setIdle(0)
        else:
            self.setIdle(300)
            
        new_players_setting = self._max_players
        try:
            for ix in range(1, len(self._player_counts)+1):
                if _players >= int(self._player_counts[ix][0]):
                    new_players_setting = int(self._player_counts[ix][1])
            self.debug (new_players_setting)
            return new_players_setting
        except Exception, msg:
            self.debug('Error %s' % msg)
            self.console.say('Error in player count settings')
            return self._max_players
        
    def show_current_settings(self):
        if self._current_rotation_no != 0:
            self.console.say('Map Rotation set to Rotation %s' % self._current_rotation_no)
        else:
            self.console.say('Error setting new map rotation')
            
        if self._next_gametype:
            self.console.say('Current gametype is %s on %s and tickets at %s%%' % (self._next_gametype, self._easy_map_names[self._next_map_name], self._use_mult))
            
    def check_map_info(self, map_info):
        map_details = map_info.split(',')
        if not map_details[1] in GAME_MODES_NAMES:
            self.error('There is an error with your Rotation Manager Plugin config in %s' % map_info)
            return False
                    
        if not map_details[0]in BF3_MAP_NAMES:
            self.debug(self._easy_map_names)
            if not map_details[0] in self._easy_map_names:
                self.error('There is an error with your Rotation Manager Plugin config in %s' % map_info)
                return False
         
        return True
           
    def _start_delay(self):
        self._delay_player_check = False
        self.console.say('Player count adjuster now active')
        
    def get_gt_multiplier(self):
        round_no, rounds_total = self.getRoundinfo()
        if rounds_total - round_no > 1:
            c = self.console.game
            self._next_gametype = c.gameType
            self._nextmapname = c.mapName
        else:
            self._next_gametype, self._next_map_name  = self.getNextGametype()
            
        self.debug('Next Round Gametype is %s' % self._next_gametype)
        self.debug('gt_mult is %s' % self._gametype_mults[self._next_gametype])
        
        return self._gametype_mults[self._next_gametype]
        
        
    def setticketcount(self, tickets):
        try:
            self.console.write(('vars.gameModeCounter', tickets))
            self.debug('Tickets set to %s' % tickets)
            return tickets
        except CommandFailedError, err:
            self.debug('Error: %s' % err.message)
            return false
            
    def getRoundinfo(self):
        rounds = self.console.write(('mapList.getRounds', ))
        round_no = int(rounds[0])
        rounds_total = int(rounds[1])
        self.debug('Round %s of %s' % (round_no, rounds_total))
        return (round_no, rounds_total)

    def getNextGametype(self):
        """Return the name of the next gamemode"""
        maps = self.console.getFullMapRotationList()
        if len(maps) == 0:
            next_map_gamemode = self.game.gameType
            next_map_name = self.game.mapName
        else:
            mapIndices = self.console.write(('mapList.getMapIndices', ))
            next_map_info = maps[int(mapIndices[1])]
        return  next_map_info['gamemode'], next_map_info['name']
        
    def _check_idle_setting(self):
        clients = self.console.clients.getList()
        _players = len(clients)
        
        if _players < self._idle_player_count  and self._idle_kick_disable:
            self.setIdle(0)
        else:
            self.setIdle(300)

    def setIdle(self, idlesecs):
        self.console.write(('vars.idleTimeout', idlesecs))

