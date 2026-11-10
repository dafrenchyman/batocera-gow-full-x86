let
  pkgs = import (builtins.fetchTarball {
    url = "https://github.com/NixOS/nixpkgs/archive/1f607aa79b6356ed45d3cd3c8079c196e79efa2c.tar.gz";
  }) {system = "x86_64-linux";};
in {
  inherit (pkgs) xwayland xauth util-linux mesa;
}
