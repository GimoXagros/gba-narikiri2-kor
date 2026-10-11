"""Exact-ROM VBA-M v10 native-state to desktop SGM format adapter.

Only the audited RGB565 libretro core and empty desktop cheat section are
supported. This changes container layout, not saved game execution state.
Desktop UI loading and cross-ROM compatibility are not asserted.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,os,struct,tempfile
from pathlib import Path
from v09c_io import atomic_write_new

CORE_SHA='bcb5fb8ab944caa5a1ed06213a2dc3747a2ac3741bc953d06afdae0915cb7f4d'
NATIVE_SIZE=723452
PREFIX=479
PIXEL_START=PREFIX+0x8000+0x400+0x40000+0x20000+0x400
NATIVE_PIXELS=4*240*160
DESKTOP_PIXELS=4*241*162
CHEATS=4+16384*84
RTC=48
DESKTOP_SIZE=NATIVE_SIZE+DESKTOP_PIXELS-NATIVE_PIXELS+CHEATS


def sha(data):return hashlib.sha256(data).hexdigest()


def _publish_new(staged, destination):
    if os.name == 'nt':
        os.rename(staged, destination)
    else:
        os.link(staged, destination)


def publish_pair(destination, compressed, sidecar, metadata):
    """Stage both files first; roll back only files still owned on failure.

    Two paths cannot form a filesystem crash-atomic transaction. An abrupt
    process/power loss may require manually moving an incomplete pair aside.
    Ordinary write/publication failures leave no owned orphan behind.
    """
    with tempfile.TemporaryDirectory(prefix='.sgm-', dir=destination.parent) as directory:
        staged_pairs=[]
        for number,(path,data) in enumerate(((destination,compressed),(sidecar,metadata))):
            staged=Path(directory)/str(number)
            atomic_write_new(staged,data)
            stat=staged.stat()
            staged_pairs.append((staged,path,data,(stat.st_dev,stat.st_ino)))
        published=[]
        try:
            for staged,path,data,identity in staged_pairs:
                _publish_new(staged,path)
                published.append((path,identity))
                if path.read_bytes()!=data:raise OSError('Published SGM pair read-back mismatch')
        except BaseException:
            for path,identity in reversed(published):
                if path.exists() and not path.is_symlink():
                    stat=path.stat()
                    if (stat.st_dev,stat.st_ino)==identity:path.unlink()
            raise


def require_header(data,size):
    if len(data)!=size or struct.unpack_from('<I',data)[0]!=10:
        raise ValueError('Expected exact supported v10 state extent and version')


def to_desktop(native):
    require_header(native,NATIVE_SIZE)
    pix=native[PIXEL_START:PIXEL_START+NATIVE_PIXELS]
    if any(pix[240*160*2:]):raise ValueError('Unsupported nonzero unused native framebuffer')
    out=bytearray(DESKTOP_PIXELS)
    for y in range(160):
        for x in range(240):
            v=struct.unpack_from('<H',pix,2*(y*240+x))[0]
            r,g,b=(v>>11)&31,(v>>5)&63,v&31
            rgb=((r*255//31)<<16)|((g*255//63)<<8)|(b*255//31)
            struct.pack_into('<I',out,4*((y+1)*241+x),rgb)
    tail=native[PIXEL_START+NATIVE_PIXELS:]
    desktop=native[:PIXEL_START]+out+tail[:-RTC]+bytes(CHEATS)+tail[-RTC:]
    require_header(desktop,DESKTOP_SIZE)
    return bytes(desktop)


def to_native(desktop):
    require_header(desktop,DESKTOP_SIZE)
    if any(desktop[-RTC-CHEATS:-RTC]):raise ValueError('Nonempty cheat sections are not supported')
    pix=desktop[PIXEL_START:PIXEL_START+DESKTOP_PIXELS]
    # The audited native format has no desktop border or alpha channel.
    if any(pix[:241*4]) or any(pix[161*241*4:]):raise ValueError('Nonzero desktop framebuffer border')
    for y in range(160):
        if any(pix[4*((y+1)*241+240):4*((y+2)*241)]):raise ValueError('Nonzero desktop framebuffer pitch padding')
    out=bytearray(NATIVE_PIXELS)
    for y in range(160):
        for x in range(240):
            rgb=struct.unpack_from('<I',pix,4*((y+1)*241+x))[0]
            if rgb>>24:raise ValueError('Desktop alpha is not supported')
            r,g,b=(rgb>>16)&255,(rgb>>8)&255,rgb&255
            v=(((r*31+127)//255)<<11)|(((g*63+127)//255)<<5)|((b*31+127)//255)
            struct.pack_into('<H',out,2*(y*240+x),v)
    tail=desktop[PIXEL_START+DESKTOP_PIXELS:-RTC-CHEATS]+desktop[-RTC:]
    native=desktop[:PIXEL_START]+out+tail
    require_header(native,NATIVE_SIZE)
    if to_desktop(native)!=desktop:raise ValueError('Noncanonical RGB565 desktop frame')
    return bytes(native)


def convert(source,destination,rom):
    source,destination,rom=map(Path,(source,destination,rom))
    sidecar=destination.with_suffix(destination.suffix+'.json')
    if destination.suffix.lower()!='.sgm':raise ValueError('Destination must be .sgm')
    if destination.exists() or destination.is_symlink() or sidecar.exists() or sidecar.is_symlink():
        raise FileExistsError('Existing output or sidecar is preserved')
    native=source.read_bytes();image=rom.read_bytes()
    metadata=json.loads(source.with_suffix(source.suffix+'.json').read_text(encoding='utf-8'))
    if (metadata.get('state_sha256')!=sha(native) or metadata.get('rom_sha256')!=sha(image)
        or metadata.get('core_sha256')!=CORE_SHA):raise ValueError('State, core or exact-ROM binding differs')
    if len(image)!=0x800000:raise ValueError('This delivery profile requires the exact 8 MiB ROM')
    if native[4:20]!=image[0xA0:0xB0]:raise ValueError('Native state cartridge identity differs')
    if not isinstance(metadata.get('frame'),int) or metadata['frame']<0:raise ValueError('Missing state frame provenance')
    desktop=to_desktop(native)
    if to_native(desktop)!=native:raise ValueError('Native inverse differs')
    compressed=gzip.compress(desktop,mtime=0)
    if to_native(gzip.decompress(compressed))!=native:raise ValueError('SGM inverse differs')
    report=dict(rom_sha256=sha(image),core_sha256=CORE_SHA,state_sha256=sha(native),frame=metadata['frame'],
        sgm_sha256=sha(compressed),sgm_raw_size=len(desktop),sgm_version=10,
        empty_cheats=True,cpu_memory_device_bytes_preserved=True,exact_inverse_roundtrip=True,
        desktop_ui_load_tested=False,cross_rom_supported=False,
        format_target='VBA-M 01ceb896 desktop v10-compatible reader')
    destination.parent.mkdir(parents=True,exist_ok=True)
    publish_pair(destination,compressed,sidecar,(json.dumps(report,indent=2)+'\n').encode('utf-8'))
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','destination','rom'):p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args();print(json.dumps(convert(**vars(args)),indent=2))


if __name__=='__main__':main()
