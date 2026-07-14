# ADB Root Shell for DJI RC2 (RC331)

This repository documents how to get an ADB root shell on the DJI RC2.

## Requirements

- `adb-shell`
- `libusb1`

## Usage

1. Connect the RC2 via USB.
2. Make sure no ADB server is running in the background. Otherwise the USB device cannot be claimed.
3. Run `djiadb.py`.
4. Accept the connection prompt on the RC2.
5. You should now have a simple interactive ADB root shell.

## Useful Commands

To transfer files, use normal file transfer. The "Internal shared storage" link points to `/storage/emulated/0/`.

Set the DJI app as the home app:

```sh
cmd package set-home-activity dji.go.v5/com.dji.component.application.activity.DJIPureLaunchActivity
```

Enable Launcher3:

```sh
pm enable com.android.launcher3
```

Run Launcher3 once:

```sh
am start -a android.intent.action.MAIN -c android.intent.category.HOME
```

Set Launcher3 as home:

```sh
cmd package set-home-activity com.android.launcher3/.uioverrides.QuickstepLauncher
```

If disabling the DJI app does not take effect, enabling it resets Launcher3 as home:

```sh
pm disable-user --user 0 dji.go.v5/com.dji.component.application.activity.DJIPureLaunchActivity
pm enable dji.go.v5/com.dji.component.application.activity.DJIPureLaunchActivity
```

## What Works

- Root access
- Installing `.apk` files
- Escaping to Launcher3 via the start command
- Changing settings via command line
- Exploring system options with ActivityLauncher

## Future Ideas

Feel free to contribute ideas or improvements.

- Persistent Launcher3 access
- A reliable way to exit `dji_fly`
- Making the settings app show everything
- Understanding more of the SecNeo-protected `dji_fly` app, which only decodes its DEX files in RAM

## Tested RC2 Firmware Versions

- `v02.00.0300`

## Credits

- u/mitreffahcs Reddit post that figured out the required handshake: https://www.reddit.com/r/dji/s/tfF9CRFEHE

## Disclaimer

For educational purposes only. This material is provided "as is" without warranties of any kind, express or implied. To the fullest extent permitted by law, the author and contributors disclaim all liability for any loss, damage, injury, or claim arising from use of this material. Use at your own risk.
