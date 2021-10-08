FROM registry.git.cccv.de/uffd/docker-images/bullseye AS builder

ENV DEBIAN_FRONTEND=noninteractive
ENV PYBUILD_INSTALL_ARGS="--install-lib=/usr/share/uffd/ --install-scripts=/usr/share/uffd/"

RUN mkdir /build-dir && mkdir /build
WORKDIR /build-dir

COPY . .

RUN set -x && \
    ./debian/create_changelog.py uffd > debian/changelog && \
    dpkg-buildpackage -us -uc && \
    dpkg-deb -I /*.deb && \
    dpkg-deb -c /*.deb && \
    mv /*.deb /build/uffd.deb

FROM debian:bullseye

COPY --from=builder /build/uffd.deb /uffd.deb

RUN set -x && \
    apt update && \
    apt install -y --no-install-recommends /uffd.deb python3-psycopg2 python3-pymysql && \
    rm -rf /var/lib/apt/lists/* && \
    rm /uffd.deb && \
    cat /etc/uffd/uffd.cfg | grep -v "SECRET_KEY=" > /etc/uffd/uffd.cfg.tmp && \
    mv /etc/uffd/uffd.cfg.tmp /etc/uffd/uffd.cfg && \
    mkdir --parents /var/www/uffd && \
    chown root:uffd /var/www/uffd

COPY .docker/entrypoint.sh /entrypoint.sh

USER uffd
USER root

EXPOSE 3031/tcp
EXPOSE 9191/tcp

CMD bash /entrypoint.sh

LABEL project="https://git.cccv.de/uffd/uffd"
