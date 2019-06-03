#!/bin/bash
set -x

createrepo /6wind/.
touch /etc/yum.repos.d/nuage_6wind.repo
echo "[nuage_6wind]" >> /etc/yum.repos.d/nuage_6wind.repo
echo "name=nuage_6wind" >> /etc/yum.repos.d/nuage_6wind.repo
echo "baseurl=file:///6wind/" >> /etc/yum.repos.d/nuage_6wind.repo
echo "enabled = 1" >> /etc/yum.repos.d/nuage_6wind.repo
echo "gpgcheck = 0" >> /etc/yum.repos.d/nuage_6wind.repo
yum install -y selinux-policy-nuage-avrs
yum install -y python-pyelftools
yum install -y dkms
yum remove -y dpdk
yum install -y 6windgate*
yum remove -y nuage-openvswitch
yum install -y nuage-openvswitch*
yum install -y nuage-metadata-agent*
yum install -y virtual-accelerator*
rm -rf /6wind/repodata
rm -rf /etc/yum.repos.d/nuage_6wind.repo
