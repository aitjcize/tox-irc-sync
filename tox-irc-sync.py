import sys
import socket
import string
import select
import re

from tox import Tox

from time import sleep
from os.path import exists

SERVER = ["54.199.139.199", 33445, "7F9C31FE850E97CEFD4C4591DF93FC757C7C12549DDD55F8EEAECC34FE76C029"]
GROUP_BOT = '56A1ADE4B65B86BCD51CC73E2CD4E542179F47959FE3E0E21B4B0ACDADE5185520B3E6FC5D64'

IRC_HOST = "irc.freenode.net"
IRC_PORT = 6667
NAME = NICK = IDENT = REALNAME = "SyncBot"

CHANNEL = '#tox-ontopic'

class SyncBot(Tox):
    def __init__(self):
        if exists('data'):
            self.load_from_file('data')

        self.connect()
        self.set_name("SyncBot")
        self.set_status_message("Send me a message with the word 'invite'")
        print('ID: %s' % self.get_address())

        self.readbuffer = ""
        self.sent = None
        self.tox_group_id = None

        self.irc_init()

    def irc_init(self):
        self.irc = socket.socket()
        self.irc.connect((IRC_HOST, IRC_PORT))
        self.irc.send("NICK %s\r\n" % NICK)
        self.irc.send("USER %s %s bla :%s\r\n" % (IDENT, IRC_HOST, REALNAME))

    def connect(self):
        print('connecting...')
        self.bootstrap_from_address(SERVER[0], 1, SERVER[1], SERVER[2])

    def ensure_exe(self, func, args):
        count = 0
        THRESHOLD = 50

        while True:
            try:
                return func(*args)
            except:
                assert count < THRESHOLD
                count += 1
                for i in range(10):
                    self.do()
                    sleep(0.02)

    def loop(self):
        checked = False
        self.joined = False
        self.request = False

        try:
            while True:
                status = self.isconnected()
                if not checked and status:
                    print('Connected to DHT.')
                    checked = True
                    try:
                        self.bid = self.get_friend_id(GROUP_BOT)
                    except:
                        self.ensure_exe(self.add_friend, (GROUP_BOT, "Hi"))
                        self.bid = self.get_friend_id(GROUP_BOT)

                if checked and not status:
                    print('Disconnected from DHT.')
                    self.connect()
                    checked = False

                readable, _, _ = select.select([self.irc], [], [], 0.01)

                if readable:
                    self.readbuffer += self.irc.recv(4096)
                    lines = self.readbuffer.split('\n')
                    self.readbuffer = lines.pop()

                    for line in lines:
                        rx = re.match(r':(.*?)!.*? PRIVMSG %s :(.*?)\r' %
                                CHANNEL, line, re.S)
                        if rx:
                            print('IRC> %s: %s' % rx.groups())
                            msg = '[%s]: %s' % rx.groups()
                            content = rx.group(2)

                            if content == '^syncbot' or \
                                    content == '^echobot':
                                self.irc_send('PRIVMSG %s :%s\r\n' %
                                        (CHANNEL, self.get_address()))
                                self.ensure_exe(self.group_message_send,
                                        (self.tox_group_id, self.get_address()))
                            elif content[1:].startswith('ACTION '):
                                action = '[%s]: %s' % (rx.group(1),
                                        rx.group(2)[8:-1])
                                self.sent = action
                                self.ensure_exe(self.group_action_send,
                                        (self.tox_group_id, action))
                            elif self.tox_group_id != None:
                                self.sent = msg
                                self.ensure_exe(self.group_message_send,
                                        (self.tox_group_id, msg))

                        l = line.rstrip().split()
                        if l[0] == "PING":
                           self.irc_send("PONG %s\r\n" % l[1])
                        if l[1] == "376":
                           self.irc.send("JOIN %s\r\n" % CHANNEL)

                self.do()
        except KeyboardInterrupt:
            self.save_to_file('data')

    def irc_send(self, msg):
        success = False
        while not success:
            try:
                self.irc.send(msg)
                success = True
                break
            except socket.error:
                self.irc_init()
                sleep(1)

    def on_connection_status(self, friendId, status):
        if not self.request and not self.joined \
                and friendId == self.bid and status:
            print('Groupbot online, trying to join group chat.')
            self.request = True
            self.ensure_exe(self.send_message, (self.bid, 'invite'))

    def on_group_invite(self, friendid, pk):
        if not self.joined:
            self.joined = True
            self.tox_group_id = self.join_groupchat(friendid, pk)
            print('Joined groupchat.')

    def on_group_message(self, groupnumber, friendgroupnumber, message):
        if message != self.sent:
            name = self.group_peername(groupnumber, friendgroupnumber)
            print('TOX> %s: %s' % (name, message))
            if message.startswith('^'):
                self.irc_send('PRIVMSG %s :%s\r\n' % (CHANNEL, message))
            else:
                self.irc_send('PRIVMSG %s :[%s]: %s\r\n' %
                              (CHANNEL, name, message))

    def on_group_action(self, groupnumber, friendgroupnumber, action):
        if action != self.sent:
            name = self.group_peername(groupnumber, friendgroupnumber)
            print('TOX> %s: %s' % (name, action))
            self.irc_send('PRIVMSG %s :\x01ACTION [%s]: %s\x01\r\n' %
                    (CHANNEL, name, action))

    def on_friend_request(self, pk, message):
        print('Friend request from %s: %s' % (pk, message))
        self.add_friend_norequest(pk)
        print('Accepted.')

    def on_friend_message(self, friendid, message):
        if message == 'invite':
            print('Inviting %s' % self.get_name(friendid))
            self.invite_friend(friendid, self.tox_group_id)
        else:
            self.ensure_exe(self.send_message, (friendid, message))

t = SyncBot()
t.loop()
