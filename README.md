    # SigmaOS-theming-native

    Native (CSD-less) theming engine

    Part of the **SigmaOS** sovereign operating-system ecosystem — a multi-repository
    distribution modelled on Linux Mint and Omarchy Linux. See the parent
    [`SigmaOS`](https://github.com/AaryanSinghChauhan09/SigmaOS) repository for the
    full component index.

    ## Upstream inspirations
    - https://github.com/omacom/aether

    ## Design principles applied
    - **Abstraction**
- **Generalisation**
- **Plan Before Act**
- **Fail-Fast**
- **Defensive Programming**
- **DRY**
- **KISS**
- **Deterministic Testing**

    ## Usage
    Verbs: `list, apply-plan, sync-plan, palette, cursor, icons, diff`

    ```
    $ sigma-theme list --root ~/.themes
Mint-Y      Mint-Y      Standard dark-neutral theme
Mint-Y-Dark Mint-Y-Dark Dark variant
$ sigma-theme apply-plan --root ~/.themes --set gtk-theme=Mint-Y-Dark --set cursor-size=32
gsettings set org.gnome.desktop.interface gtk-theme 'Mint-Y-Dark'
$ sigma-theme palette ./A --compare ./B
changed bg: #1e1e2e -> #181825 (delta 12)
$ sigma-theme icons Mint-Y-Dark --root ~/.themes
Mint-Y-Dark inherits: Mint-Y, Adwaita  [ok]
$ sigma-theme sync-plan ./src/theme ./build/theme
$ sigma-theme diff ./A ./B

    ```

    ## Build & test
    ```
    make build
    make test
    ```

    ## Licence
    GNU General Public License v3.0 (FOSS).
