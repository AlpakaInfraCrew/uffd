#!/bin/bash

echo "Copying static files ..."
cp -r /usr/share/uffd/uffd/static /var/www/uffd

db_ready="false"
count=0
while [ $count -lt 4 ] && [ "$db_ready" != "true" ] ;do
  if uffd-admin db current >> /dev/null 2>&1 ;then
    db_ready="true"
  else
    echo "Waiting for db to become ready..."
    ((duration=2**$count))
    sleep $duration
    ((count=$count+1))
  fi
done

if [ "$db_ready" == "true" ] ;then
  echo "Running datbase migrations ..."
  uffd-admin db upgrade

  if [ -n "$UFFD_INITIAL_ADMIN_PW" ] && [ "$(uffd-admin user list)" == "" ]; then
    echo "Creating groups and roles for initial admin user ..."
    if ! uffd-admin group show 'uffd_admin' >> /dev/null 2>&1 ;then
      uffd-admin group create 'uffd_admin'
    fi
    if ! uffd-admin group show 'uffd_access' >> /dev/null 2>&1 ;then
      uffd-admin group create 'uffd_access'
    fi
    if ! uffd-admin role show 'uffd_admin' >> /dev/null 2>&1 ;then
      uffd-admin role create 'uffd_admin' --add-group 'uffd_admin' --add-group 'uffd_access'
    fi
    if [ -z "$UFFD_INITIAL_ADMIN_USER" ] ;then
      UFFD_INITIAL_ADMIN_USER='uffd_admin'
    fi
    if [ -z "$UFFD_INITIAL_ADMIN_MAIL" ] ;then
      UFFD_INITIAL_ADMIN_MAIL='uffd_admin@localhost'
    fi
    echo "Creating initial admin user ..."
    uffd-admin user create "$UFFD_INITIAL_ADMIN_USER" --password "$UFFD_INITIAL_ADMIN_PW" --mail "$UFFD_INITIAL_ADMIN_MAIL" --add-role 'uffd_admin'
  fi
else
  echo "WARNING: Database is not ready yet, skipping migration and initialization"
fi

echo "Starting server ..."
runuser --preserve-environment -u uffd -- \
 uwsgi --ini /etc/uwsgi/apps-enabled/uffd.ini --socket 0.0.0.0:3031 --master --stats 0.0.0.0:9191
