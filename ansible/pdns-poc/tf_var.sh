export VSPHERE_SERVER=vsphere.example.com
export VSPHERE_PASSWORD=$(vault read -field=password Deptartment/ehw/vsphere)
export VSPHERE_USER=$(whoami)