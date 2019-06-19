#!/usr/bin/env bash

set -o errexit
set -o nounset
set -x

if [ "${USER}" != "stack" ]; then
    echo "ERROR: Run the script as \"stack\" user."
    exit 1
fi

source /home/stack/stackrc

roles=(ComputeAvrsSingle ComputeAvrsDual)
echo "creating ${roles[*]} Role"

cp -r /home/stack/openstack-tripleo-heat-templates/roles/* ../../roles/

for role in "${roles[@]}"; do
    sudo openstack overcloud roles generate --roles-path ../../roles -o ../../roles/${role}.yaml Compute
    sudo sed -i -e "s/ Compute/ ${role}/g' ../../roles/${role}.yaml
    sudo sed -i -e "s/HostnameFormatDefault: '%stackname%-compute-%index%'/HostnameFormatDefault: '%stackname%-${role,,}-%index%'/g" ../../roles/${role}.yaml
    sudo sed -i -e "s/- OS::TripleO::Services::NovaCompute/- OS::TripleO::Services::${role}/g'   ../../roles/${role}.yaml
done


openstack overcloud roles generate --roles-path ../../roles -o ../../roles/compute-avrs-role.yaml Controller Compute  ${roles[*]}

echo "Complete!! Created  ${roles[*]} Roles "
echo "Use ../environments/avrs-multirole-environment-sample.yaml to configure the correct value for AVRS nodes"