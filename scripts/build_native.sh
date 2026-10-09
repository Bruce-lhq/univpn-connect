#!/bin/sh
# Run in an extracted/patched OpenConnect tree. Dependencies are OS packages.
set -eu
export CFLAGS="${CFLAGS:--std=gnu11 -O2 -g0} -ffile-prefix-map=$PWD=."
if [ "$(uname -s)" = Darwin ]; then
    export CPPFLAGS="${CPPFLAGS:-} -I$(brew --prefix openssl@3)/include"
    export LDFLAGS="${LDFLAGS:-} -L$(brew --prefix openssl@3)/lib"
    export PKG_CONFIG_PATH="$(brew --prefix openssl@3)/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
fi
sh autogen.sh
./configure --without-gnutls --with-openssl --without-lz4 --without-libpcsclite \
    --without-libproxy --without-stoken --without-libpskc --without-gssapi \
    --disable-nls --with-vpnc-script=/etc/vpnc/vpnc-script
make -j4 P11KIT_LIBS=
case "$(uname -s)" in
    MINGW*|MSYS*) ;; # Windows integration needs its real socket/TUN environment.
    *) python3 tests/univpn-integration.py ./openconnect
       make -C tests univpn-codec buftest seqtest lzstest
       ./tests/univpn-codec && ./tests/buftest && ./tests/seqtest && ./tests/lzstest ;;
esac
