#FROM registry.access.redhat.com/rhosp13/openstack-horizon:latest
FROM undercloud16.ctlplane.localdomain:8787/rhosp-rhel8/openstack-horizon:16.0
MAINTAINER Nuage OpenStack Engineering opensource@nuagenetworks.net

LABEL name="undercloud16.ctlplane.localdomain:8787/rhosp-rhel8/openstack-horizon"
LABEL version="16.0-nuage"
LABEL release=latest

COPY redhat.repo /etc/yum.repos.d/redhat.repo
COPY RPM-GPG-KEY-Nuage /tmp/RPM-GPG-KEY-Nuage
COPY nuage.repo /etc/yum.repos.d/nuage.repo
RUN yum -y install nuage-openstack-horizon nuage-openstack-neutronclient && yum clean all

RUN rm -f /etc/yum.repos.d/nuage.repo

