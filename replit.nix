{pkgs}: {
  deps = [
    pkgs.rustc
    pkgs.pkg-config
    pkgs.libxcrypt
    pkgs.libiconv
    pkgs.cargo
    pkgs.libmysqlclient
    pkgs.postgresql
    pkgs.openssl
  ];
}
