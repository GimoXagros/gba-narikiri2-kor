"""No ROM/core assets: exact v10 framebuffer transform and malformed input checks."""
import json,struct,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import vbam_sgm_v10 as s


def sample(start=0):
    data=bytearray(s.NATIVE_SIZE);struct.pack_into('<I',data,0,10)
    for i in range(240*160):struct.pack_into('<H',data,s.PIXEL_START+2*i,(start+i)&0xFFFF)
    data[-s.RTC:]=bytes(range(s.RTC))
    return bytes(data)


class SgmV10Tests(unittest.TestCase):
    def test_pair_staging_and_publication_failure_leave_no_orphan(self):
        for failing_name in ('atomic_write_new','_publish_new'):
            with self.subTest(stage=failing_name),tempfile.TemporaryDirectory() as directory:
                p=Path(directory);out=p/'out.sgm';meta=p/'out.sgm.json'
                original=getattr(s,failing_name);calls=0
                def fail_second(*args):
                    nonlocal calls
                    calls+=1
                    if calls==2:raise OSError('injected second write failure')
                    return original(*args)
                with patch.object(s,failing_name,side_effect=fail_second):
                    with self.assertRaises(OSError):s.publish_pair(out,b'sgm',meta,b'json')
                self.assertEqual(list(p.iterdir()),[])
                s.publish_pair(out,b'sgm',meta,b'json')
                self.assertEqual(out.read_bytes(),b'sgm');self.assertEqual(meta.read_bytes(),b'json')

    def test_pair_collision_preserves_other_writer_and_rolls_back_owned_file(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory);out=p/'out.sgm';meta=p/'out.sgm.json'
            original=s._publish_new;calls=0
            def collide(staged,destination):
                nonlocal calls
                calls+=1
                if calls==2:destination.write_bytes(b'other writer')
                return original(staged,destination)
            with patch.object(s,'_publish_new',side_effect=collide):
                with self.assertRaises(FileExistsError):s.publish_pair(out,b'sgm',meta,b'json')
            self.assertFalse(out.exists());self.assertEqual(meta.read_bytes(),b'other writer')

    def test_all_rgb565_values_inverse_and_cpu_device_bytes(self):
        for start in (0,32768):
            native=sample(start);desktop=s.to_desktop(native)
            self.assertEqual(s.to_native(desktop),native)
            self.assertEqual(desktop[:s.PIXEL_START],native[:s.PIXEL_START])
            self.assertEqual(desktop[-s.RTC:],native[-s.RTC:])

    def test_truncation_version_and_unused_native_pixels_are_rejected(self):
        native=sample()
        for size in (0,3,24,s.PIXEL_START,s.NATIVE_SIZE-1):
            with self.assertRaises(ValueError):s.to_desktop(native[:size])
        for at,value in ((0,11),(s.PIXEL_START+240*160*2,1)):
            data=bytearray(native);data[at]=value
            with self.assertRaises(ValueError):s.to_desktop(data)

    def test_cheats_padding_and_noncanonical_pixels_cannot_disappear(self):
        desktop=s.to_desktop(sample())
        for at in (-s.RTC-s.CHEATS,s.PIXEL_START,s.PIXEL_START+241*4-1,
                   s.PIXEL_START+241*4+3,s.PIXEL_START+241*4+240*4):
            data=bytearray(desktop);data[at]=1
            with self.assertRaises(ValueError):s.to_native(data)
        data=bytearray(desktop);struct.pack_into('<I',data,s.PIXEL_START+241*4,0x010101)
        with self.assertRaises(ValueError):s.to_native(data)

    def test_existing_destination_and_wrong_metadata_preserve_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory);source=p/'state';rom=p/'rom';out=p/'out.sgm'
            source.write_bytes(sample());rom.write_bytes(b'local source')
            source.with_suffix('.json').write_text(json.dumps(dict(state_sha256='wrong')))
            before=source.read_bytes()
            with self.assertRaises(ValueError):s.convert(source,out,rom)
            self.assertFalse(out.exists());self.assertEqual(source.read_bytes(),before)
            out.write_bytes(b'existing')
            with self.assertRaises(FileExistsError):s.convert(source,out,rom)
            self.assertEqual(out.read_bytes(),b'existing')


if __name__=='__main__':unittest.main()
