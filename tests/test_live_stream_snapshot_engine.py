import os
import unittest
from unittest.mock import patch, MagicMock
from core.video_processor import parse_m3u8_segments, build_finite_m3u8, download_live_video_snapshot
from core.extractor import download_live_audio_snapshot


SAMPLE_M3U8_TEXT = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:5
#EXT-X-MEDIA-SEQUENCE:100
#EXT-X-PROGRAM-DATE-TIME:2026-09-16T00:00:00.000+00:00
#EXTINF:5.0,
https://example.com/live/seg_100.ts
#EXTINF:5.0,
https://example.com/live/seg_101.ts
#EXTINF:5.0,
https://example.com/live/seg_102.ts
#EXTINF:5.0,
https://example.com/live/seg_103.ts
#EXTINF:5.0,
https://example.com/live/seg_104.ts
#EXTINF:5.0,
https://example.com/live/seg_105.ts
"""


class TestLiveStreamSnapshotEngine(unittest.TestCase):

    def test_parse_m3u8_segments(self):
        seq, dur, pairs = parse_m3u8_segments(SAMPLE_M3U8_TEXT)
        self.assertEqual(seq, 100)
        self.assertEqual(dur, 5.0)
        self.assertEqual(len(pairs), 6)
        self.assertEqual(pairs[0][0], "#EXTINF:5.0,")
        self.assertEqual(pairs[0][1], "https://example.com/live/seg_100.ts")
        self.assertEqual(pairs[-1][1], "https://example.com/live/seg_105.ts")

    def test_build_finite_m3u8_adds_endlist_and_vod_type(self):
        seq, dur, pairs = parse_m3u8_segments(SAMPLE_M3U8_TEXT)
        finite = build_finite_m3u8(seq, dur, pairs, 102, 106)
        lines = finite.strip().splitlines()

        self.assertIn("#EXT-X-PLAYLIST-TYPE:VOD", lines)
        self.assertIn("#EXT-X-MEDIA-SEQUENCE:102", lines)
        self.assertEqual(lines[-1], "#EXT-X-ENDLIST")
        self.assertIn("https://example.com/live/seg_102.ts", lines)
        self.assertIn("https://example.com/live/seg_105.ts", lines)
        self.assertNotIn("https://example.com/live/seg_100.ts", lines)

    def test_recent_minutes_segment_calculation(self):
        # 60 segments de 5 segundos = 300s (5 minutos)
        pairs = [(f"#EXTINF:5.0,", f"https://example.com/live/seg_{i}.ts") for i in range(200, 260)]
        seq = 200
        dur = 5.0

        # Pede os últimos 2 minutos (120s = 24 segmentos de 5s)
        recent_min = 2.0
        wanted_segs = int((recent_min * 60.0) / dur) # 24
        target_end = seq + len(pairs) # 260
        target_start = max(seq, target_end - wanted_segs) # 236

        finite = build_finite_m3u8(seq, dur, pairs, target_start, target_end)
        self.assertIn("#EXT-X-MEDIA-SEQUENCE:236", finite)
        self.assertIn("#EXT-X-ENDLIST", finite)
        self.assertIn("https://example.com/live/seg_236.ts", finite)
        self.assertIn("https://example.com/live/seg_259.ts", finite)
        self.assertNotIn("https://example.com/live/seg_235.ts", finite)

        # Pede os últimos 60 minutos (1 hora = 3600s = 720 segmentos de 5s)
        # Se a live tiver 1000 segmentos disponíveis (5000s)
        long_pairs = [(f"#EXTINF:5.0,", f"https://example.com/live/seg_{i}.ts") for i in range(1000, 2000)]
        long_seq = 1000
        wanted_1h_segs = int((60.0 * 60.0) / dur) # 720
        target_1h_end = long_seq + len(long_pairs) # 2000
        target_1h_start = max(long_seq, target_1h_end - wanted_1h_segs) # 1280

        finite_1h = build_finite_m3u8(long_seq, dur, long_pairs, target_1h_start, target_1h_end)
        self.assertIn("#EXT-X-MEDIA-SEQUENCE:1280", finite_1h)
        self.assertIn("#EXT-X-ENDLIST", finite_1h)
        self.assertIn("https://example.com/live/seg_1280.ts", finite_1h)
        self.assertIn("https://example.com/live/seg_1999.ts", finite_1h)
        self.assertNotIn("https://example.com/live/seg_1279.ts", finite_1h)

    @patch('yt_dlp.YoutubeDL')
    @patch('urllib.request.urlopen')
    @patch('subprocess.run')
    @patch('os.path.exists')
    @patch('os.path.getsize')
    def test_download_live_video_snapshot_fast_path(
        self, mock_getsize, mock_exists, mock_subproc, mock_urlopen, mock_ydl_cls
    ):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            'formats': [
                {
                    'format_id': '270',
                    'vcodec': 'avc1.640028',
                    'acodec': 'none',
                    'protocol': 'm3u8_native',
                    'height': 1080,
                    'url': 'https://example.com/video.m3u8'
                },
                {
                    'format_id': '234',
                    'vcodec': 'none',
                    'acodec': 'mp4a.40.2',
                    'protocol': 'm3u8_native',
                    'abr': 128,
                    'url': 'https://example.com/audio.m3u8'
                }
            ]
        }

        resp_v = MagicMock()
        resp_v.read.return_value = SAMPLE_M3U8_TEXT.encode('utf-8')
        resp_v.__enter__.return_value = resp_v

        resp_a = MagicMock()
        resp_a.read.return_value = SAMPLE_M3U8_TEXT.encode('utf-8')
        resp_a.__enter__.return_value = resp_a

        resp_seg = MagicMock()
        resp_seg.read.return_value = b'dummy_ts_data'
        resp_seg.__enter__.return_value = resp_seg

        def _fake_urlopen(req, *args, **kwargs):
            url_str = req.full_url if hasattr(req, 'full_url') else str(req)
            if 'seg_' in url_str:
                return resp_seg
            if 'audio' in url_str:
                return resp_a
            return resp_v

        mock_urlopen.side_effect = _fake_urlopen
        mock_subproc.return_value = MagicMock(returncode=0)
        mock_exists.return_value = True
        mock_getsize.return_value = 50000000

        res = download_live_video_snapshot(
            "https://youtu.be/live_test",
            output_path="test_out.mp4",
            recent_minutes=15.0
        )
        self.assertIsNotNone(res.get("path"))
        self.assertIsNone(res.get("error"))

    @patch('yt_dlp.YoutubeDL')
    @patch('urllib.request.urlopen')
    @patch('subprocess.run')
    @patch('os.path.exists')
    @patch('os.path.getsize')
    def test_download_live_audio_snapshot_fast_path(
        self, mock_getsize, mock_exists, mock_subproc, mock_urlopen, mock_ydl_cls
    ):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            'formats': [
                {
                    'format_id': '234',
                    'vcodec': 'none',
                    'acodec': 'mp4a.40.2',
                    'protocol': 'm3u8_native',
                    'abr': 128,
                    'url': 'https://example.com/audio.m3u8'
                }
            ]
        }

        resp_a = MagicMock()
        resp_a.read.return_value = SAMPLE_M3U8_TEXT.encode('utf-8')
        resp_a.__enter__.return_value = resp_a

        mock_urlopen.return_value = resp_a
        mock_subproc.return_value = MagicMock(returncode=0)
        mock_exists.return_value = True
        mock_getsize.return_value = 5000000

        res = download_live_audio_snapshot(
            "https://youtu.be/live_test",
            output_path="test_out.mp3",
            recent_minutes=15.0
        )
        self.assertIsNotNone(res.get("path"))
        self.assertIsNone(res.get("error"))

    @patch('yt_dlp.YoutubeDL')
    @patch('urllib.request.urlopen')
    @patch('os.path.exists')
    @patch('os.path.getsize')
    def test_dvr_strategy_triggered_for_30min(
        self, mock_getsize, mock_exists, mock_urlopen, mock_ydl_cls
    ):
        """
        Valida que recent_minutes=30.0 aciona a Estratégia B (DVR via live_from_start).
        O yt-dlp.download() deve ser chamado (DVR path) e urlopen NÃO deve ser chamado
        para segmentos HLS individuais.
        """
        import time as _time
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl

        fake_epoch = int(_time.time()) - 7200  # stream rodando há 2h
        mock_ydl.extract_info.return_value = {
            'timestamp': fake_epoch,
            'is_live': True,
            'live_status': 'is_live',
            'formats': [
                {
                    'format_id': '270',
                    'vcodec': 'avc1.640028',
                    'acodec': 'none',
                    'protocol': 'm3u8_native',
                    'height': 1080,
                    'url': 'https://example.com/video.m3u8'
                },
                {
                    'format_id': '234',
                    'vcodec': 'none',
                    'acodec': 'mp4a.40.2',
                    'protocol': 'm3u8_native',
                    'abr': 128,
                    'url': 'https://example.com/audio.m3u8'
                }
            ]
        }
        mock_exists.return_value = True
        mock_getsize.return_value = 200_000_000

        res = download_live_video_snapshot(
            "https://youtu.be/live_test",
            output_path="test_dvr_out.mp4",
            recent_minutes=30.0
        )

        # DVR usa yt-dlp.download() — deve ter sido chamado
        mock_ydl.download.assert_called_once()
        # HLS Snapshot usaria urlopen para segmentos — não deve ter sido chamado para .ts
        ts_calls = [c for c in mock_urlopen.call_args_list if 'seg_' in str(c)]
        self.assertEqual(len(ts_calls), 0, "DVR path nao deve chamar urlopen para segmentos HLS")
        self.assertIsNotNone(res.get("path"))

    @patch('yt_dlp.YoutubeDL')
    @patch('urllib.request.urlopen')
    @patch('os.path.exists')
    @patch('os.path.getsize')
    def test_dvr_strategy_triggered_for_full_buffer(
        self, mock_getsize, mock_exists, mock_urlopen, mock_ydl_cls
    ):
        """
        Valida que recent_minutes=None (Buffer Completo) aciona a Estratégia B (DVR).
        """
        import time as _time
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl

        fake_epoch = int(_time.time()) - 3600  # stream rodando há 1h
        mock_ydl.extract_info.return_value = {
            'timestamp': fake_epoch,
            'is_live': True,
            'live_status': 'is_live',
            'formats': [
                {'format_id': '270', 'vcodec': 'avc1', 'acodec': 'none',
                 'protocol': 'm3u8_native', 'height': 1080, 'url': 'https://example.com/v.m3u8'},
                {'format_id': '234', 'vcodec': 'none', 'acodec': 'mp4a',
                 'protocol': 'm3u8_native', 'abr': 128, 'url': 'https://example.com/a.m3u8'}
            ]
        }
        mock_exists.return_value = True
        mock_getsize.return_value = 800_000_000  # 800MB (1h de video)

        # recent_minutes=None, start_sec=None, end_sec=None → Buffer Completo → DVR
        res = download_live_video_snapshot(
            "https://youtu.be/live_test",
            output_path="test_full_buffer.mp4",
            recent_minutes=None
        )

        mock_ydl.download.assert_called_once()
        self.assertIsNotNone(res.get("path"))

    @patch('yt_dlp.YoutubeDL')
    @patch('urllib.request.urlopen')
    @patch('subprocess.run')
    @patch('os.path.exists')
    @patch('os.path.getsize')
    def test_direct_parallel_dvr_segment_engine_youtube_template(
        self, mock_getsize, mock_exists, mock_subproc, mock_urlopen, mock_ydl_cls
    ):
        """
        Valida que o Direct Parallel DVR Segment Engine detecta o template /sq/{number}/
        em transmissões ao vivo ativas e realiza o download paralelo dos segmentos
        mesmo para trechos antigos não mais presentes no manifesto HLS rolling window.
        """
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            'is_live': True,
            'live_status': 'is_live',
            'formats': [
                {
                    'format_id': '270',
                    'vcodec': 'avc1.640028',
                    'acodec': 'none',
                    'protocol': 'm3u8_native',
                    'height': 1080,
                    'url': 'https://manifest.googlevideo.com/v.m3u8'
                },
                {
                    'format_id': '234',
                    'vcodec': 'none',
                    'acodec': 'mp4a.40.2',
                    'protocol': 'm3u8_native',
                    'abr': 128,
                    'url': 'https://manifest.googlevideo.com/a.m3u8'
                }
            ]
        }

        yt_v_manifest = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:2
#EXT-X-MEDIA-SEQUENCE:1000
#EXTINF:2.0,
https://rr1---sn.googlevideo.com/videoplayback/sq/1000/dur/2.000/v.ts
#EXTINF:2.0,
https://rr1---sn.googlevideo.com/videoplayback/sq/1001/dur/2.000/v.ts
#EXTINF:2.0,
https://rr1---sn.googlevideo.com/videoplayback/sq/1002/dur/2.000/v.ts
"""
        yt_a_manifest = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:2
#EXT-X-MEDIA-SEQUENCE:1000
#EXTINF:2.0,
https://rr1---sn.googlevideo.com/videoplayback/sq/1000/dur/2.000/a.ts
#EXTINF:2.0,
https://rr1---sn.googlevideo.com/videoplayback/sq/1001/dur/2.000/a.ts
#EXTINF:2.0,
https://rr1---sn.googlevideo.com/videoplayback/sq/1002/dur/2.000/a.ts
"""
        resp_v = MagicMock()
        resp_v.read.return_value = yt_v_manifest.encode('utf-8')
        resp_v.__enter__.return_value = resp_v

        resp_a = MagicMock()
        resp_a.read.return_value = yt_a_manifest.encode('utf-8')
        resp_a.__enter__.return_value = resp_a

        resp_seg = MagicMock()
        resp_seg.status = 200
        resp_seg.read.return_value = b'dummy_ts_data'
        resp_seg.__enter__.return_value = resp_seg

        def _mock_open(req, *args, **kwargs):
            url_str = req.full_url if hasattr(req, 'full_url') else str(req)
            if '/v.m3u8' in url_str:
                return resp_v
            if '/a.m3u8' in url_str:
                return resp_a
            return resp_seg

        mock_urlopen.side_effect = _mock_open
        mock_subproc.return_value = MagicMock(returncode=0)
        mock_exists.return_value = True
        mock_getsize.return_value = 50_000_000

        res = download_live_video_snapshot(
            "https://youtu.be/live_test",
            output_path="test_direct_parallel.mp4",
            recent_minutes=0.1
        )

        self.assertIsNotNone(res.get("path"))
        self.assertIsNone(res.get("error"))
        mock_subproc.assert_called()


if __name__ == '__main__':
    unittest.main()
