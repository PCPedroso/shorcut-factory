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


if __name__ == '__main__':
    unittest.main()
