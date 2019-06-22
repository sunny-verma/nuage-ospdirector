#!/usr/bin/env bash

set -o errexit
set -o nounset

if [ "${USER}" != "stack" ]; then
    echo "ERROR: Run the script as \"stack\" user."
    exit 1
fi

CURRENT_DIR=$(basename $(pwd))
if [ "${CURRENT_DIR}" != "create_roles" ]; then
    echo "ERROR: Run the script from create_roles directory please."
    exit 1
fi


source /home/stack/stackrc

echo "creating ComputeAvrs Role"
cp -r /usr/share/openstack-tripleo-heat-templates/roles/* ../../roles/
sudo openstack overcloud roles generate --roles-path ../../roles -o ../../roles/ComputeAvrs.yaml Compute
sudo sed -i -e 's/ Compute/ ComputeAvrs/g' ../../roles/ComputeAvrs.yaml
sudo sed -i -e "s/HostnameFormatDefault: '%stackname%-compute-%index%'/HostnameFormatDefault: '%stackname%-computeavrs-%index%'/g" ../../roles/ComputeAvrs.yaml
sudo sed -i -e 's/- OS::TripleO::Services::NovaCompute/- OS::TripleO::Services::NovaComputeAvrs/g'   ../../roles/ComputeAvrs.yaml
openstack overcloud roles generate --roles-path ../../roles -o ../../roles/compute-avrs-role.yaml Controller Compute ComputeAvrs


FILE=../../roles/compute-avrs-role.yaml
if [ -f "$FILE" ]; then
    echo "$FILE has been created"
else
    echo "There was some issue creating $FILE"
fi

echo "Complete!! Created ComputeAvrs Role "
echo "Use ../../environments/compute-avrs-environment.yaml to configure the correct value for AVRS nodes"