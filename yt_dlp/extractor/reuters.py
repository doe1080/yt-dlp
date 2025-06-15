from .common import InfoExtractor
from ..utils import (
    clean_html,
    float_or_none,
    parse_iso8601,
    str_or_none,
    url_or_none,
)
from ..utils.traversal import require, traverse_obj


class ReutersIE(InfoExtractor):
    _VALID_URL = r'https?://(?:[^/]+\.)?reuters\.com/(?P<type>[^/]+)/(?:[^/]+/)*(?P<id>[^/?#&]+)(?:[/?#]|$)'
    _TESTS = [{
        'url': 'https://www.reuters.com/video/watch/idRW929604062025RP1/',
        'info_dict': {
            'id': 'RW929604062025RP1',
            'ext': 'mp4',
            'title': 'Iraqi farmers use sprinklers to grow crops in desert',
            'description': 'md5:1f757f36e42c1fd3caf2b7703f766a57',
            'display_id': 'idRW929604062025RP1',
            'duration': 119.285,
            'modified_date': '20250605',
            'modified_timestamp': 1749135780,
            'release_timestamp': 1749135015,
            'release_date': '20250605',
            'thumbnail': r're:https?://ajo\.prod\.reuters\.tv/api/v2/img/.+',
        },
    }, {
        'url': 'https://www.reuters.com/sustainability/sustainable-finance-reporting/uk-economy-shrinks-by-03-april-ons-says-2025-06-12/',
        'info_dict': {
            'id': 'RW123512062025RP1',
            'ext': 'mp4',
            'title': 'UK economy shrinks by the most since 2023 as U.S. tariffs hit',
            'description': 'md5:d86475d0b5dcb8268d49c99fbce92e5c',
            'display_id': 'uk-economy-shrinks-by-03-april-ons-says-2025-06-12',
            'duration': 78.745,
            'modified_date': '20250612',
            'modified_timestamp': 1749726678,
            'release_timestamp': 1749723417,
            'release_date': '20250612',
            'thumbnail': r're:https?://ajo\.prod\.reuters\.tv/api/v2/img/.+',
        },
    }, {
        'url': 'https://www.reuters.com/podcasts/drone-wars-2025-06-14/',
        'info_dict': {
            'id': 'THRH8451800069',
            'ext': 'mp3',
            'title': 'Drone wars',
            'description': 'md5:3e87ebb3f1b41d68c802398e4c5c57bd',
            'display_id': 'THRH8451800069',
            'duration': 1246.32,
            'release_timestamp': 1749895200,
            'release_date': '20250614',
            'series': 'Reuters World News',
            'thumbnail': r're:https?://megaphone\.imgix\.net/podcasts/.+\.(?:jpe?g|png)',
        },
        'add_ie': ['Megaphone'],
    }]

    def _real_extract(self, url):
        url_type, display_id = self._match_valid_url(url).group('type', 'id')
        webpage = self._download_webpage(url, display_id)

        if url_type == 'podcasts':
            cache = self._search_json(
                r'Fusion\.contentCache\s*=', webpage, 'content cache', display_id)
            megaphone_id = traverse_obj(cache, (
                'transcript-by-episode-id-v1', ..., 'data', 'result',
                'episode', 'uid', {str}, any, {require('megaphone ID')}))
            return self.url_result(
                f'https://player.megaphone.fm/{megaphone_id}', 'Megaphone')

        content = self._search_json(
            r'Fusion\.globalContent\s*=', webpage, 'global content', display_id)
        if url_type == 'video':
            m3u8_url = self._og_search_property('video:url', webpage, 'manifest URL')
        else:
            m3u8_url = traverse_obj(self._yield_json_ld(webpage, display_id), (
                lambda _, v: v['video']['@type'] == 'VideoObject', 'video',
                'embedUrl', {url_or_none}, any, {require('manifest URL')}))

        video = traverse_obj(content, (
            'result', ('related_content', None), 'videos',
            lambda _, v: v['source']['hls'] == m3u8_url, any))
        formats, subtitles = self._extract_m3u8_formats_and_subtitles(m3u8_url, display_id, 'mp4')

        return {
            'display_id': display_id,
            'formats': formats,
            'subtitles': subtitles,
            **traverse_obj(video, {
                'id': ('id', {str_or_none}),
                'title': ('title', {clean_html}),
                'duration': ('duration', {float_or_none}),
                'description': ('description', {clean_html}),
                'modified_timestamp': ('updated_time', {parse_iso8601}),
                'release_timestamp': ('published_time', {parse_iso8601}),
                'thumbnail': ('thumbnail', 'url', {url_or_none}),
            }),
        }
