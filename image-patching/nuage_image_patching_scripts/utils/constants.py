# List of Nuage packages
NUAGE_PYTHON_OVS = "python-openvswitch-nuage"
NUAGE_PACKAGES = "nuage-puppet-modules selinux-policy-nuage " \
                 "nuage-openstack-neutronclient"
#                 "nuage-bgp nuage-openstack-neutronclient"
NUAGE_DEPENDENCIES = "libvirt perl-JSON lldpad createrepo"
NUAGE_VRS_PACKAGE = "nuage-openvswitch nuage-metadata-agent"
VIRT_CUSTOMIZE_MEMSIZE = "2048"
VIRT_CUSTOMIZE_ENV = "export LIBGUESTFS_BACKEND=direct;"
SCRIPT_NAME = 'patching_script.sh'
TEMPORARY_PATH = '/tmp/'
LOG_FILE_NAME='nuage_image_patching.log'
RHEL_SUB_PORTAL = "portal"
RHEL_SUB_SATELLITE = "satellite"
RHEL_SUB_DISABLED = "disabled"
