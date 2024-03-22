#!/bin/bash -v
#
# Licensed under the terms of the GNU GPL License version 2

FedoraRelease=Fedora40
currentkernel=kernel-`uname -r`
kojidir=/home/kerneltest/koji/
kerneltestdir=/home/kerneltest/kernel-tests/

# Just gives us time to log in and kill it for maintenance
sleep 90

#Update Guest
dnf -y update

if [ ! -f /data/latest/$FedoraRelease ]; then
    mount /data
fi

latestkernel=`cat /data/latest/$FedoraRelease`

#Make sure we are on the latest kernel, install if not
if [ "$currentkernel" != "$latestkernel.x86_64" ]
then
    cd $kojidir
    rm *.rpm
    koji download-build --arch=x86_64 $latestkernel
    dnf -y update *.rpm
    reboot
fi

#We are on the latest kernel, run some tests
cd $kerneltestdir
git pull
sleep 120
#Regression Test as root
./runtests.sh
if [ "$result" != "0" ]
then
    echo "Regression Test Suite fail for kernel $currentkernel"
    ./runtests.sh
fi

/usr/sbin/shutdown now -h
