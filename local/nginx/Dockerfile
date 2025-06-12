ARG ALPINE_VERSION=3.21
ARG OPENSSL_TAG=openssl-3.4.0
ARG LIBOQS_TAG=0.12.0
ARG OQSPROVIDER_TAG=0.8.0
ARG NGINX_VERSION=1.27.3
ARG BASEDIR="/opt"
ARG INSTALLDIR=${BASEDIR}/nginx
ARG DEFAULT_GROUPS=x25519:x448:prime256v1:secp384r1:secp521r1:mlkem512:mlkem768:mlkem1024:X25519MLKEM768:SecP256r1MLKEM768
ARG OSSLDIR=${BASEDIR}/openssl/.openssl

FROM alpine:${ALPINE_VERSION} AS builder
ARG OPENSSL_TAG LIBOQS_TAG OQSPROVIDER_TAG NGINX_VERSION BASEDIR INSTALLDIR DEFAULT_GROUPS OSSLDIR
RUN apk update && apk --no-cache add build-base linux-headers libtool automake autoconf make cmake ninja git wget pcre-dev openssl openssl-dev
WORKDIR /opt
RUN git clone --depth 1 --branch ${LIBOQS_TAG} https://github.com/open-quantum-safe/liboqs \
    && git clone --depth 1 --branch ${OQSPROVIDER_TAG} https://github.com/open-quantum-safe/oqs-provider.git \
    && git clone --depth 1 --branch ${OPENSSL_TAG} https://github.com/openssl/openssl.git \
    && wget -q nginx.org/download/nginx-${NGINX_VERSION}.tar.gz \
    && tar -zxf nginx-${NGINX_VERSION}.tar.gz && rm nginx-${NGINX_VERSION}.tar.gz

WORKDIR /opt/liboqs/build
RUN cmake -G"Ninja" -DOQS_DIST_BUILD=ON -DBUILD_SHARED_LIBS=OFF -DCMAKE_INSTALL_PREFIX="${INSTALLDIR}" .. \
    && ninja -j"$(nproc)" install

WORKDIR /opt/nginx-${NGINX_VERSION}
RUN ./configure --prefix=${INSTALLDIR} --with-debug --with-http_ssl_module --with-openssl=/opt/openssl --without-http_gzip_module \
    && make -j"$(nproc)" install

RUN mkdir -p ${OSSLDIR}/ssl \
    && cp /opt/openssl/apps/openssl.cnf ${OSSLDIR}/ssl/ \
    && sed -i -e "s/default = default_sect/default = default_sect\noqsprovider = oqsprovider_sect/g" \
              -e "s/\[default_sect\]/\[default_sect\]\nactivate = 1\n\[oqsprovider_sect\]\nactivate = 1\n/g" \
              -e "s/providers = provider_sect/providers = provider_sect\nssl_conf = ssl_sect\n\n\[ssl_sect\]\nsystem_default = system_default_sect\n\n\[system_default_sect\]\nGroups = \$ENV\:\:DEFAULT_GROUPS\n/g" \
              -e "s/HOME\t\t\t= ./HOME\t\t= .\nDEFAULT_GROUPS\t= ${DEFAULT_GROUPS}/g" ${OSSLDIR}/ssl/openssl.cnf

WORKDIR /opt/oqs-provider
RUN ln -s "/opt/nginx/include/oqs" "${OSSLDIR}/include" \
    && cmake -DCMAKE_BUILD_TYPE=Debug -DOPENSSL_ROOT_DIR="${OSSLDIR}" -DCMAKE_PREFIX_PATH="${INSTALLDIR}" -S . -B build \
    && cmake --build build \
    && cp build/lib/oqsprovider.so "$(find "${OSSLDIR}" -name ossl-modules)" \
    && mkdir -p "${OSSLDIR}/lib64" && ln -s "${OSSLDIR}/lib/ossl-modules" "${OSSLDIR}/lib64"

WORKDIR ${INSTALLDIR}
ENV PATH="${INSTALLDIR}/sbin:${OSSLDIR}/bin:${PATH}"
RUN strip "${OSSLDIR}/lib/"*.a "${OSSLDIR}/lib64/ossl-modules/oqsprovider.so" "${INSTALLDIR}/sbin/"*

FROM alpine:${ALPINE_VERSION}
ARG INSTALLDIR BASEDIR OSSLDIR
RUN apk update && apk --no-cache add pcre-dev python3 py3-psutil py3-pandas openssl
COPY --from=builder ${INSTALLDIR} ${INSTALLDIR}
COPY --from=builder ${OSSLDIR} ${OSSLDIR}
RUN ln -sf /dev/stdout "${INSTALLDIR}/logs/access.log" && ln -sf /dev/stderr "${INSTALLDIR}/logs/error.log"
EXPOSE 4433
ENV PATH="${INSTALLDIR}/sbin:${PATH}" OPENSSL_CONF="${OSSLDIR}/ssl/openssl.cnf"
STOPSIGNAL SIGTERM