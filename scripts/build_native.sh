#!/bin/sh
# Run in an extracted/patched OpenConnect tree. Dependencies are OS packages.
set -eu
export CFLAGS="${CFLAGS:--std=gnu11 -O2 -g0} -ffile-prefix-map=$PWD=."
if [ "$(uname -s)" = Darwin ]; then
    export CPPFLAGS="${CPPFLAGS:-} -I$(brew --prefix openssl@3)/include"
    export LDFLAGS="${LDFLAGS:-} -L$(brew --prefix openssl@3)/lib"
    export PKG_CONFIG_PATH="$(brew --prefix openssl@3)/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
fi
case "$(uname -s)" in
    MINGW*|MSYS*)
        # Some MSYS2 runners omit this MinGW compatibility header although
        # OpenConnect only needs errno_t from it.
        mkdir -p sec_api
        if [ ! -f sec_api/stdlib_s.h ]; then
            cat > sec_api/stdlib_s.h <<'EOF'
#ifndef UNIVPN_STDLIB_S_H
#define UNIVPN_STDLIB_S_H
typedef int errno_t;
#endif
EOF
        fi
        export CPPFLAGS="${CPPFLAGS:-} -I$PWD"
        ;;
esac
sh autogen.sh
./configure --without-gnutls --with-openssl --without-lz4 --without-libpcsclite \
    --without-libproxy --without-stoken --without-libpskc --without-gssapi \
    --disable-nls --with-vpnc-script=/etc/vpnc/vpnc-script
make -j4 P11KIT_LIBS=
case "$(uname -s)" in
    MINGW*|MSYS*) ;; # Windows integration needs its real socket/TUN environment.
    *) if [ -f tests/univpn-integration.py ]; then
           python3 tests/univpn-integration.py ./openconnect
       fi
       if [ -f tests/univpn-codec.c ]; then
           ${CC:-cc} -I. tests/univpn-codec.c -o tests/univpn-codec
           ./tests/univpn-codec
       fi
       make -C tests buftest seqtest lzstest
       ./tests/buftest && ./tests/seqtest && ./tests/lzstest ;;
esac
