"""Lossless CSV and explicit keyboard-code preservation."""
import csv,io,os,sys,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import export_strict_dialogue_data as exporter
from export_strict_dialogue_data import csv_bytes,keyboard_display,publish_export


class ExportTests(unittest.TestCase):
    def test_machine_csv_keeps_formula_like_text_quotes_and_multiline(self):
        rows=[dict(id='00001234',japanese='「文,字」\n"次"',korean='=1+1\n한글',count=3)]
        actual=list(csv.DictReader(io.StringIO(csv_bytes(rows).decode('utf-8'),newline='')))
        self.assertEqual(actual,[{k:str(v) for k,v in rows[0].items()}])

    def test_keyboard_retains_mode_and_private_name_tokens(self):
        raw=b'%h\xCE\xCF '+bytes((127,1,1))+b'\n'
        self.assertEqual(keyboard_display(raw,['가']),'%h⟦FONT:CE⟧⟦FONT:CF⟧ 가\n')

    def test_failed_staging_and_publication_are_retryable(self):
        files=(('one.csv',b'first'),('two.json',b'second'))
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)/'export'
            original=exporter.atomic_write_new
            def fail_stage(path,data):
                if path.name=='two.json':raise OSError('injected staging failure')
                return original(path,data)
            with patch.object(exporter,'atomic_write_new',side_effect=fail_stage):
                with self.assertRaises(OSError):publish_export(out,files)
            self.assertFalse(out.exists())
            operation='rename' if os.name=='nt' else 'link'
            original_publish=getattr(os,operation)
            def fail_publish(source,destination):
                if destination.parent==out and destination.name=='two.json':raise OSError('injected publication failure')
                return original_publish(source,destination)
            with patch.object(exporter.os,operation,side_effect=fail_publish):
                with self.assertRaises(OSError):publish_export(out,files)
            self.assertFalse(out.exists())
            publish_export(out,files)
            self.assertEqual({p.name:p.read_bytes() for p in out.iterdir()},dict(files))

    def test_failure_keeps_competing_output_and_existing_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)/'export'
            operation='rename' if os.name=='nt' else 'link'
            original_publish=getattr(os,operation)
            def race(source,destination):
                if destination.parent==out and destination.name=='two.json':
                    destination.write_bytes(b'foreign')
                    raise FileExistsError('competing writer')
                return original_publish(source,destination)
            with patch.object(exporter.os,operation,side_effect=race):
                with self.assertRaises(FileExistsError):
                    publish_export(out,(('one.csv',b'first'),('two.json',b'second')))
            self.assertEqual({p.name:p.read_bytes() for p in out.iterdir()},{'two.json':b'foreign'})
            with self.assertRaises(FileExistsError):publish_export(out,(('new.csv',b'new'),))


if __name__=='__main__':unittest.main()
