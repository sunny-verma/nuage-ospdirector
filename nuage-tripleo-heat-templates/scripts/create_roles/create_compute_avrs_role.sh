#!/usr/bin/env bash

set -o errexit
set -o nounset
set -x

if [ "${USER}" != "stack" ]; then
    echo "ERROR: Run the script as \"stack\" user."
    exit 1
fi

source /home/stack/stackrc

echo "creating ComputeAvrs Role"
cp -r /home/stack/openstack-tripleo-heat-templates/roles/* ../../roles/
sudo openstack overcloud roles generate --roles-path ../../roles -o ../../roles/ComputeAvrs.yaml Compute
sudo sed -i -e 's/ Compute/ ComputeAvrs/g' ../../roles/ComputeAvrs.yaml
sudo sed -i -e "s/HostnameFormatDefault: '%stackname%-compute-%index%'/HostnameFormatDefault: '%stackname%-computeavrs-%index%'/g" ../../roles/ComputeAvrs.yaml
sudo sed -i -e 's/- OS::TripleO::Services::NovaCompute/- OS::TripleO::Services::NovaComputeAvrs/g'   ../../roles/ComputeAvrs.yaml
openstack overcloud roles generate --roles-path ../../roles -o ../../roles/compute-avrs-role.yaml Controller Compute ComputeAvrs

echo "Complete!! Created ComputeAvrs Role "
echo "Use ../environments/avrs-environment.yaml to configure the correct value for AVRS nodes"