import subprocess
import sys
import logging
import os
from utils import *
import yaml
from  constants import *

logger = utils.logger

'''
This script is used to patch an existing OpenStack
image with Nuage components
This script takes in following input parameters:
 RhelUserName      : User name for the RHEL subscription
 RhelPassword      : Password for the RHEL subscription
 RhelPool          : RHEL Pool to subscribe
 RepoFile          : Name for the file repo hosting the Nuage RPMs
 DeploymentType    : ["ovrs"] --> OVRS deployment
                     ["avrs"] --> AVRS + VRS deployment
                     ["vrs"]  --> VRS deployment
 RpmPublicKey      : RPM GPG Key 
 logFile           : Log file name
The following sequence is executed by the script
 1. Subscribe to RHEL and the pool
 2. Uninstall OVS
 3. Download AVRS packages to the image if AVRS is enabled
 4. Install NeutronClient, Nuage-BGP, Selinux Policy Nuage, 
    Nuage Puppet Module, Redhat HF and Mellanox packages.
 5. Install O/VRS, Nuage Metadata Agent
 6. Unsubscribe from RHEL
'''


#####
# Function to install Nuage packages that are required
#####


def install_nuage_packages():
    cmds = '''
#### Installing Nuage Packages
yum install --setopt=skip_missing_names_on_install=False -y %s
yum install --setopt=skip_missing_names_on_install=False -y %s
yum install --setopt=skip_missing_names_on_install=False -y %s
''' % (NUAGE_DEPENDENCIES, NUAGE_VRS_PACKAGE,
       NUAGE_PACKAGES)

    write_to_file(constants.SCRIPT_NAME, cmds)


#####
# Function to install Mellanox packages that are required
#####


def install_mellanox():
    # Installing Mellanox OFED Packages
    cmds = '''
#### Installing Mellanox OFED and os-net-config Packages
yum clean all
yum install --setopt=skip_missing_names_on_install=False -y %s
systemctl disable mlnx-en.d
''' % (MLNX_OFED_PACKAGES)
    write_to_file(SCRIPT_NAME, cmds)


#####
# Updating kernel to Red Hat Hot Fix
#####


def update_kernel():
    # Updating Kernel
    cmds = '''
#### Installing Kernel Hot Fix Packages
yum clean all
yum install --setopt=skip_missing_names_on_install=False -y %s
''' % (KERNEL_PACKAGES)
    write_to_file(SCRIPT_NAME, cmds)


#####
# Function to install Nuage AVRS packages that are required
#####


def download_avrs_packages():
    cmds = '''
#### Downloading Nuage Avrs and 6wind Packages
mkdir -p /6wind
rm -rf /var/cache/yum/Nuage
yum clean all
touch /kernel-version
rpm -q kernel | awk '{ print substr($1,8) }' > /kernel-version
yum install --setopt=skip_missing_names_on_install=False -y createrepo
yum install --setopt=skip_missing_names_on_install=False --downloadonly --downloaddir=/6wind kernel-headers-$(awk 'END{print}' /kernel-version) kernel-devel-$(awk 'END{print}' /kernel-version) python-pyelftools* dkms* 6windgate* nuage-openvswitch-6wind nuage-metadata-agent virtual-accelerator*
yum install --setopt=skip_missing_names_on_install=False --downloadonly --downloaddir=/6wind selinux-policy-nuage-avrs*
yum install --setopt=skip_missing_names_on_install=False --downloadonly --downloaddir=/6wind 6wind-openstack-extensions
rm -rf /kernel-version
yum clean all
%s
'''
    write_to_file(SCRIPT_NAME, cmds)


####
# Check Config
####
def check_config(nuage_config):
    missing_config = []
    for key in ["ImageName", "RepoFile"]:
        if not (nuage_config.get(key)):
            missing_config.append(key)
    if missing_config:
        logger.error("Please provide missing config %s value "
                     "in your config file. \n" % missing_config)
        sys.exit(1)
    file_exists(nuage_config["ImageName"])
    msg = "DeploymentType config option %s is not correct or supported " \
          " Please enter:\n ['vrs'] --> for VRS deployment\n " \
          "['avrs'] --> for AVRS + VRS deployment\n " \
          "['ovrs'] --> for OVRS deployment" % nuage_config["DeploymentType"]
    if len(nuage_config["DeploymentType"]) > 1:
        new_msg = "Multiple " + msg
        logger.error(new_msg)
        sys.exit(1)
    elif "vrs" in nuage_config["DeploymentType"]:
        logger.info("Overcloud Image will be patched with Nuage VRS rpms")
    elif "avrs" in nuage_config["DeploymentType"]:
        logger.info("Overcloud Image will be patched with Nuage VRS & AVRS rpms")
    elif "ovrs" in nuage_config["DeploymentType"]:
        logger.info("Overcloud Image will be patched with OVRS rpms")
    else:
        logger.error(msg)
        sys.exit(1)
    logger.info("Verifying pre-requisite packages for script")
    libguestfs = cmds_run(['rpm -q libguestfs-tools-c'])
    if 'not installed' in libguestfs:
        logger.info("Please install libguestfs-tools-c package for the script to run")
        sys.exit(1)


####
# Image Patching
####


def image_patching(nuage_config):
    check_config(nuage_config)

    if nuage_config.get("logFileName"):
        handler = logging.FileHandler(nuage_config["logFileName"])
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    start_script()

    if nuage_config.get("RpmPublicKey"):
        logger.info("Importing gpgkey(s) to overcloud image")
        importing_gpgkeys(nuage_config["ImageName"],
                                nuage_config["RpmPublicKey"])

    if nuage_config.get("RhelUserName") and nuage_config.get(
            "RhelPassword") and nuage_config.get("RhelPool"):
        if nuage_config.get("ProxyHostname") and nuage_config.get("ProxyPort"):
            rhel_subscription(
                nuage_config["RhelUserName"], nuage_config["RhelPassword"],
                nuage_config["RhelPool"], nuage_config["ProxyHostname"],
                nuage_config["ProxyPort"])
        else:
            rhel_subscription(
                nuage_config["RhelUserName"], nuage_config["RhelPassword"],
                nuage_config["RhelPool"])
    uninstall_packages()

    logger.info("Copying RepoFile to the overcloud image")
    copy_repo_file(nuage_config["ImageName"], nuage_config["RepoFile"])

    if nuage_config['KernelHF']:
        update_kernel(nuage_config["KernelRepoNames"])

    if "ovrs" in nuage_config["DeploymentType"]:
        install_mellanox(nuage_config["MellanoxRepoNames"])

    if "avrs" in nuage_config["DeploymentType"]:
        download_avrs_packages()

    install_nuage_packages()

    if nuage_config.get("RhelUserName") and nuage_config.get(
            "RhelPassword") and nuage_config.get("RhelPool"):
        rhel_remove_subscription()

    logger.info("Running the patching script on Overcloud image")
    virt_customize_run(
        ' %s -a %s --memsize %s --selinux-relabel' % (
            SCRIPT_NAME, nuage_config["ImageName"],
            VIRT_CUSTOMIZE_MEMSIZE))
    logger.info("Reset the Machine ID")
    cmds_run([VIRT_CUSTOMIZE_ENV + "virt-sysprep --operation machine-id -a %s" % nuage_config["ImageName"]])
    logger.info("Done")


