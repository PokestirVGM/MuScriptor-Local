# Application icon

The waveform-and-note mark is the official upstream MuScriptor mark, copied from
`web/public/muscriptor-mark-v4.svg` at the revision in `upstream-revision.txt`.
Source: https://github.com/muscriptor/muscriptor (Kyutai x Mirelo, MIT; see
`licenses/MuScriptor-MIT.txt`). MuScriptor Local remains an independent launcher.

`muscriptor.svg` is the original vector. `muscriptor.png` is a 1024-pixel render
made with resvg. The ICO contains 16, 24, 32, 48, 64, 128, and 256-pixel sizes;
the ICNS contains the macOS sizes through 1024 pixels. Both were encoded from
the PNG using Pillow. Normal app builds use these checked-in assets and do not
need an image-generation tool or additional graphics dependencies.

Windows embeds the ICO in the executable and setup installer and uses it for
the window/taskbar icon. macOS copies the ICNS into the bundle and declares it
in Info.plist. Previously published macOS packages are not changed.
