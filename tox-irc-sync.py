import sys
import socket
import string
import select
import re

from tox import Tox

from time import sleep
from os.path import exists

SERVER = ["192.81.133.111", 33445, "8CD5A9BF0A6CE358BA36F7A653F99FA6B258FF756E490F52C1F98CC420F78858"]
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

        self.irc = socket.socket()
        self.irc.connect((IRC_HOST, IRC_PORT))
        self.irc.send("NICK %s\r\n" % NICK)
        self.irc.send("USER %s %s bla :%s\r\n" % (IDENT, IRC_HOST, REALNAME))
        self.irc.send("JOIN %s\r\n" % CHANNEL)

    def connect(self):
        print('connecting...')
        self.bootstrap_from_address(SERVER[0], 0, SERVER[1], SERVER[2])

    def loop(self):
        checked = False
        self.joined = False

        try:
            self.add_friend(GROUP_BOT, "")
        except: pass

        try:
            while True:
                status = self.isconnected()
                if not checked and status:
                    print('Connected to DHT.')
                    checked = True

                if checked and not status:
                    print('Disconnected from DHT.')
                    self.connect()
                    checked = False

                if not self.joined:
                    try:
                        tid = self.get_friend_id(GROUP_BOT)
                        self.send_message(tid, 'invite')
                    except: pass

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
                            msg = '%s> %s' % rx.groups()

                            if rx.group(2) == '^syncbot':
                                self.irc.send('PRIVMSG %s :%s\r\n' %
                                        (CHANNEL, self.get_address()))
                            else:
                                self.send_group_msg(msg)

                        l = line.rstrip().split()
                        if l[0] == "PING":
                           self.irc.send("PONG %s\r\n" % l[1])

                self.do()
        except KeyboardInterrupt:
            self.save_to_file('data')

    def send_group_msg(self, msg):
        self.sent = msg
        if self.tox_group_id != None:
            sent = False
            while not sent:
                try:
                    self.group_message_send(self.tox_group_id, msg)
                    sent = True
                except:
                    self.do()
                    sleep(0.02)

    def on_group_invite(self, friendid, pk):
        if not self.joined:
            self.joined = True
            self.tox_group_id = self.join_groupchat(friendid, pk)
            print('Joined groupchat.')

    def on_group_message(self, groupnumber, friendgroupnumber, message):
        if message != self.sent:
            name = self.group_peername(groupnumber, friendgroupnumber)
            print('TOX> %s: %s' % (name, message))
            self.irc.send('PRIVMSG %s :%s> %s\r\n' % (CHANNEL, name, message))

    def on_friend_request(self, pk, message):
        print('Friend request from %s: %s' % (pk, message))
        self.add_friend_norequest(pk)
        print('Accepted.')

    def on_friend_message(self, friendid, message):
        if message == 'invite':
            self.invite_friend(friendid, self.tox_group_id)

t = SyncBot()
t.loop()
