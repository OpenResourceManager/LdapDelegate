#!/usr/bin/env python
from __future__ import print_function
from socketIO_client import SocketIO, LoggingNamespace
from includes.AdManager import AdManager
from includes.helpers import read_config, read_encrypted_message
from signal import SIGTERM
import socket
import sys
import os
import time
import atexit

IO = None
HOST_NAME = None
BC_KEY = None
DELEGATE_HOST = 'localhost'
DELEGATE_PORT = 3000


class LdapDelegate:
    def __init__(self, pidfile, stdin='/dev/null', stdout='/var/log/orm/LdapDelegate/run.log',
                 stderr='/var/log/orm/LdapDelegate/error.log'):
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.pidfile = pidfile

    def daemonize(self):
        """
        do the UNIX double-fork magic, see Stevens' "Advanced
        Programming in the UNIX Environment" for details (ISBN 0201563177)
        http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC16
        """
        try:
            pid = os.fork()
            if pid > 0:
                # exit first parent
                sys.exit(0)
        except OSError, e:
            sys.stderr.write("fork #1 failed: %d (%s)\n" % (e.errno, e.strerror))
            sys.exit(1)

        # decouple from parent environment
        os.chdir("/")
        os.setsid()
        os.umask(0)

        # do second fork
        try:
            pid = os.fork()
            if pid > 0:
                # exit from second parent
                sys.exit(0)
        except OSError, e:
            sys.stderr.write("fork #2 failed: %d (%s)\n" % (e.errno, e.strerror))
            sys.exit(1)

        # redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()
        si = file(self.stdin, 'r')
        so = file(self.stdout, 'a+')
        se = file(self.stderr, 'a+', 0)
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())

        # write pidfile
        atexit.register(self.delpid)
        pid = str(os.getpid())
        file(self.pidfile, 'w+').write("%s\n" % pid)

    def delpid(self):
        os.remove(self.pidfile)

    def start(self):
        """
        Start the daemon
        """
        # Check for a pidfile to see if the daemon already runs
        try:
            pf = file(self.pidfile, 'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None

        if pid:
            message = "pidfile %s already exist. Daemon already running?\n"
            sys.stderr.write(message % self.pidfile)
            sys.exit(1)

        # Start the daemon
        self.daemonize()
        self.run()

    def stop(self):
        """
        Stop the daemon
        """
        # Get the pid from the pidfile
        try:
            pf = file(self.pidfile, 'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None

        if not pid:
            message = "pidfile %s does not exist. Daemon not running?\n"
            sys.stderr.write(message % self.pidfile)
            return  # not an error in a restart

        # Try killing the daemon process
        try:
            while 1:
                os.kill(pid, SIGTERM)
                time.sleep(0.1)
        except OSError, err:
            err = str(err)
            if err.find("No such process") > 0:
                if os.path.exists(self.pidfile):
                    os.remove(self.pidfile)
            else:
                print
                str(err)
                sys.exit(1)

    def restart(self):
        """
        Restart the daemon
        """
        self.stop()
        self.start()

    def load_config(self):
        global HOST_NAME, DELEGATE_HOST, DELEGATE_PORT, BC_KEY
        c = read_config()
        config = c['general']
        HOST_NAME = socket.gethostname()
        DELEGATE_HOST = config['delegate_server_host']
        DELEGATE_PORT = config['delegate_server_port']
        try:
            if not config['bc_key']:
                raise Exception('You have not provided a `bc_key` in your config file! Hint: `php artisan orm:bckey`')
        except KeyError:
            raise KeyError('You have not provided a `bc_key` in your config file! Hint: `php artisan orm:bckey`')
        BC_KEY = config['bc_key']

    def connect_to_sio(self):
        global IO
        print('Connecting...')
        IO = SocketIO(DELEGATE_HOST, DELEGATE_PORT, LoggingNamespace)
        print('Connected!')

    def on_create_account(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            account = message['data']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.new_account(account)

    def on_update_account(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            account = message['data']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.modify_account(account)

    def on_delete_account(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            account = message['data']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.delete_account(account)

    def on_restore_account(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            account = message['data']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.restore_account(account)

    def on_create_duty(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            duty = message['data']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.create_group(duty, 'Duty')

    def on_destroy_duty(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            duty = message['data']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.delete_group(duty, 'Duty')

    def on_restore_duty(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            duty = message['data']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.restore_group(duty, 'Duty')

    def on_create_campus(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            campus = message['data']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.create_group(campus, 'Campus')

    def on_destroy_campus(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            campus = message['data']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.delete_group(campus, 'Campus')

    def on_restore_campus(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            campus = message['data']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.restore_group(campus, 'Campus')

    def on_create_building(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            building = message['data']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.create_group(building, 'Building')

    def on_destroy_building(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            building = message['data']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.delete_group(building, 'Building')

    def on_restore_building(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            building = message['data']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.restore_group(building, 'Building')

    def on_create_room(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            room = message['data']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.create_group(room, 'Room')

    def on_destroy_room(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            room = message['data']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.delete_group(room, 'Room')

    def on_restore_room(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            room = message['data']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.restore_group(room, 'Room')

    def on_create_department(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            department = message['data']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.create_group(department, 'Department')

    def on_destroy_department(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            department = message['data']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.delete_group(department, 'Department')

    def on_restore_department(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            department = message['data']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.restore_group(department, 'Department')

    def on_create_course(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            course = message['data']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.create_group(course, 'Course')

    def on_destroy_course(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            course = message['data']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.delete_group(course, 'Course')

    def on_restore_course(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            course = message['data']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.restore_group(course, 'Course')

    def on_create_school(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            school = message['data']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.create_group(school, 'School')

    def on_destroy_school(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            school = message['data']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.delete_group(school, 'School')

    def on_restore_school(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            school = message['data']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.restore_group(school, 'School')

    def on_course_account_assignment(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            data = message['data']
            account = data['account']
            course = data['course']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.add_account_to_group(account, course, 'Course')

    def on_course_account_unassignment(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            data = message['data']
            account = data['account']
            course = data['course']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.remove_account_from_group(account, course, 'Course')

    def on_department_account_assignment(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            data = message['data']
            account = data['account']
            department = data['department']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.add_account_to_group(account, department, 'Department')

    def on_department_account_unassignment(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            data = message['data']
            account = data['account']
            department = data['department']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.remove_account_from_group(account, department, 'Department')

    def on_duty_account_assignment(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            data = message['data']
            account = data['account']
            duty = data['duty']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.add_account_to_group(account, duty, 'Duty')

    def on_duty_account_unassignment(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            data = message['data']
            account = data['account']
            duty = data['duty']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.remove_account_from_group(account, duty, 'Duty')

    def on_room_account_assignment(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            data = message['data']
            account = data['account']
            room = data['room']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.add_account_to_group(account, room, 'Room')

    def on_room_account_unassignment(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            data = message['data']
            account = data['account']
            room = data['room']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.remove_account_from_group(account, room, 'Room')

    def on_school_account_assignment(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            data = message['data']
            account = data['account']
            school = data['school']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.add_account_to_group(account, school, 'School')

    def on_school_account_unassignment(*args):
        for arg in args:
            message = read_encrypted_message(arg, BC_KEY)
            ldap_conf = message['conf']['ldap']
            data = message['data']
            account = data['account']
            school = data['school']
            if ldap_conf['enabled']:
                ad = AdManager(ldap_conf)
                ad.remove_account_from_group(account, school, 'School')

    def run(self):
        # Load the configuration
        self.load_config()
        # Connect to the server
        self.connect_to_sio()
        # Emmit that we're here
        IO.emit('join', {'hostname': HOST_NAME})
        # Account Listeners
        IO.on('create_account', self.on_create_account)
        IO.on('update_account', self.on_update_account)
        IO.on('delete_account', self.on_delete_account)
        IO.on('restore_account', self.on_restore_account)
        # Duty Listeners
        IO.on('create_duty', self.on_create_duty)
        IO.on('delete_duty', self.on_destroy_duty)
        IO.on('restore_duty', self.on_restore_duty)
        # Campus Listeners
        IO.on('create_campus', self.on_create_campus)
        IO.on('delete_campus', self.on_destroy_campus)
        IO.on('restore_campus', self.on_restore_campus)
        # Building Listeners
        IO.on('create_building', self.on_create_building)
        IO.on('delete_building', self.on_destroy_building)
        IO.on('restore_building', self.on_restore_building)
        # Room Listeners
        IO.on('create_room', self.on_create_room)
        IO.on('delete_room', self.on_destroy_room)
        IO.on('restore_room', self.on_restore_room)
        # Department Listeners
        IO.on('create_department', self.on_create_department)
        IO.on('delete_department', self.on_destroy_department)
        IO.on('restore_department', self.on_restore_department)
        # Course Listeners
        IO.on('create_course', self.on_create_course)
        IO.on('delete_course', self.on_destroy_course)
        IO.on('restore_course', self.on_restore_course)
        # Account Assignment Listeners
        IO.on('course_account_assignment', self.on_course_account_assignment)
        IO.on('course_account_unassignment', self.on_course_account_unassignment)
        IO.on('department_account_assignment', self.on_department_account_assignment)
        IO.on('department_account_unassignment', self.on_department_account_unassignment)
        IO.on('duty_account_assignment', self.on_duty_account_assignment)
        IO.on('duty_account_unassignment', self.on_duty_account_unassignment)
        IO.on('room_account_assignment', self.on_room_account_assignment)
        IO.on('room_account_unassignment', self.on_room_account_unassignment)
        IO.on('school_account_assignment', self.on_school_account_assignment)
        IO.on('school_account_unassignment', self.on_school_account_unassignment)
        # Hang out
        IO.wait()


if __name__ == "__main__":
    daemon = LdapDelegate('/var/run/ldap-delegate.pid')
    if len(sys.argv) == 2:
        if 'start' == sys.argv[1]:
            daemon.start()
        elif 'stop' == sys.argv[1]:
            daemon.stop()
        elif 'restart' == sys.argv[1]:
            daemon.restart()
        else:
            print
            "Unknown command"
            sys.exit(2)
        sys.exit(0)
    else:
        print
        "usage: %s start|stop|restart" % sys.argv[0]
        sys.exit(2)
