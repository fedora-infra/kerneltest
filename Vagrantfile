# -*- mode: ruby -*-
# vi: set ft=ruby :
ENV['VAGRANT_NO_PARALLEL'] = 'yes'

Vagrant.configure(2) do |config|
  config.hostmanager.enabled = true
  config.hostmanager.manage_host = true
  config.hostmanager.manage_guest = true

  config.vm.define "kerneltest" do |kerneltest|
    kerneltest.vm.box_url = "https://download.fedoraproject.org/pub/fedora/linux/releases/38/Cloud/x86_64/images/Fedora-Cloud-Base-Vagrant-38-1.6.x86_64.vagrant-libvirt.box"
    kerneltest.vm.box = "f38-cloud-libvirt"
    kerneltest.vm.hostname = "kerneltest.tinystage.test"

    kerneltest.vm.synced_folder '.', '/vagrant', disabled: true
    kerneltest.vm.synced_folder ".", "/home/vagrant/kerneltest", type: "sshfs"

    kerneltest.vm.provider :libvirt do |libvirt|
      libvirt.cpus = 2
      libvirt.memory = 2048
    end

    kerneltest.vm.provision "ansible" do |ansible|
      ansible.playbook = "devel/ansible/kerneltest.yml"
      ansible.config_file = "devel/ansible/ansible.cfg"
      ansible.verbose = true
    end
  end

end