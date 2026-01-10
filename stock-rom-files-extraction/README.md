# Extracting stuff from the sock ROM of Fariphone 5

# Prerequistes
Some linux distro, to build the sparse image extraction tool (on Windows try maybe mingw32-make from mingw compiler set, or msys2?).

Tools:
```
git g++ make 7z 
```

Android sparse image extraction tool:
https://github.com/anestisb/android-simg2img

# Instructions

1. Clone the Android sparse image extraction tool, and build it:
```bash
git clone https://github.com/anestisb/android-simg2img
cd android-simg2img && git checkout a6fcc0f1c61b2aa5b55516829cd7d13dbfbacb91
make
```

2. Download the .zip of the ROM image from the Manufactureer site: https://support.fairphone.com/hc/en-us/articles/18896094650513-How-to-manually-install-Android-on-your-Fairphone  
Scroll down for chapter `Step 2: Find and download your package` over there.

3. Unzip it. For Fairphone 5 it will be something like this:
```bash
unzip FP5-*-factory.zip
```

4. Navigate to the unzipped images folder of the archive:
```bash
cd FP5-*-factory/images
```

5. Use sigm2igm from point _1._ to unpack the `super.img`
```bash
android-simg2img/simg2img super.img super.unsparsed.img
```

6. Un-7z the `super.unsparsed.img` into `super_unpacked` directory
```bash
mkdir super_unpacked
cd super_unpacked
7z x ../super.unsparsed.img
```
This will create following files:
```
odm_a.img  odm_b  product_a.img  product_b system_a.img  system_b  system_ext_a.img  system_ext_b  vendor_a.img  vendor_b
```
Those are the target partitions of the ROM file.

7. You can keep un-7zipping them, to get files from the respective paritions. Here for vendor:
```bash
(mkdir vendor_a_unpacked && cd vendor_a_unpacked && 7z x ../vendor_a.img)
```
Example content of vendor:
```bash
[vendor_a_unpacked]$ ls
app  bin  bt_firmware  build.prop  default.prop  dsp  etc  firmware  firmware_mnt  gpu  lib  lib64  lost+found  odm  overlay  rfs  vm-system
```