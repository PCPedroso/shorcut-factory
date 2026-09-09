import unittest
from unittest.mock import patch, MagicMock
from core.extractor import get_video_metadata
from core.library_manager import add_or_update_video_in_library, get_library


class TestLiveStreamHandler(unittest.TestCase):

    @patch('yt_dlp.YoutubeDL')
    def test_get_video_metadata_detects_live_stream(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            'title': 'Debate Eleitoral AO VIVO',
            'duration': None,
            'is_live': True,
            'live_status': 'is_live',
            'upload_date': '20260825',
            'thumbnail': 'https://example.com/thumb.jpg',
            'uploader': 'Band Jornalismo',
            'webpage_url': 'https://www.youtube.com/watch?v=live123'
        }

        meta = get_video_metadata('https://www.youtube.com/watch?v=live123')
        self.assertTrue(meta['is_live'])
        self.assertEqual(meta['live_status'], 'is_live')
        self.assertEqual(meta['title'], 'Debate Eleitoral AO VIVO')

    @patch('yt_dlp.YoutubeDL')
    def test_get_video_metadata_normal_video(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            'title': 'Entrevista Gravada',
            'duration': 1800,
            'is_live': False,
            'live_status': 'not_live',
            'upload_date': '20260824',
            'thumbnail': 'https://example.com/thumb2.jpg',
            'uploader': 'Canal Normal',
            'webpage_url': 'https://www.youtube.com/watch?v=normal123'
        }

        meta = get_video_metadata('https://www.youtube.com/watch?v=normal123')
        self.assertFalse(meta['is_live'])
        self.assertEqual(meta['duration'], 1800)

    def test_library_manager_records_is_live(self):
        entry = add_or_update_video_in_library(
            video_id='live_test_id',
            title='Live Test',
            upload_date_raw='20260825',
            url='https://www.youtube.com/watch?v=live_test_id',
            is_live=True
        )
        self.assertTrue(entry.get('is_live'))

    @patch('core.extractor.download_live_audio_snapshot')
    def test_download_audio_routes_to_live_snapshot(self, mock_snap):
        from core.extractor import download_audio
        mock_snap.return_value = {"path": "test.mp3", "error": None}
        with patch('os.path.exists', return_value=True):
            res = download_audio("https://youtu.be/live123", output_path="test.mp3", is_live=True)
            mock_snap.assert_called_once()
            self.assertEqual(res["path"], "test.mp3")

    @patch('core.video_processor.download_live_video_snapshot')
    def test_download_full_video_routes_to_live_snapshot(self, mock_snap):
        from core.video_processor import download_full_video
        mock_snap.return_value = {"path": "test.mp4", "error": None}
        with patch('os.path.exists', return_value=True):
            res = download_full_video("https://youtu.be/live123", output_path="test.mp4", is_live=True)
            mock_snap.assert_called_once()
            self.assertEqual(res["path"], "test.mp4")

    @patch('yt_dlp.YoutubeDL')
    @patch('urllib.request.urlopen')
    @patch('subprocess.run')
    def test_download_live_audio_snapshot_injects_endlist(self, mock_subproc, mock_urlopen, mock_ydl_cls):
        from core.extractor import download_live_audio_snapshot
        import os

        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            'formats': [{
                'format_id': '234',
                'vcodec': 'none',
                'protocol': 'm3u8_native',
                'url': 'https://manifest.example.com/playlist.m3u8'
            }]
        }

        # Mock urllib para retornar um m3u8 sem #EXT-X-ENDLIST
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"#EXTM3U\n#EXTINF:5.0,\nseg1.ts\n#EXTINF:5.0,\nseg2.ts"
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        # Mock subprocess
        mock_proc = MagicMock()
        mock_proc.return_value.returncode = 0
        mock_subproc.return_value = mock_proc

        out_path = "scratch/test_live_mock.mp3"
        with patch('os.path.exists', side_effect=lambda p: True if p == out_path else False), \
             patch('os.path.getsize', return_value=50000):
            res = download_live_audio_snapshot("https://youtu.be/live123", output_path=out_path)
            self.assertEqual(res["path"], out_path)
            mock_subproc.assert_called_once()
            # Verifica argumentos do FFmpeg
            call_args = mock_subproc.call_args[0][0]
            self.assertIn('-protocol_whitelist', call_args)
            self.assertIn('-vn', call_args)
            self.assertIn('libmp3lame', call_args)

    @patch('yt_dlp.YoutubeDL')
    @patch('subprocess.run')
    def test_download_live_video_snapshot_with_time_slice(self, mock_subproc, mock_ydl_cls):
        from core.video_processor import download_live_video_snapshot

        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            'formats': [{
                'format_id': '270',
                'height': 1080,
                'protocol': 'm3u8_native',
                'manifest_url': 'https://manifest.example.com/hls_variant.m3u8',
                'url': 'https://manifest.example.com/stream270.m3u8'
            }]
        }

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_subproc.return_value = mock_proc

        out_path = "scratch/test_live_video_mock.mp4"
        with patch('os.path.exists', side_effect=lambda p: True if p == out_path else False), \
             patch('os.path.getsize', return_value=500000):
            res = download_live_video_snapshot(
                "https://youtu.be/live123",
                output_path=out_path,
                start_sec=60.0,
                end_sec=90.0
            )
            self.assertEqual(res["path"], out_path)
            mock_subproc.assert_called_once()
            call_args = mock_subproc.call_args[0][0]
            self.assertIn('-ss', call_args)
            self.assertIn('60.0', call_args)
            self.assertIn('-t', call_args)
            self.assertIn('30.0', call_args)
            self.assertIn('copy', call_args)


if __name__ == '__main__':
    unittest.main()

