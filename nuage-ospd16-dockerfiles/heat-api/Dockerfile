FROM undercloud16.ctlplane.localdomain:8787/rhosp-rhel8/openstack-heat-api:16.0
MAINTAINER Nuage OpenStack Engineering opensource@nuagenetworks.net

LABEL name="undercloud16.ctlplane.localdomain:8787/openstack-nuage-heat-api"

LABEL version="16.0-nuage"

LABEL release=latest

USER root

COPY RPM-GPG-KEY-Nuage /tmp/RPM-GPG-KEY-Nuage
COPY redhat.repo /etc/yum.repos.d/redhat.repo
COPY nuage.repo /etc/yum.repos.d/nuage.repo
RUN yum -y install nuage-openstack-neutronclient && yum clean all


USER heat
