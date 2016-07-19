#!/usr/bin/python
import sys, paramiko, time, re, signal, os, getpass, argparse
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
    parser_epilog = ("Example:\n\n"
    "%s root 10.5.42.3 10.5.42.255 10.5.45.255\n\n"
    "This command will establish an ssh session with the host 10.5.42.3 with the username root, then search for vmware VMs running on the host and search for their ip addresses via mac address in the subnets 10.5.42.x and 10.5.45.x. It then prompts to connect to one of the VMs. It attempts to start the VM if not running." % sys.argv[0])
    parser = argparse.ArgumentParser(description="Remotely start vmware virtual machines and locate their ip address", epilog=parser_epilog, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("username", help="The username for logging into the vm host")
    parser.add_argument("hostname", help="The hostname or ip address of the vm host")
    parser.add_argument("subnets", nargs='+', help="The subnets to search for the VMs ip addresses")
    args = parser.parse_args()

    user = args.username
    host = args.hostname
    subnets = args.subnets

    signal.signal(signal.SIGINT, stop)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=user, password=getpass.getpass('Password: '))
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

