ARG ALPINE_VERSION=3.21
ARG OPENSSL_TAG=openssl-3.4.0
ARG LIBOQS_TAG=0.12.0
ARG OQSPROVIDER_TAG=0.8.0
ARG CURL_VERSION=8.11.1
ARG INSTALLDIR=/opt/oqssa
ARG DEFAULT_GROUPS="x25519:x448:kyber512:p256_kyber512:kyber768:p384_kyber768:kyber1024:p521_kyber1024"

FROM alpine:${ALPINE_VERSION} AS intermediate
ARG OPENSSL_TAG LIBOQS_TAG OQSPROVIDER_TAG CURL_VERSION INSTALLDIR DEFAULT_GROUPS

RUN apk update && apk --no-cache add build-base linux-headers libtool automake autoconf cmake ninja make openssl openssl-dev git wget

WORKDIR /opt
RUN git clone --depth 1 --branch ${LIBOQS_TAG} https://github.com/open-quantum-safe/liboqs && \
    git clone --depth 1 --branch ${OPENSSL_TAG} https://github.com/openssl/openssl.git && \
    git clone --depth 1 --branch ${OQSPROVIDER_TAG} https://github.com/open-quantum-safe/oqs-provider.git && \
    wget -q https://curl.haxx.se/download/curl-${CURL_VERSION}.tar.gz && tar -zxf curl-${CURL_VERSION}.tar.gz

WORKDIR /opt/liboqs/build
RUN cmake -G"Ninja" .. -DOQS_DIST_BUILD=ON -DCMAKE_INSTALL_PREFIX="${INSTALLDIR}" && ninja install

WORKDIR /opt/openssl
RUN ln -s ${INSTALLDIR}/lib64 ${INSTALLDIR}/lib 2>/dev/null || true && \
    ln -s ${INSTALLDIR}/lib ${INSTALLDIR}/lib64 2>/dev/null || true && \
    LDFLAGS="-Wl,-rpath -Wl,${INSTALLDIR}/lib64" ./config shared --prefix="${INSTALLDIR}" && \
    make -j$(nproc) && make install_sw install_ssldirs

ENV PATH="${INSTALLDIR}/bin:${PATH}"

WORKDIR /opt/oqs-provider
RUN ln -s ../openssl . && \
    cmake -DOPENSSL_ROOT_DIR="${INSTALLDIR}" -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="${INSTALLDIR}" -S . -B _build && \
    cmake --build _build && \
    cp _build/lib/oqsprovider.so "${INSTALLDIR}/lib64/ossl-modules" && \
    sed -i -e "s/default = default_sect/default = default_sect\noqsprovider = oqsprovider_sect/g" \
           -e "s/\[default_sect\]/\[default_sect\]\nactivate = 1\n\[oqsprovider_sect\]\nactivate = 1\n/g" \
           -e "s/providers = provider_sect/providers = provider_sect\nssl_conf = ssl_sect\n\n\[ssl_sect\]\nsystem_default = system_default_sect\n\n\[system_default_sect\]\nGroups = \$ENV::DEFAULT_GROUPS\n/g" \
           -e "s/\# Use this in order to automatically load providers/\# Set default KEM groups if not set via environment variable\nKDEFAULT_GROUPS = $DEFAULT_GROUPS\n\n# Use this in order to automatically load providers/g" \
           -e "s/HOME\t\t\t= ./HOME\t\t= .\nDEFAULT_GROUPS\t= ${DEFAULT_GROUPS}/g" ${INSTALLDIR}/ssl/openssl.cnf

WORKDIR /opt/curl-${CURL_VERSION}
RUN env LDFLAGS="-Wl,-R${INSTALLDIR}/lib64" ./configure --prefix="${INSTALLDIR}" --with-ssl="${INSTALLDIR}" --without-libpsl && \
    make -j$(nproc) && make install

FROM alpine:${ALPINE_VERSION} AS final
ARG INSTALLDIR

RUN apk update && apk --no-cache add \
    python3 py3-pip py3-setuptools py3-wheel \
    py3-psutil py3-pandas tshark \
    build-base curl-dev libffi-dev openssl-dev \
    musl-dev linux-headers python3-dev

COPY --from=intermediate ${INSTALLDIR} ${INSTALLDIR}
ENV PATH="${INSTALLDIR}/bin:${PATH}" \
    PYCURL_CURL_CONFIG=${INSTALLDIR}/bin/curl-config

RUN pip install --no-binary :all: pycurl --break-system-packages

COPY --from=intermediate ${INSTALLDIR}/bin/curl /usr/bin/curl
COPY --from=intermediate ${INSTALLDIR}/lib/ /usr/lib/
COPY --from=intermediate ${INSTALLDIR}/ssl /etc/ssl

RUN cp -a ${INSTALLDIR}/lib64/libcurl.so* /usr/lib/ 2>/dev/null || true && \
    cp -a ${INSTALLDIR}/lib64/libssl.so* /usr/lib/ 2>/dev/null || true && \
    cp -a ${INSTALLDIR}/lib64/libcrypto.so* /usr/lib/ 2>/dev/null || true
