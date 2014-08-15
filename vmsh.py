#!/usr/bin/python
import sys, paramiko, time, re, signal, os
from subprocess import Popen, PIPE
from ethip import ethip

def stop(signal, frame):
    print
    exit(1)

def host_exec(command, channel):
    if channel.recv_ready():
        channel.recv(2048)
    channel.send('%s\n' % command)
    result = ''
    while not prompt in result:
        time.sleep(.1)
        if channel.recv_ready():
            result += channel.recv(2048)
    return '\n'.join(result.split('\n')[1:-1]).strip()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print '%s [username] [hostname] [subnets...]' % sys.argv[0]

    signal.signal(signal.SIGINT, stop)

    user = sys.argv[1]
    host = sys.argv[2]
    subnets = sys.argv[3:]
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=user)
    channel = ssh.invoke_shell()
    time.sleep(.3)
    channel.recv(2048)
    channel.send('PS1=\'PROMPT>>\'\n')
    time.sleep(.3)
    channel.recv(2048)
    prompt = 'PROMPT>>'

    ether = {}
    vmxs = host_exec('find $HOME -name *.vmx', channel).split('\n')
    for vmx in vmxs:
        try:
            mac = host_exec('cat "%s" | grep "ethernet0.generatedAddress ="' % vmx.strip(), channel).strip().split()[-1][1:-1]
            ether[mac.lower()] = [vmx.strip().split('/')[-1].strip('.vmx'), None, vmx.strip()]
        except:
            continue

    ips = [(ether[key] + [key]) for key in ether.iterkeys()]

    hostname = host_exec('hostname', channel).strip().split('.')[0]
    print "\n\t0: %s%s" % (("%s (VMWare host)" % hostname).ljust(40), host)
    count = 1
    for machine in ips:
        print "\t%d: %s%s" % (count, machine[0].ljust(40), machine[1] or machine[3])
        count += 1
    try:
        selection = int(raw_input('\nWhich machine would you like to connect to? '))-1
        ips[selection]
    except:
        exit(0)

    # Connect to the host machine?
    if selection == -1:
        print '# ssh %s@%s' % (user, host)
        Popen(['/usr/bin/ssh', '%s@%s' % (user, host)]).wait()
        exit(0)

    # Make sure the machine is on
    print 'Turning on the machine...'
    error = host_exec('vmrun start "%s" nogui' % ips[selection][2], channel)
    if error and 'The file is already in use' not in error:
        print error

    if not ips[selection][1]:
        print 'Discovering IP address...'
        for subnet in subnets:
            resp = ethip.getip(ips[selection][3], subnet)
            if resp:
                ips[selection][1] = resp
                break

    if ips[selection][1]:
        print '# ssh %s@%s' % (user, ips[selection][1])
        Popen(['/usr/bin/ssh', '%s@%s' % (user, ips[selection][1])]).wait()

        choice = raw_input('\nSuspend the machine (y/N)? ') + ' '
        if choice.lower()[0] == 'y':
            print 'Suspending the machine...'
            host_exec('nohup vmrun suspend "%s" &' % ips[selection][2], channel)
    else:
        print 'IP address could not be found'

