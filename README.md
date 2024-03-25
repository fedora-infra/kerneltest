# kerneltest

This is a small web application to display the results of the different
tests performed on kernels.

This application is currently deployed at:

https://kerneltest.fedoraproject.org/


## Development Envrionment

Quickly start hacking on kerneltest using the vagrant setup that is included in the
repo is super simple.

1. Set up tinystage (if you haven't already) and ensure the base boxes are running.

   https://github.com/fedora-infra/tiny-stage

   This sets up the infrastructure to use things like authentication and Fedora Messaging
   when developing on kerneltest

2. Check out the repo, and run:

   `vagrant up`

   to provision your kerneltest instance

3. Kerneltest will be available at https://kerneltest.tinystage.test/

## Deploying

### Staging
To deploy to https://kerneltest.stg.fedoraproject.org, merge the changes required into the
staging branch, and they will be deployed in a few minutes.

### Production
To deploy to https://kerneltest.fedoraproject.org, merge the changes required into the
stable branch, and they will be deployed in a few minutes.
