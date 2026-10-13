import unittest
from unittest.mock import patch, MagicMock
import os
import core.extractor as extractor
import core.video_processor as video_processor

class TestKickSupport(unittest.TestCase):

    def test_get_video_id_kick_vod(self):
        url = "https://kick.com/gabepeixe/videos/01a12bc9-9a78-7443-b6df-0f453895b31a"
        vid = extractor.get_video_id(url)
        self.assertEqual(vid, "kick_01a12bc9-9a78-7443-b6df-0f453895b31a")

    def test_get_video_id_kick_existing_id(self):
        vid = extractor.get_video_id("kick_01a12bc9-9a78-7443-b6df-0f453895b31a")
        self.assertEqual(vid, "kick_01a12bc9-9a78-7443-b6df-0f453895b31a")

    def test_get_video_id_kick_channel(self):
        url = "https://kick.com/gabepeixe"
        vid = extractor.get_video_id(url)
        self.assertTrue(vid.startswith("kick_"))

    @patch('core.extractor.requests.get')
    def test_extract_kick_metadata_mocked(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = r'''
        <!DOCTYPE html><html><body>
        <script>
        self.__next_f.push([1,"...{\"category\":{\"id\":15,\"name\":\"Just Chatting\"},\"channel\":{\"username\":\"gabepeixe\"},\"duration\":3600,\"id\":\"01a12bc9-9a78-7443-b6df-0f453895b31a\",\"is_live\":false,\"recording_url\":\"https://stream.kick.com/test/master.m3u8\",\"start_time\":\"2026-10-11T16:00:00Z\",\"thumbnail\":{\"src\":\"https://web.kick.com/thumb.jpg\"},\"title\":\"Live do Peixao\"}..."]);
        </script>
        </body></html>
        '''
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        meta = extractor.extract_kick_metadata("https://kick.com/gabepeixe/videos/01a12bc9-9a78-7443-b6df-0f453895b31a")
        self.assertIsNone(meta.get("error"))
        self.assertEqual(meta.get("title"), "Live do Peixao")
        self.assertEqual(meta.get("channel"), "gabepeixe")
        self.assertEqual(meta.get("duration"), 3600)
        self.assertEqual(meta.get("recording_url"), "https://stream.kick.com/test/master.m3u8")
        self.assertEqual(meta.get("thumbnail"), "https://web.kick.com/thumb.jpg")
        self.assertFalse(meta.get("is_live"))

    @patch('core.extractor.extract_kick_metadata')
    def test_get_video_metadata_routes_kick(self, mock_extract):
        mock_extract.return_value = {
            "title": "Live do Peixao",
            "duration": 3600,
            "recording_url": "https://stream.kick.com/test/master.m3u8",
            "error": None
        }
        res = extractor.get_video_metadata("https://kick.com/gabepeixe/videos/01a12bc9-9a78-7443-b6df-0f453895b31a")
        self.assertEqual(res["title"], "Live do Peixao")
        mock_extract.assert_called_once()

    @patch('core.video_processor.os.remove')
    @patch('core.video_processor.subprocess.run')
    @patch('core.video_processor.os.path.exists')
    @patch('core.video_processor.os.path.getsize')
    @patch('core.extractor.extract_kick_metadata')
    def test_download_full_video_kick_slice(self, mock_extract, mock_getsize, mock_exists, mock_subproc, mock_rm):
        mock_extract.return_value = {
            "recording_url": "https://stream.kick.com/test/master.m3u8",
            "error": None
        }
        mock_exists.return_value = True
        mock_getsize.return_value = 50000000
        mock_subproc.return_value = MagicMock(returncode=0)

        res = video_processor.download_full_video(
            url="https://kick.com/gabepeixe/videos/01a12bc9-9a78-7443-b6df-0f453895b31a",
            output_path="test_kick.mp4",
            start_sec=60,
            end_sec=120
        )
        self.assertIsNotNone(res.get("path"))
        self.assertIsNone(res.get("error"))
        # Verify ffmpeg arguments had -ss and -t
        call_args = mock_subproc.call_args[0][0]
        self.assertIn("-ss", call_args)
        self.assertIn("60.0", call_args)
        self.assertIn("-t", call_args)
        self.assertIn("60.0", call_args)
        self.assertIn("-c", call_args)
        self.assertIn("copy", call_args)

    @patch('core.extractor.os.remove', create=True)
    @patch('core.extractor.subprocess.run', create=True)
    @patch('core.extractor.os.path.exists')
    @patch('core.extractor.os.path.getsize')
    @patch('core.extractor.extract_kick_metadata')
    def test_download_audio_kick_slice(self, mock_extract, mock_getsize, mock_exists, mock_subproc, mock_rm):
        mock_extract.return_value = {
            "recording_url": "https://stream.kick.com/test/master.m3u8",
            "error": None
        }
        mock_exists.return_value = True
        mock_getsize.return_value = 2000000
        mock_subproc.return_value = MagicMock(returncode=0)

        res = extractor.download_audio(
            url="https://kick.com/gabepeixe/videos/01a12bc9-9a78-7443-b6df-0f453895b31a",
            output_path="test_kick.mp3",
            start_sec=120,
            end_sec=180
        )
        self.assertIsNotNone(res.get("path"))
        self.assertIsNone(res.get("error"))
        call_args = mock_subproc.call_args[0][0]
        self.assertIn("-ss", call_args)
        self.assertIn("-vn", call_args)
        self.assertIn("libmp3lame", call_args)

    @patch('core.video_processor.os.remove')
    @patch('core.video_processor.subprocess.run')
    @patch('core.video_processor.os.path.exists')
    @patch('core.video_processor.os.path.getsize')
    @patch('core.extractor.extract_kick_metadata')
    def test_download_full_video_kick_live_flag(self, mock_extract, mock_getsize, mock_exists, mock_subproc, mock_rm):
        """Verifica se download_full_video com is_live=True roteia para download_kick_video sem chamar yt-dlp"""
        mock_extract.return_value = {
            "recording_url": "https://stream.kick.com/test/master.m3u8",
            "error": None
        }
        mock_exists.return_value = True
        mock_getsize.return_value = 50000000
        mock_subproc.return_value = MagicMock(returncode=0)

        res = video_processor.download_full_video(
            url="https://kick.com/gabepeixe/videos/01a12bc9-9a78-7443-b6df-0f453895b31a",
            output_path="test_kick_live.mp4",
            is_live=True,
            start_sec=100,
            end_sec=200
        )
        self.assertIsNotNone(res.get("path"))
        self.assertIsNone(res.get("error"))
        call_args = mock_subproc.call_args[0][0]
        self.assertIn("-ss", call_args)
        self.assertIn("100.0", call_args)
        self.assertIn("-t", call_args)
        self.assertIn("100.0", call_args)

    @patch('core.video_processor.os.remove')
    @patch('core.video_processor.subprocess.run')
    @patch('core.video_processor.os.path.exists')
    @patch('core.video_processor.os.path.getsize')
    @patch('core.extractor.extract_kick_metadata')
    @patch('core.extractor.get_kick_playlist_total_duration')
    def test_download_full_video_kick_recent_minutes(self, mock_dur, mock_extract, mock_getsize, mock_exists, mock_subproc, mock_rm):
        """Verifica se captura de últimos minutos da live calcula -ss e -t corretamente baseado na duração total"""
        mock_extract.return_value = {
            "recording_url": "https://stream.kick.com/test/master.m3u8",
            "error": None
        }
        mock_exists.return_value = True
        mock_getsize.return_value = 50000000
        mock_subproc.return_value = MagicMock(returncode=0)
        # 3600 segundos de live total
        mock_dur.return_value = 3600.0

        # Últimos 15 minutos = 900s -> start = 3600 - 900 = 2700s, dur = 900s
        res = video_processor.download_full_video(
            url="https://kick.com/gabepeixe/videos/01a12bc9-9a78-7443-b6df-0f453895b31a",
            output_path="test_kick_15m.mp4",
            is_live=True,
            recent_minutes=15.0
        )
        self.assertIsNotNone(res.get("path"))
        call_args = mock_subproc.call_args[0][0]
        self.assertIn("-ss", call_args)
        self.assertIn("2700.0", call_args)
        self.assertIn("-t", call_args)
        self.assertIn("900.0", call_args)

    @patch('urllib.request.urlopen')
    def test_get_kick_playlist_total_duration(self, mock_urlopen):
        """Verifica a extração da duração total de playlist HLS da Kick"""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"#EXTM3U\n#EXT-X-TWITCH-TOTAL-SECS:4319.650\n#EXTINF:10.0,\n0.ts\n"
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        dur = extractor.get_kick_playlist_total_duration("https://stream.kick.com/test/variant.m3u8")
        self.assertAlmostEqual(dur, 4319.650, places=2)

if __name__ == '__main__':
    unittest.main()

