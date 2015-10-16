# Vault
Admin webapp for Openstack's Keystone services. Bundled with Swift UI.

### Short description
Like Openstack Horizon, Vault is a Front-End for services handled by Keystone, but with minimal configurantion and dependencies.

You can:

- Manage users and tenants on your Keystone service.

- manage containers and objects on Swift. (A customized version of [django-swiftbrowser](https://github.com/cschwede/django-swiftbrowser))

- take your service, add it`s endpoints to Keystone and create a Django App inside Vault to manage it.

### Basic setup (production)
=======

1) install dependencies

    $ pip install -r requirements.txt

2) set environment variables

    $ export VAULT_DEBUG=False
    $ export VAULT_PAGINATION_SIZE=10  # Default number of items for pages with lists
    $ export VAULT_STATIC_URL='http://your-static-url'
 
    $ export VAULT_MYSQL_USER=(vault mysql user)
    $ export VAULT_MYSQL_PASSWORD=(vault mysql password)
    $ export VAULT_MYSQL_PORT=3306  # Or your custom mysql port
    $ export VAULT_MYSQL_HOST=(vault mysql host) 
   
    $ export VAULT_KEYSTONE_URL='https://your-keystone-url:5000'
    $ export VAULT_KEYSTONE_USERNAME=user  # user with keystone/services superpowers
    $ export VAULT_KEYSTONE_PASSWORD=pass
    $ export VAULT_KEYSTONE_PROJECT=project  # default project to use with Keystone
    $ export VAULT_KEYSTONE_ROLE=uuid  # swiftoperator role ID 


3) create a mysql database named "vault"

    # on mysql: 'create database vault;'
    $ python manage.py syncdb

4) run

    $ python manage.py runserver

### static files
    $ python manage.py collectstatic --noinput

    # upload your static files to your static_url
    # if Swift do:
    $ cd statictemp
    $ swift -A https://your-keystone-url:5000/v2.0 -V 2.0 -U <user> -K <password> --os-tenant-name <project> --os-endpoint-type adminURL upload <your-container> .

### To run tests
    pip install -r requirements_test.txt
    make tests

=======
### Compatibilities

- Django 1.7
- Swift 2.1.0 (auth v2.0)
- Keystone 2014.1

### Screenshots

![Login](screenshots/vault_login.png)
![Dashboard](screenshots/vault_dashboard.png)
