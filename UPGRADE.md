# Upgrading from v1 to v2

Prior to v2 uffd stored users, groups and mail aliases on an LDAP server.
OAuth2 and API client credentials were defined in the config. Starting with
v2 uffd stores all of this in its database and no longer supports LDAP.
A number of other features and configurations are no longer supported. See the
changelog for details on changed and removed features.

## Preparations

Create a backup of the database before attempting an upgrade. The database
migration scripts are quite complex and somewhat fragile. If anything fails,
you will end up with a broken database that is difficult or impossible to
recover from. Furthermore downgrading from v2 to v1 is not supported.

Make sure no service (besides uffd) directly accesses your LDAP server.
Migrate any remaining services to [uffd-ldapd][] or other solutions that
solely rely on uffds API and OAuth2 endpoints. Uffd will cease to update
any data stored in the LDAP directory.

Migrate all API clients defined with the `API_CLIENTS` config option to the
`API_CLIENTS_2` option. This includes changing authentication from a
token-based mechanism to HTTP Basic Authentication and consequently replacing
affected credentials.

The imported OAuth2 and API clients are grouped by service objects. These
service objects will be auto-created for each client with unique names derived
from the `client_id` parameter. Add the `service_name` parameter to clients to
set a custom name. This name is visible to users in place of the OAuth2
`client_id`. Use the same `service_name` for multiple clients to group them
together. This is recommended for OAuth2 and API credentials used by the same
services, as future features like service-specific email addresses will be
added as service-level options. The OAuth2 client parameter `required_group` is
imported as a service-level option. Make sure that grouped OAuth2 clients have
the same `required_group` value, otherwise nobody will be able to access the
service. Note that values other than a single group name are not supported.

Adjust the ACLs of your LDAP server so uffd can read the `userPassword`
attribute of user objects. Note that uffd will not perform any writes to the
LDAP server during or after the upgrade.

If you use user bind (config option `LDAP_SERVICE_USER_BIND`), i.e. if you
have uffd authenticate with the LDAP server using the credentials of the
currently logged in user, you will have to replace this configuration and
grant uffd full read access to all user, group and mail alias data with
config-defined credentials.

Install the new dependency `python3-argon2`. (Dist-)Upgrading the Debian
package will do that for you. Do not uninstall the removed dependency
`python3-ldap3` (i.e. do not run `apt autoremove`)! It is required to import
data from the LDAP server.

There is a safeguard in place to prevent accidental upgrades. Add the
following line to your config file to disable the safeguard:

```
UPGRADE_V1_TO_V2=True
```

## Running the Upgrade

Upgrade the Debian package to v2. This will restart the uffd UWSGI app. With
the default UWSGI configuration, the database migration scripts will run
automatically.

Otherwise run them manually:

```
uffd-admin db upgrade
```

The database migration scripts import users, groups and mail aliases from the
configured LDAP server. They also import OAuth2 and API clients defined with
the `OAUTH2_CLIENTS` and `API_CLIENTS_2` config options to the database.

Due to data being split between the LDAP server and the database, uffd v1
tended to accumulate orphaned database objects (e.g. role memberships of
deleted users). All orphaned objects are deleted during the upgrade.

As a side-effect upgrading resets all rate limits.

## Follow-up

Rename the following config options:

* `LDAP_USER_GID` -> `USER_GID`
* `LDAP_USER_MIN_UID` -> `USER_MIN_UID`
* `LDAP_USER_MAX_UID` -> `USER_MAX_UID`
* `LDAP_USER_SERVICE_MIN_UID` -> `USER_SERVICE_MIN_UID`
* `LDAP_USER_SERVICE_MAX_UID` -> `USER_SERVICE_MAX_UID`

Add the following config options:

* `GROUP_MIN_GID`
* `GROUP_MAX_GID`

Remove the following config options:

* `UPGRADE_V1_TO_V2`
* `LDAP_USER_SEARCH_BASE`
* `LDAP_USER_SEARCH_FILTER`
* `LDAP_USER_OBJECTCLASSES`
* `LDAP_USER_DN_ATTRIBUTE`
* `LDAP_USER_UID_ATTRIBUTE`
* `LDAP_USER_UID_ALIASES`
* `LDAP_USER_LOGINNAME_ATTRIBUTE`
* `LDAP_USER_LOGINNAME_ALIASES`
* `LDAP_USER_DISPLAYNAME_ATTRIBUTE`
* `LDAP_USER_DISPLAYNAME_ALIASES`
* `LDAP_USER_MAIL_ATTRIBUTE`
* `LDAP_USER_MAIL_ALIASES`
* `LDAP_USER_DEFAULT_ATTRIBUTES`
* `LDAP_GROUP_SEARCH_BASE`
* `LDAP_GROUP_SEARCH_FILTER`
* `LDAP_GROUP_GID_ATTRIBUTE`
* `LDAP_GROUP_NAME_ATTRIBUTE`
* `LDAP_GROUP_DESCRIPTION_ATTRIBUTE`
* `LDAP_GROUP_MEMBER_ATTRIBUTE`
* `LDAP_MAIL_SEARCH_BASE`
* `LDAP_MAIL_SEARCH_FILTER`
* `LDAP_MAIL_OBJECTCLASSES`
* `LDAP_MAIL_DN_ATTRIBUTE`
* `LDAP_MAIL_UID_ATTRIBUTE`
* `LDAP_MAIL_RECEIVERS_ATTRIBUTE`
* `LDAP_MAIL_DESTINATIONS_ATTRIBUTE`
* `LDAP_SERVICE_URL`
* `LDAP_SERVICE_USE_STARTTLS`
* `LDAP_SERVICE_BIND_DN`
* `LDAP_SERVICE_BIND_PASSWORD`
* `LDAP_SERVICE_USER_BIND`
* `ENABLE_INVITE`
* `ENABLE_PASSWORDRESET`
* `ENABLE_ROLESELFSERVICE`
* `OAUTH2_CLIENTS`
* `API_CLIENTS` (should not be set, see "Preparation")
* `API_CLIENTS_2`
* `LDAP_SERVICE_MOCK` (development option, should not be set)

If you set a custom config filename with the environment variable
`CONFIG_FILENAME`, replace it with `CONFIG_PATH`. The new variable must be
set to a full path instead of a filename.

If you set the config option `ACL_SELFSERVICE_GROUP`, but not
`ACL_ACCESS_GROUP`, make sure to set `ACL_ACCESS_GROUP` to the same value as
`ACL_SELFSERVICE_GROUP`.

Add a cron job that runs `uffd-admin cleanup` at least daily. Unless you
modified `/etc/cron.d/uffd`, upgrading the Debian package will do this for you.

Uninstall the previous dependency `python3-ldap3` (i.e. run `apt autoremove`).

[uffd-ldapd]: https://git.cccv.de/uffd/uffd-ldapd
