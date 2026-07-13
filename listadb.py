import usb1

VENDOR_ID = None  # fill in after first run if you know it, otherwise leave None to scan all

with usb1.USBContext() as ctx:
    for device in ctx.getDeviceList(skip_on_error=True):
        try:
            manufacturer = device.getManufacturer()
            product = device.getProduct()
        except Exception:
            manufacturer = product = "?"

        print(f"\nDevice: {device.getVendorID():04x}:{device.getProductID():04x}  "
              f"{manufacturer} / {product}")

        for cfg in device.iterConfigurations():
            for iface in cfg:
                for setting in iface:
                    print(f"  Interface {setting.getNumber()}, AltSetting {setting.getAlternateSetting()}: "
                          f"Class={setting.getClass():#04x} Sub={setting.getSubClass():#04x} "
                          f"Proto={setting.getProtocol():#04x}")
                    for ep in setting:
                        print(f"    Endpoint {ep.getAddress():#04x}  "
                              f"Attr={ep.getAttributes():#04x}  MaxPacket={ep.getMaxPacketSize()}")