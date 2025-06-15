import itertools

from .common import InfoExtractor
from ..utils import (
    ExtractorError,
    clean_html,
    float_or_none,
    parse_iso8601,
    parse_qs,
    update_url,
    url_or_none,
)
from ..utils.traversal import require, traverse_obj


class MegaphoneIE(InfoExtractor):
    IE_NAME = 'megaphone'

    _BASE_URL = 'https://player.megaphone.fm'
    _VALID_URL = r'https?://(?:play(?:er|list))\.megaphone\.fm/(?:\?[ep]=)?(?P<id>[A-Z0-9]+)'
    _EMBED_REGEX = [rf'<iframe[^>]+\bsrc\s*=\s*["\'](?P<url>{_VALID_URL})']
    _TESTS = [{
        'url': 'https://player.megaphone.fm/GLT9749789991',
        'info_dict': {
            'id': 'GLT9749789991',
            'ext': 'mp3',
            'title': '#97 What Kind Of Idiot Gets Phished?',
            'description': 'md5:8fc2ba1da0efb099ef928df127358a90',
            'duration': 1998.36,
            'release_date': '20170518',
            'release_timestamp': 1495101600,
            'series': 'Reply All',
            'thumbnail': r're:https?://megaphone\.imgix\.net/podcasts/.+\.(?:jpe?g|png)',
        },
    }, {
        'url': 'https://playlist.megaphone.fm/?e=THRH8451800069',
        'info_dict': {
            'id': 'THRH8451800069',
            'ext': 'mp3',
            'title': 'Drone wars',
            'description': 'md5:3e87ebb3f1b41d68c802398e4c5c57bd',
            'duration': 1246.32,
            'release_date': '20250614',
            'release_timestamp': 1749895200,
            'series': 'Reuters World News',
            'thumbnail': r're:https?://megaphone\.imgix\.net/podcasts/.+\.(?:jpe?g|png)',
        },
    }, {
        'url': 'https://playlist.megaphone.fm/?p=BL5764516365',
        'info_dict': {
            'id': 'BL5764516365',
        },
        'playlist_count': 65,
    }]

    def _entries(self, playlist_id):
        for page in itertools.count(1):
            playlist = self._download_json(
                f'{self._BASE_URL}/playlist/{playlist_id}', playlist_id,
                f'Downloading page {page}', query={'page': page})
            for episode_id in traverse_obj(playlist, (
                'episodes', ..., 'uid', {str}, filter, all, filter,
            )):
                yield self.url_result(f'{self._BASE_URL}/{episode_id}')

            if playlist['limit'] * page >= playlist['totalCount']:
                break

    def _real_extract(self, url):
        megaphone_id = self._match_id(url)
        query = {k: v[0] for k, v in parse_qs(url).items() if v}
        if 'p' in query:
            return self.playlist_result(self._entries(megaphone_id), megaphone_id)

        episode = self._download_json(
            f'{self._BASE_URL}/playlist/episode/{megaphone_id}',
            megaphone_id, expected_status=404)
        if errors := episode.get('errors'):
            raise ExtractorError(errors, expected=True)

        return {
            'id': megaphone_id,
            'series': traverse_obj(episode, ('podcastTitle', {clean_html})),
            'vcodec': 'none',
            **traverse_obj(episode, ('episodes', ..., {
                'title': ('title', {clean_html}),
                'alt_title': ('subtitle', {clean_html}, filter),
                'description': ('summary', {clean_html}),
                'duration': ('duration', {float_or_none}),
                'release_timestamp': ('pubDate', {parse_iso8601}),
                'thumbnail': ('imageUrl', {url_or_none}, {update_url(query=None)}),
                'url': ('audioUrl', {self._proto_relative_url}, {url_or_none}, {require('podcast source')}),
            }, any)),
        }
