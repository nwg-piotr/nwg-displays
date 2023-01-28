{
  description = "An output management utility for the sway Wayland compositor, inspired by wdisplays and wlay.";
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
  };

  outputs = inputs@{ self, flake-parts, nixpkgs, ...  }:
    flake-parts.lib.mkFlake {inherit inputs;} {
      # TODO: This probably works on more linux architechtures but I haven't tested them
      systems = ["x86_64-linux"];
      imports = [];

      perSystem = { config, inputs', pkgs, system, ... }: 
        {
          packages = rec {
            default = nwg-displays;
            nwg-displays = pkgs.python3Packages.buildPythonApplication
            rec {
              pname = "nwg-displays";
              version = "0.1.4";
              doCheck = false;
              src = self;

              nativeBuildInputs = [
                pkgs.wrapGAppsHook
                pkgs.gobject-introspection
              ];

              buildInputs = with pkgs; [
                gtk3
              ];

              propagatedBuildInputs = with pkgs; [
                pango
                gtk-layer-shell
                gdk-pixbuf
                atk
                python310Packages.i3ipc
                python310Packages.pygobject3
                python310Packages.gst-python
              ];

              dontWrapGApps = true;

              preFixup = ''
                makeWrapperArgs+=("''${gappsWrapperArgs[@]}");
              '';
            };
          };
        };
      };
}
