# uffd

This is the UserFerwaltungsFrontend.
A web service to manage LDAP users, groups and permissions.

Development chat: [#uffd-development](https://rocket.events.ccc.de/channel/uffd-development)

## dependencies
- python3
- python3-ldap3
- python3-flask
- python3-flask-sqlalchemy
- python3-flask-migrate
- python3-qrcode
- python3-fido2 (version 0.5.0, optional)
- python3-flask-oauthlib
- python3-flask-babel

Some of the dependencies (especially fido2 and flask-oauthlib) changed their API in recent versions, so make sure to install the versions from Debian Buster.
You can also use virtualenv with the supplied `requirements.txt`.

## development

Clone this repository with the `--recurse-submodules` flag to retrieve submodule dependencies.

Before running uffd, you need to create the database with `flask db upgrade`. The database is placed in
`instance/uffd.sqlit3`.

Then use `flask run` to start the application:

```
FLASK_APP=uffd flask db upgrade
FLASK_APP=uffd FLASK_ENV=development flask run
```

During development, you may want to enable LDAP mocking, as you otherwise need to have access to an actual LDAP server with the required schema.
You can do so by setting `LDAP_SERVICE_MOCK=True` in the config.
Afterwards you can login as a normal user with "testuser" and "userpassword", or as an admin with "testadmin" and "adminpassword".
Please note that the mocked LDAP functionality is very limited and many uffd features do not work correctly without a real LDAP server.

## deployment

Use uwsgi. Make sure to run `flask db upgrade` after every update!
For an example uwsgi config, see our [uswgi.ini](uwsgi.ini).

## python style conventions

PEP 8 without double new lines, tabs instead of spaces and a max line length of 160 characters.

## Config

Uffd reads its default config from `uffd/default_config.cfg`.
You can overwrite config variables by creating a config file in the `instance` folder.
The file must be named `conifg.cfg` (Python syntax), `config.json` or `config.yml`/`config.yaml`.
You can also set a custom file name with the environment variable `CONFIG_FILENAME`.

## Bind with service account or as user?

Uffd can use a dedicated service account for LDAP operations by setting `LDAP_SERVICE_BIND_DN`.
Leave that variable blank to use anonymouse bind.
Or set `LDAP_SERVICE_USER_BIND` to use the credentials of the currently logged in user.

If you choose to run with user credentials, some features are not available, like password resets
or self signup, since in both cases, no user credentials can exist. 

## OAuth2 Single-Sign-On Provider

Other services can use uffd as an OAuth2.0-based authentication provider.
The required credentials (client_id, client_secret and redirect_uris) for these services are defined in the config.
The services need to be setup to use the following URLs with the Authorization Code Flow:

* `/oauth2/authorize`: authorization endpoint
* `/oauth2/token`: token request endpoint
* `/oauth2/userinfo`: endpoint that provides information about the current user

The userinfo endpoint returns json data with the following structure:

```
{
  "id": 10000,
  "name": "Test User",
  "nickname": "testuser"
  "email": "testuser@example.com",
  "ldap_dn": "uid=testuser,ou=users,dc=example,dc=com",
  "groups": [
    "uffd_access",
    "users"
  ],
}
```

`id` is the uidNumber, `name` the display name (cn) and `nickname` the uid of the user's LDAP object.


## Translation

The web frontend is initialy written in English and translated in the following Languages:

![status](https://git.cccv.de/uffd/uffd/badges/master/coverage.svg?job=trans_de&key_text=DE)

The selection uses the language browser header by default but can be overwritten via a UI element.
You can specify the availble languages in the config.

## License

GNU Affero General Public License v3.0, see [LICENSE](LICENSE).
