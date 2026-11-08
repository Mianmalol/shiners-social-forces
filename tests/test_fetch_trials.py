"""Offline checks for the all-trial front end; real ZIP/CRC extraction in memory."""
import copy
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location('fetch_trials', Path(__file__).resolve().parents[1]/'scripts'/'fetch_trials.py')
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


class MemoryTransport:
    def __init__(self, parts):
        self.parts = parts
        self.calls = []
    def range(self, name, start, end, total):
        assert len(self.parts[name]) == total
        self.calls.append((name,start,end))
        return self.parts[name][start:end+1]


def fixture():
    archives=[]; parts={}
    for kind,name in [('tracks','shiners-tracks.zip'),('networks','shiners-networks.zip'),('videos','shiners-videos.zip')]:
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_STORED) as z:
            if kind in fetch.KINDS:
                for trial in fetch.TRIALS:
                    z.writestr(fetch.PREFIXES[kind]+trial+'.parquet',f'{kind} {trial}\n'.encode()*5)
            else:
                z.writestr('unselected-video.mp4',b'no video should be fetched')
        blob=buffer.getvalue();mid=len(blob)//2
        p1=name+'.part001';p2=name+'.part002';parts[p1]=blob[:mid];parts[p2]=blob[mid:]
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            members=[{'path':i.filename,'size':i.file_size,'compressed_size':i.compress_size,'crc32':f'{i.CRC:08x}'} for i in z.infolist()]
        archives.append({'name':name,'size':len(blob),'sha256':'a'*64,
                         'parts':[{'name':p1,'size':mid},{'name':p2,'size':len(blob)-mid}],
                         'members':members})
    manifest={'schema_version':1,'repository':fetch.helpers.REPOSITORY,'tag':fetch.helpers.TAG,'archives':archives}
    source={'files':[{'name':a['name'],'size':a['size'],'sha256':a['sha256']} for a in archives]}
    return manifest,source,MemoryTransport(parts)


class FetchTrialsTests(unittest.TestCase):
    def test_aliases_and_stable_deduplication(self):
        self.assertEqual(fetch.selected_trials(['0066','10-fish/0066','151-fish']),
                         ['10-fish__0066','150-fish__150-fish'])
        self.assertEqual(fetch.canonical_trial('150-fish/150-fish'),'150-fish__150-fish')
        self.assertEqual(fetch.canonical_trial('151-fish__151-fish'),'150-fish__150-fish')
        self.assertEqual(len(fetch.selected_trials(all_trials=True)),10)
        for bad in ['../../outside','151','10-fish/9999']:
            with self.assertRaises(ValueError):fetch.canonical_trial(bad)
        with self.assertRaises(ValueError):fetch.selected_trials()
        with self.assertRaises(ValueError):fetch.selected_trials(['0066'],True)

    def test_kinds_never_select_videos(self):
        self.assertEqual(fetch.selected_kinds('both'),['tracks','networks'])
        self.assertEqual(fetch.selected_kinds('tracks'),['tracks'])
        with self.assertRaises(ValueError):fetch.selected_kinds('videos')

    def test_validates_all_ten_and_selected_source_integrity(self):
        manifest,source,_=fixture()
        out=fetch.validate_manifest(manifest,source,fetch.TRIALS,['tracks','networks'])
        self.assertEqual(set(out),{'shiners-tracks.zip','shiners-networks.zip','shiners-videos.zip'})
        bad=copy.deepcopy(manifest);bad['archives'][0]['sha256']='b'*64
        with self.assertRaisesRegex(ValueError,'source manifest'):
            fetch.validate_manifest(bad,source,fetch.TRIALS,['tracks'])
        bad=copy.deepcopy(manifest);bad['archives'][0]['parts'].reverse()
        with self.assertRaisesRegex(ValueError,'parts'):
            fetch.validate_manifest(bad,source,fetch.TRIALS,['tracks'])
        bad=copy.deepcopy(manifest);bad['archives'][0]['members'].pop()
        with self.assertRaisesRegex(ValueError,'missing or duplicated'):
            fetch.validate_manifest(bad,source,fetch.TRIALS,['tracks'])

    def test_gigabyte_members_are_accepted(self):
        manifest,source,_=fixture()
        a=manifest['archives'][0];a['size']=1_900_000_000
        a['parts']=[{'name':a['name'],'size':a['size']}]
        a['members'][0].update(size=1_139_235_904,compressed_size=1_139_235_904)
        source['files'][0]['size']=a['size']
        fetch.validate_manifest(manifest,source,[fetch.TRIALS[0]],['tracks'])
        a['members'][0]['size']=3*1024**3
        with self.assertRaisesRegex(ValueError,'size/CRC'):
            fetch.validate_manifest(manifest,source,[fetch.TRIALS[0]],['tracks'])

    def test_actual_extraction_provenance_and_verified_rerun(self):
        manifest,source,transport=fixture()
        trials=[fetch.TRIALS[0],fetch.TRIALS[-1]]
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
            output=Path(d).resolve()/'data'
            fetch.fetch_trials(manifest,source,trials,['tracks','networks'],output,transport,manifest_sha256='b'*64)
            self.assertEqual({p.name for p in output.iterdir()},set(trials))
            for trial in trials:
                files={p.name for p in (output/trial).iterdir()}
                self.assertEqual(files,{'tracks.parquet','networks.parquet','provenance.json','release-manifest.json'})
                provenance=json.loads((output/trial/'provenance.json').read_text())
                self.assertEqual(provenance['trial'],trial.replace('__','/'))
                self.assertTrue(provenance['files']['tracks.parquet']['zip_member_crc32_verified'])
                self.assertFalse(provenance['full_archive_sha256_verified'])
                self.assertEqual((output/trial/'tracks.parquet').read_bytes(),f'tracks {trial}\n'.encode()*5)
            self.assertTrue(all('videos' not in call[0] for call in transport.calls))
            before=len(transport.calls)
            fetch.fetch_trials(manifest,source,trials,['tracks','networks'],output,transport,manifest_sha256='b'*64)
            self.assertEqual(len(transport.calls),before)
            (output/trials[0]/'tracks.parquet').write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError,'verified provenance'):
                fetch.fetch_trials(manifest,source,trials,['tracks'],output,transport)

    def test_wrong_trial_provenance_and_symlink_ancestor_rejected(self):
        manifest,source,transport=fixture();trial=fetch.TRIALS[0]
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
            output=Path(d).resolve()/'data';directory=output/trial;directory.mkdir(parents=True)
            (directory/'provenance.json').write_text(json.dumps({'repository':fetch.helpers.REPOSITORY,'release_tag':fetch.helpers.TAG,'trial':'wrong'}))
            with self.assertRaisesRegex(ValueError,'different release/trial'):
                fetch.fetch_trials(manifest,source,[trial],['tracks'],output,transport)
            alias=Path(d).resolve()/'alias';alias.symlink_to(output,target_is_directory=True)
            with self.assertRaisesRegex(ValueError,'symlink'):
                fetch.safe_output_directory(alias/'nested')


if __name__=='__main__':unittest.main()
