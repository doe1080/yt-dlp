import urllib.parse

from .common import InfoExtractor
from ..utils import (
    UserNotLive,
    parse_iso8601,
    str_or_none,
    update_url,
    update_url_query,
)
from ..utils.traversal import traverse_obj


class EasyBroadcastLiveIE(InfoExtractor):
    IE_NAME = 'easybroadcast:live'

    _VALID_URL = r'https?://(?:\w+\.)?player\.easybroadcast\.io/events/(?P<id>\w+)'
    _EMBED_REGEX = [rf'<iframe[^>]+\bsrc\s*=\s*["\'](?P<url>{_VALID_URL})']
    _TESTS = [{
        'url': 'https://al24.player.easybroadcast.io/events/66_al24_u4yga6h',
        'info_dict': {
            'id': '66_al24_u4yga6h',
            'ext': 'mp4',
            'title': str,
            'live_status': 'is_live',
            'modified_date': '20250412',
            'modified_timestamp': 1744496645,
            'release_date': '20241124',
            'release_timestamp': 1732438800,
            'uploader_id': '66',
        },
        'params': {
            'nocheckcertificate': True,
            'skip_download': 'Livestream',
        },
    }, {
        'url': 'https://snrt.player.easybroadcast.io/events/73_aloula_w1dqfwm',
        'info_dict': {
            'id': '73_aloula_w1dqfwm',
            'ext': 'mp4',
            'title': str,
            'live_status': 'is_live',
            'modified_date': '20250603',
            'modified_timestamp': 1748966214,
            'release_date': '20250312',
            'release_timestamp': 1741777200,
            'uploader_id': '73',
        },
        'params': {
            'nocheckcertificate': True,
            'skip_download': 'Livestream',
        },
    }]
    _WEBPAGE_TESTS = [{
        'url': 'https://al24news.dz/en/live',
        'info_dict': {
            'id': '66_al24_u4yga6h',
            'ext': 'mp4',
            'title': str,
            'live_status': 'is_live',
        },
        'skip': 'Geo-restricted to Algeria',
    }, {
        'url': 'https://snrtlive.ma/fr/al-aoula',
        'info_dict': {
            'id': '73_aloula_w1dqfwm',
            'ext': 'mp4',
            'title': str,
            'live_status': 'is_live',
        },
        'skip': 'Geo-restricted to Algeria',
    }]

    def _real_extract(self, url):
        event_id = self._match_id(url)
        metadata = self._download_json(
            update_url(url, query=None).replace('/events', '/api/events'), event_id)
        if metadata.get('status') != 'goLive':
            raise UserNotLive(video_id=event_id)

        m3u8_url = metadata['stream']
        token = None
        if metadata.get('token_authentication'):
            token = dict(urllib.parse.parse_qsl(self._download_webpage(
                'https://token.easybroadcast.io/all', event_id, 'Fetching token',
                'Unable to fetch token', fatal=True, query={'url': m3u8_url})))

        formats = self._extract_m3u8_formats(
            m3u8_url, event_id, 'mp4', m3u8_id='hls', live=True, query=token)
        for fmt in formats:
            fmt['url'] = update_url_query(fmt['url'], token)

        return {
            'id': event_id,
            'formats': formats,
            'is_live': True,
            **traverse_obj(metadata, {
                'title': ('name', {str.upper}),
                'modified_timestamp': ('updated_at', {parse_iso8601}),
                'release_timestamp': ('start', {parse_iso8601}),
                'uploader_id': ('user_id', {str_or_none}),
            }),
        }
