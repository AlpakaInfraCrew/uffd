# Uffd

Uffd (UserFerwaltungsFrontend) is a web-based user management and single sign-on software.

Development chat: [#uffd-development](https://rocket.cccv.de/channel/uffd-development)

## Dependencies

Please note that we refer to Debian packages here and **not** pip packages.

- python3
- python3-flask
- python3-flask-sqlalchemy
- python3-flask-migrate
- python3-qrcode
- python3-fido2 (version 0.5.0 or 0.9.1, optional)
- python3-prometheus-client (optional, needed for metrics)
- python3-redis (optional, needed for redis support)
- python3-oauthlib
- python3-flask-babel
- python3-argon2
- python3-itsdangerous (also a dependency of python3-flask)
- python3-mysqldb or python3-pymysql for MySQL/MariaDB support

Some of the dependencies (especially fido2) changed their API in recent versions, so make sure to install the versions from Debian Buster or Bullseye.
For development, you can also use virtualenv with the supplied `requirements.txt`.

## Development

Before running uffd, you need to create the database with `flask db upgrade`. The database is placed in
`instance/uffd.sqlit3`.

Then use `flask run` to start the application:

```
FLASK_APP=uffd flask db upgrade
FLASK_APP=uffd FLASK_ENV=development flask run
```

During development, you may want to create some example data:

```
export FLASK_APP=uffd
flask group create 'uffd_access' --description 'Access to Single-Sign-On and Selfservice'
flask group create 'uffd_admin' --description 'Admin access to uffd'
flask role create 'base' --default --add-group 'uffd_access'
flask role create 'admin' --add-group 'uffd_admin'
flask user create 'testuser' --password 'userpassword' --mail 'test@example.com' --displayname 'Test User'
flask user create 'testadmin' --password 'adminpassword' --mail 'admin@example.com' --displayname 'Test Admin' --add-role 'admin'
```

Afterwards you can login as a normal user with "testuser" and "userpassword", or as an admin with "testadmin" and "adminpassword".

## Deployment

Do not use `pip install uffd` for production deployments!
The dependencies of the pip package roughly represent the versions shipped by Debian stable.
We do not keep them updated and we do not test the pip package!
The pip package only exists for local testing/development and to help build the Debian package.

We provide packages for Debian stable and oldstable (currently Bullseye and Buster).
Since all dependencies are available in the official package mirrors, you will get security updates for everything but uffd itself from Debian.

To install uffd on Debian Bullseye, add our package mirror to `/etc/sources.list`:

```
deb https://packages.cccv.de/uffd bullseye main
```

Then download [cccv-archive-key.gpg](cccv-archive-key.gpg) and add it to the trusted repository keys in `/etc/apt/trusted.gpg.d/`.
Afterwards run `apt update && apt install uffd` to install the package.

The Debian package uses uwsgi to run uffd and ships an `uffd-admin` to execute flask commands in the correct context.
If you upgrade, make sure to run `flask db upgrade` after every update! The Debian package takes care of this by itself using uwsgi pre start hooks.
For an example uwsgi config, see our [uswgi.ini](uwsgi.ini). You might find our [nginx include file](nginx.include.conf) helpful to setup a web server in front of uwsgi.

## Python Coding Style Conventions

PEP 8 without double new lines, tabs instead of spaces and a max line length of 160 characters.
We ship a [pylint](https://pylint.org/) config to verify changes with.

## Configuration

Uffd reads its default config from `uffd/default_config.cfg`.
You can overwrite config variables by creating a config file in the `instance` folder.
The file must be named `config.cfg` (Python syntax), `config.json` or `config.yml`/`config.yaml`.
You can also set a custom file path with the environment variable `CONFIG_PATH`.

## OAuth2 Single-Sign-On Provider

Other services can use uffd as an OAuth2.0-based authentication provider.
The required credentials (client_id, client_secret and redirect_uris) for these services are defined in the config.
The services need to be setup to use the following URLs with the Authorization Code Flow:

* `/oauth2/authorize`: authorization endpoint
* `/oauth2/token`: token request endpoint
* `/oauth2/userinfo`: endpoint that provides information about the current user

The only OAuth2 scope supported is `profile`. The userinfo endpoint returns json data with the following structure:

```
{
  "id": 10000,
  "name": "Test User",
  "nickname": "testuser"
  "email": "testuser@example.com",
  "groups": [
    "uffd_access",
    "users"
  ],
}
```

`id` is the numeric (Unix) user id, `name` the display name and `nickname` the loginname of the user.

## Metrics

Uffd can export metrics in a prometheus compatible way. It needs python3-prometheus-client for this feature to work.
Metrics can be accessed via `/metrics` and `/api/v1/metrics_prometheus`.
Those endpoints are protected via api credentials. Add prometheus in the uffd UI as a service and create an
api client with the `metrics` permission. Then you can access the metrics like that:

```
$ curl localhost:5000/api/v1/metrics_prometheus --user api-user:api-password
# HELP python_info Python platform information
# TYPE python_info gauge
python_info{implementation="CPython",major="3",minor="9",patchlevel="2",version="3.9.2"} 1.0
# HELP uffd_version_info Various version infos
# TYPE uffd_version_info gauge
uffd_version_info{version="local"} 1.0
[..]
```

## Translation

The web frontend is initially written in English and translated in the following Languages:

![status](https://git.cccv.de/uffd/uffd/badges/master/coverage.svg?job=trans_de&key_text=DE)

The selection uses the language browser header by default but can be overwritten via a UI element.
You can specify the available languages in the config.

Use the `update_translations.sh` to update the translation files.

## License

GNU Affero General Public License v3.0, see [LICENSE](LICENSE).
