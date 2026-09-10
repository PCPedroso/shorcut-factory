import unittest
from core.video_processor import get_optimal_video_format


class TestVideoFormatQuality(unittest.TestCase):
    """
    Testes para garantir que a seleção de formatos de vídeo para download
    escolha a máxima resolução e taxa de bits em cada rede social:
    - Instagram: Permite 1080x1920 sem truncar com [height<=1080].
    - Twitter/X: Prioriza streams MP4 HTTP diretos em vez de HLS fragmentado.
    - TikTok: Permite 1080x1920 vertical.
    - YouTube: Mantém Full HD 1080p horizontal (1920x1080) e Shorts verticais (1080x1920).
    """

    def test_instagram_format_spec(self):
        urls = [
            "https://www.instagram.com/reel/DdHrKt9tiRQ/",
            "https://instagram.com/p/DFxyz123/",
            "https://instagr.am/tv/xyz789/"
        ]
        for url in urls:
            spec = get_optimal_video_format(url)
            # Garante que não há a restrição restritiva [height<=1080] que rebaixava para 540p
            self.assertNotIn("[height<=1080]", spec)
            # Garante que permite dimensões Full HD verticais (width e height até 1920)
            self.assertIn("width<=1920", spec)
            self.assertIn("height<=1920", spec)

    def test_twitter_x_format_spec(self):
        urls = [
            "https://x.com/i/status/2097418273868706066",
            "https://twitter.com/user/status/1838612889240408544",
            "https://x.com/SpaceX/status/2094507344713388274"
        ]
        for url in urls:
            spec = get_optimal_video_format(url)
            # No Twitter/X, deve priorizar MP4 direto (onde estão os bitrates de até 10Mbps)
            self.assertTrue(spec.startswith("best[ext=mp4]"), f"Twitter spec deve priorizar best[ext=mp4]: {spec}")
            self.assertNotIn("[height<=1080]", spec)

    def test_tiktok_format_spec(self):
        url = "https://www.tiktok.com/@user/video/7381234567890"
        spec = get_optimal_video_format(url)
        self.assertIn("width<=1920", spec)
        self.assertIn("height<=1920", spec)
        self.assertNotIn("[height<=1080]", spec)

    def test_youtube_and_default_format_spec(self):
        urls = [
            "https://www.youtube.com/watch?v=2b9djWKShlM",
            "https://www.youtube.com/shorts/C1DUSEHWQbg",
            "https://youtu.be/swd0rS-43q0",
            "https://globo.com/video.mp4"
        ]
        for url in urls:
            spec = get_optimal_video_format(url)
            # Permite tanto 1920x1080 (horizontal) quanto 1080x1920 (Shorts)
            self.assertIn("width<=1920", spec)
            self.assertIn("height<=1920", spec)
            self.assertNotIn("[height<=1080]", spec)


if __name__ == "__main__":
    unittest.main()
