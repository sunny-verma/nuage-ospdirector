#!/bin/bash
set -xe

#### Importing GPG keys

rpm --import /tmp/RPM-GPG-KEY-Nuage
subscription-manager config --server.proxy_hostname=proxy.lbs.alcatel-lucent.com  --server.proxy_port=8000
subscription-manager register --username='sai_ram.peesapati@nokia.com' --password='P3es@pati' --force 
subscription-manager attach --pool='8a85f999707800180170829d5f47065a'
#sudo subscription-manager repos --enable=rhel-8-for-x86_64-baseos-rpms # --enable=rhel-8-for-x86_64-highavailability-rpms --enable=ansible-2.8-for-rhel-8-x86_64-rpms  

#### Install Nuage Python OpenvSwitch
yum install --setopt=skip_missing_names_on_install=False -y python-openvswitch-nuage
yum clean all

#### Removing Upstream OpenvSwitch
ovs_package_name=$(rpm -qa | awk -F- '/^(openvswitch[0-9]+\.[0-9]+-|openvswitch-2)/{print $1}')
yum remove -y $ovs_package_name
yum clean all

#### Installing Nuage Packages
yum install --setopt=skip_missing_names_on_install=False -y libvirt perl-JSON lldpad createrepo
yum install --setopt=skip_missing_names_on_install=False -y nuage-openvswitch nuage-metadata-agent
yum install --setopt=skip_missing_names_on_install=False -y nuage-puppet-modules selinux-policy-nuage nuage-openstack-neutronclient
yum clean all


#### Removing RHEL Subscription
subscription-manager unregister
