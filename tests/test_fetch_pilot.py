"""Offline checks for bounded split-ZIP fetching. Run with unittest discover."""
import importlib.util
import copy
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SPEC = importlib.util.spec_from_file_location('fetch_pilot', Path(__file__).resolve().parents[1]/'scripts'/'fetch_pilot.py')
fetch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch)


class MemoryTransport:
    def __init__(self, parts): self.parts = parts; self.calls = []
    def range(self, name, start, end, total):
        data = self.parts[name]
        if len(data) != total: raise ValueError('Wrong part size')
        self.calls.append((name, start, end))
        return data[start:end+1]


def fixture(compression=zipfile.ZIP_STORED):
    data = io.BytesIO()
    payload = b'fish trajectory data\n' * 100
    with zipfile.ZipFile(data, 'w', compression=compression) as z:
        z.writestr('test.parquet', payload)
        z.writestr('unselected.bin', b'do not extract this')
    blob = data.getvalue()
    # Split through payload and central-directory/end records.
    cuts = [0, 39, len(blob)-30, len(blob)-12, len(blob)]
    parts = {f'p{i}': blob[a:b] for i,(a,b) in enumerate(zip(cuts,cuts[1:]))}
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        infos = z.infolist()
    archive = {'name':'test.zip', 'size':len(blob), 'sha256':'0'*64,
               'parts':[{'name':k,'size':len(v)} for k,v in parts.items()],
               'members':[{'path':i.filename,'size':i.file_size,'compressed_size':i.compress_size,'crc32':f'{i.CRC:08x}'} for i in infos]}
    return archive, MemoryTransport(parts), payload


class RangeTests(unittest.TestCase):
    def test_exact_final_range_required(self):
        headers = 'HTTP/1.1 302 Found\r\nLocation: example\r\n\r\nHTTP/2 206\r\nContent-Range: bytes 3-5/12\r\n\r\n'
        fetch.check_range_response(206, headers, b'abc', 3, 5, 12)
        for status, body, end, total in [(200,b'abc',5,12),(206,b'ab',5,12),(206,b'abc',6,12),(206,b'abc',5,13)]:
            with self.assertRaises(ValueError):
                fetch.check_range_response(status, headers, body, 3, end, total)

    def test_remote_seek_across_parts(self):
        archive, transport, _ = fixture()
        reader = fetch.RemoteArchive(archive, transport)
        joined = b''.join(transport.parts.values())
        reader.seek(31)
        self.assertEqual(reader.read(50), joined[31:81])
        reader.seek(-22, 2)
        self.assertEqual(reader.read(), joined[-22:])
        reader.seek(len(joined)+3)
        self.assertEqual(reader.read(1), b'')
        with self.assertRaises(ValueError): reader.seek(-1)

    def test_stored_and_deflated_split_zip(self):
        for compression in [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED]:
            with self.subTest(compression=compression), tempfile.TemporaryDirectory() as d:
                archive, transport, payload = fixture(compression)
                output = Path(d)/'tracks.parquet'
                result = fetch.fetch_member(archive, 'test.parquet', output, transport)
                self.assertEqual(output.read_bytes(), payload)
                self.assertTrue(result['zip_member_crc32_verified'])
                self.assertFalse(result['full_archive_sha256_verified'])
                self.assertEqual(set(p.name for p in Path(d).iterdir()), {'tracks.parquet'})
                count = len(transport.calls)
                self.assertEqual(fetch.fetch_member(archive,'test.parquet',output,transport,result), result)
                self.assertEqual(count, len(transport.calls), 'Verified rerun should not fetch ranges')
                output.write_bytes(b'corrupted')
                with self.assertRaisesRegex(ValueError,'verified provenance'):
                    fetch.fetch_member(archive,'test.parquet',output,transport,result)

    def test_crc_corruption_does_not_publish(self):
        archive, transport, _ = fixture()
        # Corrupt stored payload while retaining original central-directory CRC.
        name = list(transport.parts)[1]
        part = bytearray(transport.parts[name]); part[20] ^= 1
        transport.parts[name] = bytes(part)
        with tempfile.TemporaryDirectory() as d:
            output=Path(d)/'tracks.parquet'
            with self.assertRaises(zipfile.BadZipFile):
                fetch.fetch_member(archive,'test.parquet',output,transport)
            self.assertFalse(output.exists())
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_manifest_member_mismatch_and_symlink(self):
        archive, transport, _ = fixture()
        with tempfile.TemporaryDirectory() as d:
            output=Path(d)/'tracks.parquet'
            archive['members'][0]['size'] += 1
            with self.assertRaisesRegex(ValueError,'disagree'):
                fetch.fetch_member(archive,'test.parquet',output,transport)
            target=Path(d)/'outside'; target.write_text('preserve')
            output.symlink_to(target)
            with self.assertRaisesRegex(ValueError,'symlink'):
                fetch.fetch_member(archive,'test.parquet',output,transport,force=True)
            self.assertEqual(target.read_text(),'preserve')

    def test_budget_fails_before_http(self):
        transport=fetch.CurlTransport(2)
        with patch.object(fetch.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'budget'):
                transport.range('part',0,2,100)
            run.assert_not_called()

    def test_manifest_archive_and_part_mismatches(self):
        archives = []
        for name, (member, _) in fetch.MEMBERS.items():
            archives.append({'name':name, 'size':10, 'sha256':'a'*64,
                             'parts':[{'name':name, 'size':10}],
                             'members':[{'path':member, 'size':3, 'compressed_size':3, 'crc32':'00000000'}]})
        manifest={'schema_version':1, 'repository':fetch.REPOSITORY,
                  'tag':fetch.TAG, 'archives':archives}
        source={'files':[{'name':a['name'],'size':a['size'],'sha256':a['sha256']} for a in archives]}
        self.assertEqual(set(fetch.validate_manifest(manifest,source)),set(fetch.MEMBERS))
        bad=copy.deepcopy(manifest); bad['archives'][0]['sha256']='b'*64
        with self.assertRaisesRegex(ValueError,'source manifest'):
            fetch.validate_manifest(bad,source)
        bad=copy.deepcopy(manifest); bad['archives'][0]['parts'][0]['size']=9
        with self.assertRaisesRegex(ValueError,'Part sizes'):
            fetch.validate_manifest(bad,source)
        bad=copy.deepcopy(manifest); bad['archives'][0]['parts'][0]['name']='../evil'
        with self.assertRaisesRegex(ValueError,'part names'):
            fetch.validate_manifest(bad,source)
        bad=copy.deepcopy(manifest); bad['archives'][0]['members']*=2
        with self.assertRaisesRegex(ValueError,'duplicated'):
            fetch.validate_manifest(bad,source)

    def test_release_identity_rejected(self):
        with self.assertRaisesRegex(ValueError,'identity'):
            fetch.validate_manifest({'schema_version':1,'repository':'wrong','tag':fetch.TAG}, {})


if __name__ == '__main__':
    unittest.main()
