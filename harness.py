#!/usr/bin/env python
#
# Licensed under the terms of the GNU GPL License version 2

import os
import string
import time
import _thread
import logging

import fedmsg
import fedmsg.config
import fedmsg.meta

import libvirt

def domainmap(buildrel):
    rawhide = "fc41"
    if buildrel == rawhide:
        domain = "Rawhide"
    else:
        domain = buildrel.replace("fc", "Fedora") + "_"
    return domain

def writelatest(domain, kernel):
    domfilename = domain.replace("_", "")
    domfile = open('/data/latest/%s' %(domfilename), 'w')
    domfile.write(kernel)
    domfile.close()

def launchdomain(domain):
    conn = libvirt.open(None)
    dom = conn.lookupByName(domain)
    if "Rawhide" in domain:
        dom.reboot()
    else:
        while True:
            domstate = dom.info()[0]
            if domstate == 5:
               break
            time.sleep(30)
        dom.create()
    print("Domain %s started" % (domain))
 
if __name__ == '__main__':
    logging.basicConfig()
    pidfile = open('/var/run/harness.pid', 'w')
    pid = str(os.getpid())
    pidfile.write(pid)
    pidfile.close()
    config = fedmsg.config.load_config([], None)
    config['mute'] = True
    config['timeout'] = 0
    fedmsg.meta.make_processors(**config)

    for name, endpoint, topic, msg in fedmsg.tail_messages(**config):
        if "buildsys.build.state.change" in topic and msg['msg']['instance'] == 'primary':
            matchedmsg = fedmsg.meta.msg2repr(msg, **config)
            if "completed" in matchedmsg and "kernel-6" in matchedmsg:
                objectmsg = fedmsg.meta.msg2subtitle(msg, legacy=False, **config)
                package = objectmsg.split(' ')
                fcrelease = package[1].split('.')
                domain = domainmap(fcrelease[-1])
                logfile = open('/var/log/harness.log', 'a')
                logfile.write(matchedmsg + '\n')
                logfile.write('Testing ' + package[1] + '\n')
                logfile.close()
                writelatest(domain, package[1])
                dom32 = domain + 'arm64'
                dom64 = domain + '64'
                print(matchedmsg)
                print("starting domain %s" % (dom32))
                _thread.start_new(launchdomain, (dom32,))
                print("starting domain %s" % (dom64))
                _thread.start_new(launchdomain, (dom64,))
