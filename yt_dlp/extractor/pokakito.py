import re

from .common import InfoExtractor
from ..utils import unified_timestamp


class PokakitoIE(InfoExtractor):
    _VALID_URL = r'https?://www\.po-kaki-to\.com/archives/(?P<id>[\w-]+)\.html'
    _TESTS = [{
        'url': 'https://www.po-kaki-to.com/archives/35004.html',
        'info_dict': {
            'id': '35004_1',
            'ext': 'mp4',
            'title': '【速報】宇宙人、襲来',
            'display_id': '35004',
            'timestamp': 1745031658,
            'upload_date': '20250419',
        },
    }]

    def _real_extract(self, url):
        page_id = self._match_id(url)
        webpage = self._download_webpage(url, page_id)
        entries = [{
            'id': f'{page_id}_{n}',
            'ext': 'mp4',
            'title': re.sub(r'\s+-\s+ポッカキット', '', self._og_search_title(webpage)),
            'display_id': page_id,
            'http_headers': {'Referer': url},
            'timestamp': unified_timestamp(self._html_search_meta('article:published_time', webpage)),
            'url': video_url,
        } for n, video_url in enumerate(re.findall(r'type\s*=\s*"video/mp4"\s+src\s*=\s*"([^"]+)"', webpage), 1)]

        return self.playlist_result(entries, page_id)
