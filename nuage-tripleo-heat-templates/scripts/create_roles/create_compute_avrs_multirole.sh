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

roles=(ComputeAvrsSingle ComputeAvrsDual)
echo "creating ${roles[*]} Role"

cp -r /usr/share/openstack-tripleo-heat-templates/roles/* ../../roles/

for role in "${roles[@]}"; do
    sudo openstack overcloud roles generate --roles-path ../../roles -o ../../roles/${role}.yaml Compute
    sudo sed -i -e "s/ Compute/ ${role}/g" ../../roles/${role}.yaml
    sudo sed -i -e "s/HostnameFormatDefault: '%stackname%-compute-%index%'/HostnameFormatDefault: '%stackname%-${role,,}-%index%'/g" ../../roles/${role}.yaml
    sudo sed -i -e "s/- OS::TripleO::Services::NovaCompute/- OS::TripleO::Services::${role}/g"   ../../roles/${role}.yaml
    FILE=../../roles/${role}.yaml
    if [ -f "$FILE" ]; then
        echo "$FILE has been created"
    else
        echo "There was some issue creating $FILE"
    fi
done


openstack overcloud roles generate --roles-path ../../roles -o ../../roles/compute-avrs-role.yaml Controller Compute  ${roles[*]}

echo "Complete!! Created  ${roles[*]} Roles "
echo "Use ../../environments/compute-avrs-multirole-environment.yaml to configure the correct value for AVRS nodes"
